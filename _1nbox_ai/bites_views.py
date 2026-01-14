import json
import os
from datetime import datetime, timedelta, time as datetime_time
import pytz
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from firebase_admin import auth
from functools import wraps
from google import generativeai as genai

from .models import User, Topic, BitesSubscription, BitesDigest
from .bubbles import process_feeds_and_cluster


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


def generate_digest_content(topic, frequency='daily'):
    days_back = 1 if frequency == 'daily' else 7

    if not topic.sources:
        return None

    result = process_feeds_and_cluster(
        rss_urls=topic.sources,
        days_back=days_back,
        common_word_threshold=2,
        top_words_to_consider=3,
        merge_threshold=2,
        min_articles=2,
        join_percentage=0.5,
        final_merge_percentage=0.5,
        title_only=False,
        all_words=False
    )

    clusters = result.get('clusters', [])
    if not clusters:
        return None

    total_articles = sum(len(c.get('articles', [])) for c in clusters)

    cluster_text = ""
    for i, cluster in enumerate(clusters[:10]):
        articles = cluster.get('articles', [])
        common_words = cluster.get('common_words', [])
        cluster_text += f"\nCluster {i+1} ({', '.join(common_words[:3])}):\n"
        for article in articles[:5]:
            cluster_text += f"- {article.get('title', 'Untitled')}\n"

    gemini_key = os.environ.get("GEMINI_KEY")
    if not gemini_key:
        raise ValueError("Gemini API key not found")

    genai.configure(api_key=gemini_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    period = "today" if frequency == "daily" else "this week"

    prompt = f"""You are a news digest curator. Summarize the following article clusters into a clear, scannable digest.

TOPIC: {topic.name}
DIGEST TYPE: {frequency}
ARTICLE COUNT: {total_articles}

ARTICLES BY CLUSTER:
{cluster_text}

Generate a digest in this JSON format (output ONLY valid JSON, no markdown):
{{
  "summary": "2-3 sentence overview of what happened {period}",
  "sections": [
    {{
      "category": "Category Name based on common words",
      "headline": "One-line summary of this category's news",
      "summary": "2-3 sentence detailed summary",
      "article_count": 8,
      "sentiment": "positive|neutral|negative|mixed",
      "key_articles": [
        {{
          "title": "Most important article",
          "url": "URL if available",
          "why_important": "One sentence on why this matters"
        }}
      ]
    }}
  ],
  "stats": {{
    "total_articles": {total_articles},
    "categories_covered": 5,
    "top_themes": ["Theme 1", "Theme 2", "Theme 3"]
  }}
}}

GUIDELINES:
- Prioritize signal over noise
- Lead with what matters most
- Be specific, not vague
- Make it scannable"""

    response = model.generate_content(prompt)
    response_text = response.text.strip()

    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        response_text = response_text[start_idx:end_idx + 1]

    try:
        digest_data = json.loads(response_text)
    except json.JSONDecodeError:
        digest_data = {
            "summary": f"Summary of {total_articles} articles from {topic.name}",
            "sections": [],
            "stats": {"total_articles": total_articles}
        }

    return {
        'content': digest_data,
        'article_count': total_articles,
        'clusters': clusters
    }


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET", "POST"])
def subscriptions(request):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        if request.method == "GET":
            subs = BitesSubscription.objects.filter(user=user)
            data = []
            for sub in subs:
                data.append({
                    'id': sub.id,
                    'topic_id': sub.topic_id,
                    'topic_name': sub.topic.name,
                    'frequency': sub.frequency,
                    'delivery_time': str(sub.delivery_time),
                    'timezone': sub.user_timezone,
                    'is_active': sub.is_active,
                    'last_sent_at': sub.last_sent_at,
                    'created_at': sub.created_at,
                })
            return JsonResponse({'subscriptions': data})

        elif request.method == "POST":
            data = json.loads(request.body)
            topic_id = data.get('topic_id')
            frequency = data.get('frequency', 'daily')
            delivery_time_str = data.get('delivery_time', '08:00')
            timezone_str = data.get('timezone', 'UTC')

            if not topic_id:
                return JsonResponse({'error': 'topic_id is required'}, status=400)

            if frequency not in ['daily', 'weekly']:
                return JsonResponse({'error': 'frequency must be daily or weekly'}, status=400)

            topic = Topic.objects.filter(
                id=topic_id,
                organization=user.organization
            ).first()

            if not topic:
                return JsonResponse({'error': 'Topic not found'}, status=404)

            existing = BitesSubscription.objects.filter(user=user, topic=topic).first()
            if existing:
                return JsonResponse({'error': 'Subscription already exists'}, status=400)

            try:
                hour, minute = map(int, delivery_time_str.split(':'))
                delivery_time = datetime_time(hour, minute)
            except (ValueError, AttributeError):
                delivery_time = datetime_time(8, 0)

            subscription = BitesSubscription.objects.create(
                user=user,
                topic=topic,
                frequency=frequency,
                delivery_time=delivery_time,
                timezone=timezone_str,
                is_active=True
            )

            try:
                tz = pytz.timezone(timezone_str)
                now = datetime.now(tz)
                next_delivery = now.replace(
                    hour=delivery_time.hour,
                    minute=delivery_time.minute,
                    second=0,
                    microsecond=0
                )
                if next_delivery <= now:
                    next_delivery += timedelta(days=1)
                next_delivery_str = next_delivery.isoformat()
            except Exception:
                next_delivery_str = None

            return JsonResponse({
                'subscription_id': subscription.id,
                'topic_id': subscription.topic_id,
                'topic_name': topic.name,
                'frequency': subscription.frequency,
                'delivery_time': str(subscription.delivery_time),
                'timezone': subscription.user_timezone,
                'next_delivery': next_delivery_str
            })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in subscriptions: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET", "PUT", "DELETE"])
def subscription_detail(request, subscription_id):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        subscription = BitesSubscription.objects.filter(
            id=subscription_id,
            user=user
        ).first()

        if not subscription:
            return JsonResponse({'error': 'Subscription not found'}, status=404)

        if request.method == "GET":
            return JsonResponse({
                'id': subscription.id,
                'topic_id': subscription.topic_id,
                'topic_name': subscription.topic.name,
                'frequency': subscription.frequency,
                'delivery_time': str(subscription.delivery_time),
                'timezone': subscription.user_timezone,
                'is_active': subscription.is_active,
                'last_sent_at': subscription.last_sent_at,
                'created_at': subscription.created_at,
            })

        elif request.method == "PUT":
            data = json.loads(request.body)

            if 'frequency' in data:
                if data['frequency'] in ['daily', 'weekly']:
                    subscription.frequency = data['frequency']

            if 'delivery_time' in data:
                try:
                    hour, minute = map(int, data['delivery_time'].split(':'))
                    subscription.delivery_time = datetime_time(hour, minute)
                except (ValueError, AttributeError):
                    pass

            if 'timezone' in data:
                subscription.user_timezone = data['timezone']

            if 'is_active' in data:
                subscription.is_active = bool(data['is_active'])

            subscription.save()

            return JsonResponse({
                'success': True,
                'id': subscription.id,
                'frequency': subscription.frequency,
                'delivery_time': str(subscription.delivery_time),
                'timezone': subscription.user_timezone,
                'is_active': subscription.is_active,
            })

        elif request.method == "DELETE":
            subscription.delete()
            return JsonResponse({'success': True, 'message': 'Subscription deleted'})

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error in subscription_detail: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["GET"])
def preview_digest(request, topic_id):
    try:
        firebase_user = request.firebase_user
        email = firebase_user['email']
        user = User.objects.get(email=email)

        topic = Topic.objects.filter(
            id=topic_id,
            organization=user.organization
        ).first()

        if not topic:
            return JsonResponse({'error': 'Topic not found'}, status=404)

        frequency = request.GET.get('frequency', 'daily')
        if frequency not in ['daily', 'weekly']:
            frequency = 'daily'

        today = datetime.now().date()
        existing_digest = BitesDigest.objects.filter(
            topic=topic,
            digest_type=frequency,
            digest_date=today
        ).first()

        if existing_digest:
            return JsonResponse({
                'topic_name': topic.name,
                'digest_type': frequency,
                'date': str(today),
                'cached': True,
                **existing_digest.content
            })

        result = generate_digest_content(topic, frequency)

        if not result:
            return JsonResponse({
                'topic_name': topic.name,
                'digest_type': frequency,
                'date': str(today),
                'summary': 'No articles found for this period',
                'sections': [],
                'stats': {'total_articles': 0}
            })

        BitesDigest.objects.update_or_create(
            topic=topic,
            digest_type=frequency,
            digest_date=today,
            defaults={
                'content': result['content'],
                'article_count': result['article_count']
            }
        )

        return JsonResponse({
            'topic_name': topic.name,
            'digest_type': frequency,
            'date': str(today),
            'cached': False,
            **result['content']
        })

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        print(f"Error in preview_digest: {str(e)}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)
