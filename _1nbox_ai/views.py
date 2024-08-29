from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from _1nbox_ai.models import User, Topic
from django.http import HttpResponse
from django.shortcuts import render, redirect
from _1nbox_ai.answer import generate_answer
from django.views.decorators.http import require_POST, require_http_methods
import jwt
import os
import sys
from django.http import JsonResponse
from django.conf import settings
import stripe
import requests
import time

@csrf_exempt
@require_http_methods(["POST"])
def create_topic(request):
    print(request.body)
    try:
        data = json.loads(request.body)
        name = data.get('name')
        sources = data.get('sources')
        prompt = data.get('customPrompt')
        custom_rss = data.get('customRss')
        user_id = data.get('user_id')
    
        all_sources = sources + custom_rss
        try:
            user = User.objects.get(supabase_user_id=user_id)
            
            # Ensure user.topics is a list
            if not isinstance(user.topics, list):
                user.topics = []
            
            user.topics.append(name)
            user.save()
        except Exception as e:
            print(f"OJO - Counldn't save the topic for the user: {e}")

        if not name:
            return JsonResponse({'success': False, 'error': 'Topic name is required.'}, status=400)
        topic = Topic.objects.create(name=name, sources=all_sources, prompt=prompt, created_by=user_id, custom=True)
        return JsonResponse({'success': True, 'id': topic.id})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Update the view function
@csrf_exempt
def message_received(request):
    if request.method == 'POST':
        topic = request.POST.get('topic', '')
        body = request.POST.get('body', '')
        context = json.loads(request.POST.get('context', '[]'))
        try:
            answer = generate_answer(topic, body, context)
            return HttpResponse(answer, status=200)
        except Exception as e:
            print(f"A problem occurred: {e}")
            return HttpResponse(f"A problem occurred: {e}", status=500)
    else:
        return HttpResponse("Only POST requests are allowed.", status=405)

