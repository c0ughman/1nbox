import json
import os
import time
import re
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from firebase_admin import auth
from functools import wraps
from google import generativeai as genai
from urllib.parse import urlparse

# Import genai_client only when needed (for Deep Research Interactions API)
# This avoids import errors if the package isn't available
try:
    from google import genai as genai_client
except ImportError:
    # If google.genai is not available, set to None
    # Deep Research functions will handle this gracefully
    genai_client = None

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
    
    Returns:
        tuple: (context_string, sources_list)
    """
    if topic_ids:
        topics = organization.topics.filter(id__in=topic_ids)
    else:
        topics = organization.topics.all()
    
    context = ""
    sources = []

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
        
        # Collect sources from topic
        if topic.sources:
            for source_url in topic.sources:
                try:
                    parsed = urlparse(source_url)
                    domain = parsed.netloc.replace('www.', '')
                    if domain and domain not in [s.get('domain', '') for s in sources]:
                        sources.append({
                            'url': source_url,
                            'domain': domain,
                            'name': domain.split('.')[0].title() if '.' in domain else domain,
                            'type': 'topic'
                        })
                except:
                    pass

    return context, sources


def extract_images_and_sources_from_deep_research(deep_research_results):
    """Extract images and sources from Deep Research results.
    
    Args:
        deep_research_results: String containing Deep Research output
    
    Returns:
        tuple: (images_list, sources_list)
    """
    images = []
    sources = []
    
    if not deep_research_results:
        return images, sources
    
    # Extract URLs (both images and regular URLs)
    url_pattern = r'https?://[^\s\)]+'
    urls = re.findall(url_pattern, deep_research_results)
    
    # Image extensions
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']
    
    for url in urls:
        # Clean URL (remove trailing punctuation)
        url = url.rstrip('.,;:!?)')
        
        # Check if it's an image
        is_image = any(url.lower().endswith(ext) for ext in image_extensions) or 'image' in url.lower()
        
        if is_image:
            # Extract domain for image source
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                if url not in [img.get('url', '') for img in images]:
                    images.append({
                        'url': url,
                        'source': domain,
                        'alt': f'Chart from {domain}'
                    })
            except:
                pass
        else:
            # Regular source URL
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                if domain and url not in [s.get('url', '') for s in sources]:
                    sources.append({
                        'url': url,
                        'domain': domain,
                        'name': domain.split('.')[0].title() if '.' in domain else domain,
                        'type': 'deep_research'
                    })
            except:
                pass
    
    # Also look for citation patterns in the text
    citation_patterns = [
        r'\[(\d+)\]\((https?://[^\)]+)\)',  # Markdown links [1](url)
        r'Source:\s*(https?://[^\s]+)',  # Source: url
        r'Cited:\s*(https?://[^\s]+)',  # Cited: url
        r'Reference:\s*(https?://[^\s]+)',  # Reference: url
    ]
    
    for pattern in citation_patterns:
        matches = re.findall(pattern, deep_research_results, re.IGNORECASE)
        for match in matches:
            url = match if isinstance(match, str) else match[1] if isinstance(match, tuple) else match
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                if domain and url not in [s.get('url', '') for s in sources]:
                    sources.append({
                        'url': url,
                        'domain': domain,
                        'name': domain.split('.')[0].title() if '.' in domain else domain,
                        'type': 'deep_research'
                    })
            except:
                pass
    
    return images, sources


def start_deep_research(query, organization):
    """Start Deep Research in background and return interaction ID.
    
    Args:
        query: User's query
        organization: Organization object for context
    
    Returns:
        interaction_id: String ID to track the research task
    """
    if genai_client is None:
        raise ImportError(
            "Deep Research requires the 'google-genai' package. "
            "Install it with: pip install google-genai"
        )
    
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or GEMINI_KEY.")
    
    client = genai_client.Client(api_key=gemini_key)
    
    # Build comprehensive research prompt focused on decision-making
    research_prompt = f"""You are conducting comprehensive deep research to support a critical business decision.

