import json
import os
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from firebase_admin import auth
from functools import wraps
from google import generativeai as genai

from .models import User, Organization, GenieAnalysis, Topic


def firebase_auth_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'No token provided'}, status=401)

        token = auth_header.split(' ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            request.firebase_user = decoded_token
            return view_func(request, *args, **kwargs)
        except auth.ExpiredIdTokenError:
            return JsonResponse({'error': 'Token expired'}, status=401)
        except auth.RevokedIdTokenError:
            return JsonResponse({'error': 'Token revoked'}, status=401)
        except Exception:
            return JsonResponse({'error': 'Invalid token'}, status=401)

    return wrapped_view


def get_news_context(organization, topic_ids=None):
    """Get news context from organization's topics.
    
    Args:
        organization: Organization object
        topic_ids: Optional list of topic IDs to filter by
    """
    if topic_ids:
        topics = organization.topics.filter(id__in=topic_ids)
    else:
        topics = organization.topics.all()
    
    context = ""

    for topic in topics:
        latest_summary = topic.summaries.first()
        if not latest_summary:
            continue

        context += f"\n## Topic: {topic.name}\n"

        if latest_summary.final_summary:
            if isinstance(latest_summary.final_summary, dict):
                for item in latest_summary.final_summary.get('summary', []):
                    context += f"**{item.get('title', '')}**\n{item.get('content', '')}\n\n"
            elif isinstance(latest_summary.final_summary, list):
                for item in latest_summary.final_summary:
                    context += f"**{item.get('title', '')}**\n{item.get('content', '')}\n\n"

        if latest_summary.cluster_summaries:
            for cs in latest_summary.cluster_summaries[:3]:
                context += f"{cs[:500]}...\n\n"

    return context


def generate_questionnaire(query):
    """Generate a questionnaire based on user's query to gather more context."""
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or GEMINI_KEY.")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    prompt = f"""You are helping to refine a strategic intelligence query. Based on the user's question, generate 3-5 clarifying questions that will help provide better, more targeted analysis.

USER QUERY: {query}

Generate questions that will help understand:
- Specific context or constraints
- Timeframes or priorities
- Stakeholder perspectives
- Risk tolerance or strategic goals

Your response MUST be a valid JSON object with this exact structure (output ONLY valid JSON, no markdown):

{{
  "questions": [
    {{
      "id": 1,
      "question": "What is your primary timeframe for this decision?",
      "type": "multiple_choice",
      "options": ["1-3 months", "3-6 months", "6-12 months", "1+ years", "Other"]
    }},
    {{
      "id": 2,
      "question": "Which stakeholders are most impacted?",
      "type": "multiple_choice",
      "options": ["Customers", "Investors", "Employees", "Partners", "Other"]
    }}
  ]
}}

RULES:
- Generate 3-5 questions
- Each question can be "multiple_choice" or "text"
- Multiple choice questions should have 4-6 options, with "Other" as the last option
- Questions should be specific and actionable
- Focus on clarifying the strategic context"""

    response = model.generate_content(prompt)
    response_text = response.text.strip()

    # Extract JSON
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        response_text = response_text[start_idx:end_idx + 1]

    try:
        questionnaire = json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback questionnaire
        questionnaire = {
            "questions": [
                {
                    "id": 1,
                    "question": "What is your primary timeframe for this analysis?",
                    "type": "multiple_choice",
                    "options": ["Immediate (0-3 months)", "Short-term (3-6 months)", "Medium-term (6-12 months)", "Long-term (1+ years)", "Other"]
                },
                {
                    "id": 2,
                    "question": "What is your main focus area?",
                    "type": "multiple_choice",
                    "options": ["Market analysis", "Competitive intelligence", "Risk assessment", "Opportunity identification", "Other"]
                },
                {
                    "id": 3,
                    "question": "Any additional context or constraints?",
                    "type": "text",
                    "options": []
                }
            ]
        }

    return questionnaire


def generate_analysis(organization, query, questionnaire_answers, news_context):
    # Support both GEMINI_API_KEY and GEMINI_KEY for backwards compatibility
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or GEMINI_KEY.")

    genai.configure(api_key=gemini_key)
    # Use gemini-2.5-flash-lite (cheapest smart model)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    org_context = f"""
ORGANIZATION CONTEXT:
- Name: {organization.name}
- Industry: {organization.industry or 'Not specified'}
- Description: {organization.description or 'Not specified'}
- Headquarters: {organization.headquarters or 'Not specified'}
- Employee Count: {organization.employee_count or 'Not specified'}
- Annual Revenue: {organization.annual_revenue or 'Not specified'}
- Key Products: {', '.join(organization.key_products or []) or 'Not specified'}
- Competitors: {', '.join(organization.competitors or []) or 'Not specified'}
- Target Markets: {', '.join(organization.target_markets or []) or 'Not specified'}
- Strategic Priorities: {', '.join(organization.strategic_priorities or []) or 'Not specified'}
"""

    # Format questionnaire answers
    qa_context = "\nCLARIFYING INFORMATION FROM USER:\n"
    for qa in questionnaire_answers:
        qa_context += f"Q: {qa.get('question', '')}\nA: {qa.get('answer', '')}\n\n"

    prompt = f"""You are Briefed Genie, a strategic intelligence analyst. Provide deep, actionable analysis tailored to the user's specific organization.

{org_context}
{qa_context}

RECENT NEWS CONTEXT:
{news_context[:15000]}

USER QUERY: {query}

Analyze this query in the context of the organization above and the clarifying information provided. Your response MUST be a valid JSON object with this exact structure (output ONLY valid JSON, no markdown code blocks):

{{
  "top_insight": {{
    "title": "Main finding in one clear sentence",
    "summary": "2-3 sentence explanation of the key insight",
    "relevance_badge": "High Relevance"
  }},
  "key_takeaways": [
    "First key takeaway with specific data or findings",
    "Second key takeaway",
    "Third key takeaway",
    "Fourth key takeaway",
    "Fifth key takeaway"
  ],
  "featured_quote": {{
    "text": "An insightful quote from analysis or sources",
    "attribution": "Source or expert name and title"
  }},
  "sources_analyzed": 8,
  "full_analysis": {{
    "executive_summary": "2-3 paragraph summary of findings",
    "current_dynamics": "Analysis of current market/situation dynamics",
    "positive_indicators": ["Indicator 1", "Indicator 2"],
    "negative_indicators": ["Indicator 1", "Indicator 2"],
    "neutral_factors": ["Factor 1", "Factor 2"],
    "historical_context": "Comparison to previous situations or trends",
    "risk_assessment": [
      {{
        "category": "Market Risk",
        "description": "Description of the risk",
        "severity": "medium"
      }}
    ],
    "probability_assessment": {{
      "scenario_1": {{"name": "Optimistic scenario", "probability": "30-40%"}},
      "scenario_2": {{"name": "Base case", "probability": "40-50%"}},
      "scenario_3": {{"name": "Pessimistic scenario", "probability": "15-25%"}}
    }}
  }},
  "recommendations": {{
    "strategic_planning": "Specific strategic recommendations",
    "risk_management": "Risk management recommendations",
    "timing": "Timing and execution recommendations"
  }},
  "further_questions": [
    "Question 1 to consider",
    "Question 2 to consider",
    "Question 3 to consider",
    "Question 4 to consider"
  ],
  "confidence_score": 0.85,
  "data_freshness": "{datetime.now().strftime('%Y-%m-%d')}"
}}

IMPORTANT:
- Be specific to THIS organization, not generic advice
- Reference their products, competitors, and markets by name when relevant
- Quantify impact where possible
- Prioritize actionability over comprehensiveness
- impact_score should be 1-10
- impact_level should be: low, medium, high, or critical
- relevance should be: low, medium, high, or critical
- severity should be: low, medium, high, or critical
- potential_impact should be: low, medium, or high
- timeline should be: Immediate, Short-term, Medium-term, or Long-term"""

    response = model.generate_content(prompt)
    response_text = response.text.strip()

    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        response_text = response_text[start_idx:end_idx + 1]

    try:
        analysis_data = json.loads(response_text)
    except json.JSONDecodeError:
        analysis_data = {
            "top_insight": {
                "title": "Analysis generated",
                "summary": response_text[:200],
                "relevance_badge": "Medium Relevance"
            },
            "key_takeaways": ["Analysis in progress", "Please review results"],
            "featured_quote": {"text": "", "attribution": ""},
            "sources_analyzed": 0,
            "full_analysis": {
                "executive_summary": response_text,
                "current_dynamics": "",
                "positive_indicators": [],
                "negative_indicators": [],
                "neutral_factors": [],
                "historical_context": "",
                "risk_assessment": [],
                "probability_assessment": {}
            },
            "recommendations": {
                "strategic_planning": "",
                "risk_management": "",
                "timing": ""
            },
            "further_questions": [],
            "confidence_score": 0.5,
            "data_freshness": datetime.now().strftime('%Y-%m-%d')
        }

    return analysis_data


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET", "PUT"])
def organization_profile(request):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.select_related('organization').get(email=email)
        organization = user.organization

        if request.method == "GET":
            return JsonResponse({
                'id': organization.id,
                'name': organization.name,
                'industry': organization.industry,
                'description': organization.description,
                'headquarters': organization.headquarters,
                'employee_count': organization.employee_count,
                'annual_revenue': organization.annual_revenue,
                'key_products': organization.key_products or [],
                'competitors': organization.competitors or [],
                'target_markets': organization.target_markets or [],
                'strategic_priorities': organization.strategic_priorities or [],
            })

        elif request.method == "PUT":
            if user.role != 'admin':
                return JsonResponse({'error': 'Only admins can update organization profile'}, status=403)

            data = json.loads(request.body)

            if 'industry' in data:
                organization.industry = data['industry']
            if 'description' in data:
                organization.description = data['description']
            if 'headquarters' in data:
                organization.headquarters = data['headquarters']
            if 'employee_count' in data:
                organization.employee_count = data['employee_count']
            if 'annual_revenue' in data:
                organization.annual_revenue = data['annual_revenue']
            if 'key_products' in data:
                organization.key_products = data['key_products']
            if 'competitors' in data:
                organization.competitors = data['competitors']
            if 'target_markets' in data:
                organization.target_markets = data['target_markets']
            if 'strategic_priorities' in data:
                organization.strategic_priorities = data['strategic_priorities']

            organization.save()

            return JsonResponse({
                'success': True,
                'message': 'Organization profile updated',
                'organization': {
                    'id': organization.id,
                    'name': organization.name,
                    'industry': organization.industry,
                    'description': organization.description,
                    'headquarters': organization.headquarters,
                    'employee_count': organization.employee_count,
                    'annual_revenue': organization.annual_revenue,
                    'key_products': organization.key_products or [],
                    'competitors': organization.competitors or [],
                    'target_markets': organization.target_markets or [],
                    'strategic_priorities': organization.strategic_priorities or [],
                }
            })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in organization_profile: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def questionnaire(request):
    """Generate a questionnaire based on user's query."""
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        data = json.loads(request.body)
        query = data.get('query')

        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)

        try:
            questionnaire_data = generate_questionnaire(query)
            return JsonResponse({
                'success': True,
                'questionnaire': questionnaire_data
            })
        except Exception as e:
            print(f"Questionnaire generation failed: {str(e)}")
            return JsonResponse({
                'error': 'Failed to generate questionnaire'
            }, status=500)

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in questionnaire: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def analyze(request):
    """Generate final analysis with questionnaire answers and selected topics."""
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.select_related('organization').get(email=email)
        organization = user.organization

        data = json.loads(request.body)
        query = data.get('query')
        questionnaire_answers = data.get('questionnaire_answers', [])
        topic_ids = data.get('topic_ids', [])

        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)

        analysis = GenieAnalysis.objects.create(
            user=user,
            organization=organization,
            query=query,
            status='processing'
        )

        try:
            # Get news context from selected topics
            news_context = get_news_context(organization, topic_ids if topic_ids else None)
            
            # Generate analysis with questionnaire answers
            results = generate_analysis(organization, query, questionnaire_answers, news_context)

            analysis.results = results
            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()

            return JsonResponse({
                'id': analysis.id,
                'status': 'completed',
                'query': analysis.query,
                'results': results,
                'created_at': analysis.created_at,
                'completed_at': analysis.completed_at,
            })

        except Exception as e:
            analysis.status = 'failed'
            analysis.results = {'error': str(e)}
            analysis.save()
            print(f"Analysis generation failed: {str(e)}")
            return JsonResponse({
                'id': analysis.id,
                'status': 'failed',
                'error': 'Analysis generation failed'
            }, status=500)

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in analyze: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET"])
def analysis_detail(request, analysis_id):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        analysis = GenieAnalysis.objects.filter(
            id=analysis_id,
            user=user
        ).first()

        if not analysis:
            return JsonResponse({'error': 'Analysis not found'}, status=404)

        return JsonResponse({
            'id': analysis.id,
            'status': analysis.status,
            'query': analysis.query,
            'results': analysis.results,
            'sources': analysis.sources,
            'created_at': analysis.created_at,
            'completed_at': analysis.completed_at,
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error in analysis_detail: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET"])
def analyses_list(request):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        analyses = GenieAnalysis.objects.filter(user=user)

        data = []
        for analysis in analyses:
            impact_level = None
            if analysis.results and isinstance(analysis.results, dict):
                impact_level = analysis.results.get('impact_level')

            data.append({
                'id': analysis.id,
                'query': analysis.query[:100] + ('...' if len(analysis.query) > 100 else ''),
                'status': analysis.status,
                'impact_level': impact_level,
                'created_at': analysis.created_at,
                'completed_at': analysis.completed_at,
            })

        return JsonResponse({'analyses': data})

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error in analyses_list: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["DELETE"])
def delete_analysis(request, analysis_id):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        analysis = GenieAnalysis.objects.filter(
            id=analysis_id,
            user=user
        ).first()

        if not analysis:
            return JsonResponse({'error': 'Analysis not found'}, status=404)

        analysis.delete()
        return JsonResponse({'success': True, 'message': 'Analysis deleted'})

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error in delete_analysis: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)
