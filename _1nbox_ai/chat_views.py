import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from firebase_admin import auth
from functools import wraps
from google import generativeai as genai

from .models import User, Topic, ChatConversation, ChatMessage


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


DOCUMENT_TYPE_PROMPTS = {
    'executive_brief': """Generate an executive brief based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Executive Brief
**Date:** {date}

## Key Developments
[3-5 bullet points of the most important developments]

## What This Means
[2-3 paragraphs explaining implications for business leaders]

## Watch List
[3-5 items to monitor going forward]

## Recommended Actions
[2-3 specific, actionable recommendations]""",

    'swot_analysis': """Generate a SWOT analysis based on the following news articles.

FORMAT YOUR RESPONSE AS:

# SWOT Analysis

## Strengths
[Positive factors/advantages evident from the news]

## Weaknesses
[Vulnerabilities or challenges highlighted]

## Opportunities
[Potential opportunities emerging from developments]

## Threats
[Risks or threats to be aware of]

## Strategic Implications
[2-3 paragraphs on what this means strategically]""",

    'risk_assessment': """Generate a risk assessment based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Risk Assessment

## Risk Summary
[Overall risk level: Low/Medium/High/Critical]
[One paragraph summary]

## Identified Risks
[For each significant risk (max 5):
- **Severity:** Low/Medium/High/Critical
- **Likelihood:** Low/Medium/High
- **Description:** What is this risk
- **Mitigation:** Suggested mitigation steps]

## Emerging Concerns
[Items that aren't risks yet but could become ones]

## Recommendations
[Prioritized list of risk management actions]""",

    'competitive_intel': """Generate a competitive intelligence report based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Competitive Intelligence Report

## Market Overview
[Current state of the competitive landscape]

## Competitor Moves
[Key actions and announcements from competitors]

## Market Trends
[Emerging trends affecting competition]

## Opportunities
[Gaps or opportunities identified]

## Recommendations
[Strategic recommendations based on competitive analysis]""",

    'trend_report': """Generate a trend report based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Trend Report

## Emerging Trends
[Key trends identified from the news]

## Trend Analysis
[For each trend:
- Description
- Potential Impact
- Timeline]

## Industry Implications
[What these trends mean for the industry]

## Action Items
[How to prepare for or capitalize on these trends]""",

    'stakeholder_brief': """Generate a stakeholder brief based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Stakeholder Brief

## Executive Summary
[High-level summary for stakeholders]

## Key Updates
[Important developments stakeholders should know]

## Impact Assessment
[How these developments affect stakeholders]

## Next Steps
[Recommended actions and timeline]

## Q&A Preparation
[Anticipated questions and suggested responses]""",

    'action_items': """Generate a list of action items based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Action Items

## Immediate Actions (This Week)
[Urgent items requiring immediate attention]

## Short-term Actions (This Month)
[Important items to address soon]

## Long-term Actions (This Quarter)
[Strategic items to plan for]

## Monitoring Items
[Things to watch but not act on yet]""",

    'market_snapshot': """Generate a market snapshot based on the following news articles.

FORMAT YOUR RESPONSE AS:

# Market Snapshot

## Market Conditions
[Current state of the market]

## Key Metrics
[Important numbers and indicators]

## Notable Events
[Significant market events]

## Sentiment Analysis
[Overall market sentiment: Bullish/Neutral/Bearish]

## Outlook
[Short-term market outlook]"""
}


def get_topic_context(topic):
    latest_summary = topic.summaries.first()
    if not latest_summary:
        return "", []

    articles = []
    if latest_summary.clusters:
        for cluster in latest_summary.clusters:
            for article in cluster.get('articles', []):
                articles.append({
                    'title': article.get('title', ''),
                    'link': article.get('link', ''),
                })

    summary_text = ""
    if latest_summary.final_summary:
        if isinstance(latest_summary.final_summary, dict):
            for item in latest_summary.final_summary.get('summary', []):
                summary_text += f"**{item.get('title', '')}**\n{item.get('content', '')}\n\n"
        elif isinstance(latest_summary.final_summary, list):
            for item in latest_summary.final_summary:
                summary_text += f"**{item.get('title', '')}**\n{item.get('content', '')}\n\n"

    cluster_summaries = latest_summary.cluster_summaries or []

    context = f"Topic: {topic.name}\n\n"
    context += f"Summary:\n{summary_text}\n\n"
    if cluster_summaries:
        context += "Detailed Cluster Summaries:\n"
        for cs in cluster_summaries[:5]:
            context += f"{cs}\n\n"

    return context, articles