DECISION CONTEXT:
{query}

ORGANIZATION BACKGROUND:
- Organization: {organization.name}
- Industry: {organization.industry or 'Not specified'}
- Key Products/Services: {', '.join(organization.key_products or []) or 'Not specified'}
- Main Competitors: {', '.join(organization.competitors or []) or 'Not specified'}
- Target Markets: {', '.join(organization.target_markets or []) or 'Not specified'}
- Strategic Priorities: {', '.join(organization.strategic_priorities or []) or 'Not specified'}

RESEARCH OBJECTIVES:
Your goal is to gather ALL information necessary for making the best possible decision. This research will be used to create a comprehensive decision support report.

Please investigate and provide:

1. **Current Market Dynamics & Trends**
   - Latest developments in the relevant market/industry
   - Key trends that could impact this decision
   - Market size, growth rates, and forecasts

2. **Historical Context & Precedents**
   - Similar decisions/situations from the past
   - What worked and what didn't
   - Lessons learned from comparable scenarios

3. **Risk Analysis**
   - Potential risks and their likelihood
   - Risk mitigation strategies
   - Early warning signs to monitor

4. **Opportunity Assessment**
   - Potential benefits and upside scenarios
   - Competitive advantages that could be leveraged
   - Timing considerations and windows of opportunity

5. **Expert Perspectives & Analysis**
   - Industry expert opinions
   - Analyst reports and forecasts
   - Academic research if relevant

6. **Quantitative Data & Metrics**
   - Relevant statistics and data points
   - Financial implications and projections
   - Benchmarks and comparisons

7. **Stakeholder Considerations**
   - Impact on different stakeholder groups
   - Customer sentiment and needs
   - Competitive responses to anticipate

IMPORTANT INSTRUCTIONS:
- Focus on ACTIONABLE insights that will directly inform decision-making
- Prioritize recent, relevant information (last 6-12 months most important)
- Include specific data points, numbers, and citations wherever possible
- Look for both supporting and contradicting evidence
- Consider multiple scenarios and perspectives
- This is for strategic business decision support - be thorough and objective

Format your research with clear sections, bullet points, and citations. Include source URLs for all major findings."""
    
    try:
        # Start Deep Research with the agent
        interaction = client.interactions.create(
            input=research_prompt,
            agent='deep-research-pro-preview-12-2025',
            background=True
        )
        
        print(f"Deep Research started: {interaction.id}")
        return interaction.id
        
    except Exception as e:
        print(f"Failed to start Deep Research: {str(e)}")
        raise


def get_deep_research_results(interaction_id, timeout_minutes=15):
    """Poll for Deep Research completion and return results.
    
    Args:
        interaction_id: The interaction ID from start_deep_research
        timeout_minutes: Maximum time to wait (default 15 minutes)
    
    Returns:
        research_results: String containing the research findings
    """
    if genai_client is None:
        raise ImportError(
            "Deep Research requires the 'google-genai' package. "
            "Install it with: pip install google-genai"
        )
    
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found.")
    
    client = genai_client.Client(api_key=gemini_key)
    
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    poll_interval = 10  # Poll every 10 seconds
    
    print(f"Polling for Deep Research results: {interaction_id}")
    
    while True:
        try:
            interaction = client.interactions.get(interaction_id)
            
            if interaction.status == "completed":
                print(f"Deep Research completed: {interaction_id}")
                # Get the final output text
                if interaction.outputs and len(interaction.outputs) > 0:
                    return interaction.outputs[-1].text
                else:
                    return "Deep Research completed but no output was generated."
            
            elif interaction.status == "failed":
                error_msg = f"Deep Research failed: {getattr(interaction, 'error', 'Unknown error')}"
                print(error_msg)
                raise Exception(error_msg)
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                timeout_msg = f"Deep Research exceeded {timeout_minutes} minute timeout (still processing)"
                print(timeout_msg)
                raise TimeoutError(timeout_msg)
            
            # Log progress
            remaining = timeout_seconds - elapsed
            print(f"Deep Research still processing... {remaining:.0f}s remaining")
            
            # Wait before next poll
            time.sleep(poll_interval)
            
        except (TimeoutError, Exception) as e:
            # Re-raise the exception to be handled by caller
            raise


def generate_questionnaire(query):
    """Generate a questionnaire based on user's query to gather more context."""
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or GEMINI_KEY.")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-3-flash-preview")

    prompt = f"""You are helping a user make an important strategic decision. Based on their question, generate 3-5 clarifying questions that will help them make the best possible decision.

USER QUERY: {query}

Generate questions that will help understand:
- User's preferences and priorities
- Trade-offs they're willing to accept
- Constraints and requirements
- Risk tolerance
- Decision criteria and success metrics
- Stakeholder perspectives that matter

The goal is to gather information that will inform a comprehensive decision-making report - "everything you need to know before making this decision."

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


def generate_analysis(organization, query, questionnaire_answers, news_context, deep_research_results="", images=None, sources=None):
    # Support both GEMINI_API_KEY and GEMINI_KEY for backwards compatibility
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found. Set GEMINI_API_KEY or GEMINI_KEY.")

    genai.configure(api_key=gemini_key)
    # Use gemini-3-pro-preview for comprehensive decision support
    model = genai.GenerativeModel("gemini-3-pro-preview")

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

    # Add deep research section if available
    deep_research_section = ""
    if deep_research_results:
        # Limit deep research to 25,000 characters to avoid token limits
        truncated_research = deep_research_results[:25000]
        if len(deep_research_results) > 25000:
            truncated_research += "\n\n[Deep Research results truncated for length...]"
        
        deep_research_section = f"""

