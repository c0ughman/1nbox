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


def get_news_context(organization):
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


def generate_analysis(organization, query, news_context):
    gemini_key = os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

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

    prompt = f"""You are Briefed Genie, a strategic intelligence analyst. Provide deep, actionable analysis tailored to the user's specific organization.

{org_context}

RECENT NEWS CONTEXT:
{news_context[:15000]}

USER QUERY: {query}

Analyze this query in the context of the organization above. Your response MUST be a valid JSON object with this exact structure (output ONLY valid JSON, no markdown code blocks):

{{
  "executive_summary": "2-3 paragraph summary of findings and implications for this specific organization",
  "impact_score": 7.5,
  "impact_level": "high",
  "key_findings": [
    {{
      "title": "Finding title",
      "description": "Detailed description",
      "relevance": "critical",
      "source_count": 3
    }}
  ],
  "opportunities": [
    {{
      "title": "Opportunity title",
      "description": "Description",
      "potential_impact": "high"
    }}
  ],
  "threats": [
    {{
      "title": "Threat title",
      "description": "Description",
      "severity": "medium"
    }}
  ],
  "recommendations": [
    {{
      "priority": 1,
      "action": "Specific action to take",
      "timeline": "Immediate",
      "rationale": "Why this action"
    }}
  ],
  "competitive_landscape": {{
    "summary": "How competitors are positioned",
    "competitor_moves": [
      {{
        "competitor": "Competitor name",
        "action": "What they did/are doing",
        "implication": "What this means for the user's org"
      }}
    ]
  }},
  "timeline": {{
    "short_term": ["Action 1", "Action 2"],
    "medium_term": ["Action 1", "Action 2"],
    "long_term": ["Action 1", "Action 2"]
  }},
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
            "executive_summary": response_text,
            "impact_score": 5,
            "impact_level": "medium",
            "key_findings": [],
            "opportunities": [],
            "threats": [],
            "recommendations": [],
            "competitive_landscape": {"summary": "", "competitor_moves": []},
            "timeline": {"short_term": [], "medium_term": [], "long_term": []},
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
def analyze(request):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.select_related('organization').get(email=email)
        organization = user.organization

        data = json.loads(request.body)
        query = data.get('query')

        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)

        analysis = GenieAnalysis.objects.create(
            user=user,
            organization=organization,
            query=query,
            status='processing'
        )

        try:
            news_context = get_news_context(organization)
            results = generate_analysis(organization, query, news_context)

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