@csrf_exempt
@require_http_methods(["GET"])
def get_user_data(request, supabase_user_id):
    try:
        user = User.objects.get(supabase_user_id=supabase_user_id)

        summaries_list = []
        for topic in user.topics:
            chosenTopic = Topic.objects.filter(name=topic).first()
            if chosenTopic:
                summaries_list.append(chosenTopic.summary)
            else:
                print("OJO!!! - Missing a Topic here")
        
        user_data = {
            'email': user.email,
            'phone_number': user.phone_number,
            'supabase_user_id': user.supabase_user_id,
            'plan': user.plan,
            'negative_keywords': user.negative_keywords,
            'positive_keywords': user.positive_keywords,
            'language': user.language,
            'time_zone': user.time_zone,
            'messaging_app': user.messaging_app,
            'topics': user.topics,
            'days_since': user.days_since,
            'summaries_list': summaries_list,
        }
        return JsonResponse(user_data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

@csrf_exempt
@require_http_methods(["GET"])
def get_summaries(request):
    try:
        # Get the 'topics' query parameter from the URL
        topics = request.GET.get('topics', '')
        
        # Split the topics string into a list
        topic_names = topics.split(',')
    
        # Initialize an empty dictionary to store summaries
        summaries_dict = {}
    
        # Iterate through all Topic objects and check if they match any of the requested topics
        for topic in Topic.objects.all():
            if topic.name in topic_names:
                summaries_dict[topic.name] = topic.summary
    
        # Return the summaries as a JSON response
        return JsonResponse(summaries_dict)

    except json.JSONDecodeError:
        # Handle JSON decoding errors
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@csrf_exempt
def update_user_data(request):
    try:
        # Parse the JSON data from the request body
        data = json.loads(request.body.decode('utf-8'))
        
        # Get the user ID from the request data
        supabase_user_id = data.get('supabase_user_id')
        if not supabase_user_id:
            return JsonResponse({'error': 'supabase_user_id is required'}, status=400)
        
        # Retrieve the user instance by user ID
        user = User.objects.get(supabase_user_id=supabase_user_id)
        
        # Update user fields if present in the request data
        if 'email' in data:
            user.email = data['email']
        if 'phone_number' in data:
            user.phone_number = data['phone_number']
        if 'plan' in data:
            user.plan = data['plan']
        if 'negative_keywords' in data:
            user.negative_keywords = data['negative_keywords']
        if 'positive_keywords' in data:
            user.positive_keywords = data['positive_keywords']
        if 'language' in data:
            user.language = data['language']
        if 'time_zone' in data:
            user.time_zone = data['time_zone']
        if 'messaging_app' in data:
            user.messaging_app = data['messaging_app']
            
        if 'topics' in data:
            topics = data['topics']
            topics = [item for item in topics if item]
            user.topics = topics
            
        if 'days_since' in data:
            user.days_since = data['days_since']
        
        # Save the updated user instance
        user.save()
        
        # Return a success message
        return JsonResponse({'message': 'User data updated successfully'})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


@csrf_exempt
def sign_up(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            print("Full request data:", request_data)
            
            email = request_data.get('email')
            messaging_app = request_data.get('messaging_app')
            topics = request_data.get('topics')
            phone_number = request_data.get('phone_number')
            user_id = request_data.get('user_id')
            
            print(f"Extracted data: email={email}, app={messaging_app}, topics={topics}, phone={phone_number}, user_id={user_id}")
            
            user, created = User.objects.get_or_create(email=email)
            
            if created:
                user.topics = topics
                user.messaging_app = messaging_app
                user.phone_number = phone_number
                user.supabase_user_id = user_id
                user.days_since = int(time.time())
                user.save()
                print(f"New user created: {user.id}")
                return JsonResponse({'success': True, 'user_id': user.id, 'message': 'User created successfully'}, status=201)
            else:
                user.messaging_app = messaging_app
                user.topics = topics
                if phone_number:
                    user.phone_number = phone_number
                if user_id:
                    user.supabase_user_id = user_id
                user.save()
                print(f"Existing user updated: {user.id}")
                return JsonResponse({'success': True, 'user_id': user.id, 'message': 'User updated successfully'}, status=200)
        
        except Exception as e:
            print(f"Error processing request: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)
        
@csrf_exempt
def create_checkout_session(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if data.get('user_email'):
            user_email = data.get('user_email')  
        else:
            user = User.objects.filter(supabase_user_id=user_id).first()
            user_email = user.email  
        
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

        # Create a new customer with metadata
        customer = stripe.Customer.create(
            email=user_email,
            metadata={'user_id': user_id}
        )

        # Get the discount code from the request if available
        discount_code = data.get('discount_code')

        # Initialize the discount ID to None
        promotion_code = None

        # Map the discount code to the promotion code ID
        if discount_code == 'MISSME':
            promotion_code = 'promo_1PoSWZCHpOkAgMGGYb4LJ8fm'

        # Create the checkout session, including the discount if available
        checkout_session_params = {
            'customer': customer.id,
            'client_reference_id': user_id,
            'payment_method_types': ['card'],
            'line_items': [{
                'price': 'price_1PYv2KCHpOkAgMGGyv0S3LW8',  # Basic price ID
                'quantity': 1,
            }],
            'mode': 'subscription',
            'success_url': 'https://www.1nbox-ai.com/home?session_id={CHECKOUT_SESSION_ID}',
            'cancel_url': 'https://www.1nbox-ai.com/pricing',
        }

        # Add the promotion code if it exists
        if promotion_code:
            checkout_session_params['discounts'] = [{
                'promotion_code': promotion_code,
            }]

        # Create the checkout session with the parameters
        checkout_session = stripe.checkout.Session.create(**checkout_session_params)

        return JsonResponse({'checkoutUrl': checkout_session.url})
    except Exception as e:
        return JsonResponse({'error': str(e)})

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, "whsec_3qSD5i1N7n7XKePc6dYayY939tr9M4h4"
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
    
    print("EVENT TYPE: " + event['type']) 

    if event['type'] == 'customer.subscription.updated':
        session = event['data']['object']
        handle_subscription_event(session, deleted=False)

    if event['type'] == 'customer.subscription.deleted':
        session = event['data']['object']
        handle_subscription_event(session, deleted=True)
    
    return HttpResponse(status=200)

def handle_subscription_event(subscription, deleted): 

    customer_id = subscription.get('customer')
    print(f"Customer ID: {customer_id}")
    
    try:
        customer = stripe.Customer.retrieve(customer_id)
        user_id = customer.metadata.get('user_id')
        print(f"User ID from metadata: {user_id}")
        
        if user_id:
            matching_users = User.objects.filter(supabase_user_id=user_id)
            
            if matching_users.exists():
                if matching_users.count() > 1:
                    print(f"Warning: Multiple users found with ID {user_id}")
                # Update all matching users
                for user in matching_users:

                    if deleted == True:
                        user.plan = "no plan"  # Set the plan to "no plan"
                        print("UPDATED TO: no plan")

                    else:
                        if subscription['items']['data'][0]['price']['id'] == 'price_1PYv2KCHpOkAgMGGyv0S3LW8':
                            user.plan = "basic"  # Set the plan to "basic"
                            print("UPDATED TO: basic")
                        elif subscription['items']['data'][0]['price']['id'] == 'price_1PYv2VCHpOkAgMGGwiAyZpN3':
                            user.plan = "pro"  # Set the plan to "pro"
                            print("UPDATED TO: pro")

                        else:
                            print("SOMETHING WRONG WITH PLAN PRICE ID BROTHER")

                    user.save()
                    update_supabase_plan(user)

                    print(f"Updated subscription for user {user.email}")
            else:
                print(f"No user found with ID {user_id}")
        else:
            print("User ID not found in customer metadata")
    except stripe.error.StripeError as e:
        print(f"Error retrieving customer: {str(e)}")


# OLD 1NBOX RIP