DEEP RESEARCH FINDINGS:
{truncated_research}

"""

    prompt = f"""You are Briefed Genie, a strategic decision support system. Your role is to provide everything the user needs to know before making an important decision. This is decision-making support, not just analysis.

{org_context}
{qa_context}

RECENT NEWS CONTEXT:
{news_context[:15000]}
{deep_research_section}

Based on ALL the information provided above (organization context, user preferences, recent news{', and comprehensive deep research findings' if deep_research_results else ''}), generate a comprehensive decision support report. This should be "everything you need to know before making this decision" - complete, actionable, and tailored to help the user make the best possible choice.

Your response MUST be a valid JSON object with this exact structure (output ONLY valid JSON, no markdown code blocks):

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
  "images": [
    {{
      "url": "https://example.com/chart.png",
      "source": "Example Source",
      "alt": "Chart description"
    }}
  ],
  "sources": [
    {{
      "url": "https://example.com/article",
      "domain": "example.com",
      "name": "Example",
      "type": "deep_research"
    }}
  ],
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
    
    # Add images and sources to the response (override if model didn't include them)
    if images:
        analysis_data['images'] = images
    if sources:
        analysis_data['sources'] = sources
        # Update sources_analyzed count
        analysis_data['sources_analyzed'] = len(sources)

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
    """Generate a questionnaire based on user's query and optionally start Deep Research."""
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.select_related('organization').get(email=email)
        organization = user.organization

        data = json.loads(request.body)
        query = data.get('query')
        research_type = data.get('research_type', 'quick')  # 'quick', 'comprehensive', or 'deep'

        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)

        # Validate research_type
        if research_type not in ['quick', 'comprehensive', 'deep']:
            return JsonResponse({'error': 'Invalid research_type'}, status=400)

        try:
            # Generate questionnaire
            questionnaire_data = generate_questionnaire(query)
            
            # Start Deep Research if research_type is 'deep'
            deep_research_id = None
            if research_type == 'deep':
                try:
                    deep_research_id = start_deep_research(query, organization)
                    print(f"Deep Research initiated: {deep_research_id}")
                except Exception as dr_error:
                    # Log the error but don't fail the entire request
                    print(f"Failed to start Deep Research: {str(dr_error)}")
                    # In development, we want to see this error
                    return JsonResponse({
                        'error': f'Failed to start Deep Research: {str(dr_error)}'
                    }, status=500)
            
            response_data = {
                'success': True,
                'questionnaire': questionnaire_data,
                'research_type': research_type
            }
            
            if deep_research_id:
                response_data['deep_research_id'] = deep_research_id
            
            return JsonResponse(response_data)
            
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
    """Generate final analysis with questionnaire answers, selected topics, and optional Deep Research."""
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.select_related('organization').get(email=email)
        organization = user.organization

        data = json.loads(request.body)
        query = data.get('query')
        questionnaire_answers = data.get('questionnaire_answers', [])
        topic_ids = data.get('topic_ids', [])
        research_type = data.get('research_type', 'quick')
        deep_research_id = data.get('deep_research_id')

        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)

        analysis = GenieAnalysis.objects.create(
            user=user,
            organization=organization,
            query=query,
            status='processing',
            research_type=research_type,
            deep_research_id=deep_research_id
        )

        try:
            # Get news context from selected topics (returns context and sources)
            news_context, topic_sources = get_news_context(organization, topic_ids if topic_ids else None)
            
            # Wait for Deep Research to complete if this is a deep research request
            deep_research_results = ""
            deep_research_images = []
            deep_research_sources = []
            if research_type == 'deep' and deep_research_id:
                try:
                    print(f"Waiting for Deep Research to complete: {deep_research_id}")
                    deep_research_results = get_deep_research_results(deep_research_id, timeout_minutes=15)
                    analysis.deep_research_results = deep_research_results
                    analysis.save()
                    print(f"Deep Research completed successfully. Length: {len(deep_research_results)} chars")
                    
                    # Extract images and sources from Deep Research
                    deep_research_images, deep_research_sources = extract_images_and_sources_from_deep_research(deep_research_results)
                    print(f"Extracted {len(deep_research_images)} images and {len(deep_research_sources)} sources from Deep Research")
                except TimeoutError as te:
                    # Deep Research timed out - continue with other sources instead of failing
                    error_msg = f"Deep Research timed out after 15 minutes: {str(te)}"
                    print(error_msg)
                    deep_research_results = error_msg
                    # Continue with analysis using other data sources
                except Exception as dr_error:
                    # Deep Research failed - continue with other sources instead of failing
                    import traceback
                    traceback.print_exc()
                    error_msg = f"Deep Research encountered an error: {str(dr_error)}"
                    print(error_msg)
                    deep_research_results = error_msg
                    # Continue with analysis using other data sources
                    error_msg = f"Deep Research failed: {str(dr_error)}"
                    print(error_msg)
                    analysis.status = 'failed'
                    analysis.results = {'error': error_msg}
                    analysis.save()
                    return JsonResponse({
                        'id': analysis.id,
                        'status': 'failed',
                        'error': error_msg
                    }, status=500)
            
            # Combine all sources (topics + deep research)
            all_sources = topic_sources + deep_research_sources
            # Remove duplicates based on URL
            seen_urls = set()
            unique_sources = []
            for source in all_sources:
                if source['url'] not in seen_urls:
                    seen_urls.add(source['url'])
                    unique_sources.append(source)
            
            # Generate final analysis with all context including deep research
            results = generate_analysis(
                organization, 
                query, 
                questionnaire_answers, 
                news_context,
                deep_research_results,  # Pass deep research results
                deep_research_images,   # Pass images
                unique_sources          # Pass all sources
            )

            analysis.results = results
            analysis.status = 'completed'
            analysis.completed_at = timezone.now()
            analysis.save()

            return JsonResponse({
                'id': analysis.id,
                'status': 'completed',
                'query': analysis.query,
                'results': results,
                'research_type': analysis.research_type,
                'deep_research_included': bool(deep_research_results),
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
                'error': f'Analysis generation failed: {str(e)}'
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