def generate_chat_response(topic, user_message, conversation_history, document_type=None):
    # Support both GEMINI_API_KEY and GEMINI_KEY for backwards compatibility
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found in environment variables. Set GEMINI_API_KEY or GEMINI_KEY.")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    context, articles = get_topic_context(topic)

    history_text = ""
    for msg in conversation_history:
        role = "User" if msg.role == "user" else "Assistant"
        history_text += f"{role}: {msg.content}\n\n"

    if document_type and document_type in DOCUMENT_TYPE_PROMPTS:
        prompt = f"""You are Briefed Chat, an AI assistant specialized in analyzing news content.

CONTEXT:
{context}

CONVERSATION HISTORY:
{history_text}

{DOCUMENT_TYPE_PROMPTS[document_type]}

USER REQUEST: {user_message}

Generate the requested document based on the news context provided."""
    else:
        prompt = f"""You are Briefed Chat, an AI assistant specialized in analyzing and discussing news content.

CONTEXT:
{context}

CONVERSATION HISTORY:
{history_text}

INSTRUCTIONS:
1. Answer questions based on the news context provided above
2. Always cite specific articles when making claims
3. If asked about something not covered in the articles, say so clearly
4. Be concise but thorough
5. Highlight connections between different stories when relevant

USER QUESTION: {user_message}

Respond with a helpful, factual answer."""

    response = model.generate_content(prompt)
    return response.text.strip(), articles


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET", "POST"])
def conversations(request):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        if request.method == "GET":
            convos = ChatConversation.objects.filter(user=user)
            data = []
            for convo in convos:
                last_message = convo.messages.last()
                data.append({
                    'id': convo.id,
                    'title': convo.title or 'Untitled',
                    'topic_id': convo.topic_id,
                    'topic_name': convo.topic.name if convo.topic else None,
                    'last_message_at': last_message.created_at if last_message else convo.created_at,
                    'message_count': convo.messages.count(),
                    'created_at': convo.created_at,
                })
            return JsonResponse({'conversations': data})

        elif request.method == "POST":
            data = json.loads(request.body)
            topic_id = data.get('topic_id')
            title = data.get('title', 'New Conversation')

            topic = None
            if topic_id:
                topic = Topic.objects.filter(
                    id=topic_id,
                    organization=user.organization
                ).first()

            conversation = ChatConversation.objects.create(
                user=user,
                topic=topic,
                title=title
            )

            return JsonResponse({
                'id': conversation.id,
                'topic_id': conversation.topic_id,
                'title': conversation.title,
                'created_at': conversation.created_at
            })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in conversations: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET", "DELETE"])
def conversation_detail(request, conversation_id):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        conversation = ChatConversation.objects.filter(
            id=conversation_id,
            user=user
        ).first()

        if not conversation:
            return JsonResponse({'error': 'Conversation not found'}, status=404)

        if request.method == "GET":
            messages = conversation.messages.all()
            return JsonResponse({
                'conversation': {
                    'id': conversation.id,
                    'title': conversation.title,
                    'topic_id': conversation.topic_id,
                    'topic_name': conversation.topic.name if conversation.topic else None,
                },
                'messages': [{
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'document_type': msg.document_type,
                    'metadata': msg.metadata,
                    'created_at': msg.created_at,
                } for msg in messages]
            })

        elif request.method == "DELETE":
            conversation.delete()
            return JsonResponse({'success': True, 'message': 'Conversation deleted'})

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error in conversation_detail: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def send_message(request, conversation_id):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        conversation = ChatConversation.objects.filter(
            id=conversation_id,
            user=user
        ).first()

        if not conversation:
            return JsonResponse({'error': 'Conversation not found'}, status=404)

        data = json.loads(request.body)
        message_content = data.get('message')
        document_type = data.get('document_type')
        topic_id = data.get('topic_id')

        if not message_content:
            return JsonResponse({'error': 'Message is required'}, status=400)

        if topic_id and not conversation.topic:
            topic = Topic.objects.filter(
                id=topic_id,
                organization=user.organization
            ).first()
            if topic:
                conversation.topic = topic
                conversation.save()

        if not conversation.topic:
            return JsonResponse({'error': 'No topic associated with conversation'}, status=400)

        user_message = ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message_content,
            document_type=document_type
        )

        conversation_history = conversation.messages.exclude(id=user_message.id).order_by('created_at')[:10]

        response_content, articles = generate_chat_response(
            conversation.topic,
            message_content,
            list(conversation_history),
            document_type
        )

        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=response_content,
            document_type=document_type,
            metadata={
                'sources': articles[:10],
                'article_count': len(articles),
            }
        )

        if not conversation.title or conversation.title == 'New Conversation':
            conversation.title = message_content[:50] + ('...' if len(message_content) > 50 else '')
            conversation.save()

        return JsonResponse({
            'user_message': {
                'id': user_message.id,
                'role': 'user',
                'content': user_message.content,
                'created_at': user_message.created_at,
            },
            'assistant_message': {
                'id': assistant_message.id,
                'role': 'assistant',
                'content': assistant_message.content,
                'document_type': assistant_message.document_type,
                'metadata': assistant_message.metadata,
                'created_at': assistant_message.created_at,
            }
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in send_message: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET"])
def document_types(request):
    types = [
        {'id': 'executive_brief', 'name': 'Executive Brief', 'description': 'High-level summary for executives'},
        {'id': 'swot_analysis', 'name': 'SWOT Analysis', 'description': 'Strengths, Weaknesses, Opportunities, Threats'},
        {'id': 'risk_assessment', 'name': 'Risk Assessment', 'description': 'Risk identification and mitigation'},
        {'id': 'competitive_intel', 'name': 'Competitive Intel', 'description': 'Competitor analysis'},
        {'id': 'trend_report', 'name': 'Trend Report', 'description': 'Emerging trends analysis'},
        {'id': 'stakeholder_brief', 'name': 'Stakeholder Brief', 'description': 'Stakeholder-focused summary'},
        {'id': 'action_items', 'name': 'Action Items', 'description': 'Recommended actions list'},
        {'id': 'market_snapshot', 'name': 'Market Snapshot', 'description': 'Market conditions overview'},
    ]
    return JsonResponse({'document_types': types})
