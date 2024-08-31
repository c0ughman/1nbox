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
@require_http_methods(["GET"])
def get_clusters(request, name):
    try:
        topic = Topic.objects.filter(name=name).first()
        if topic:
            return JsonResponse(topic.clusters, safe=False)
        else:
            return JsonResponse({'error': 'Topic not found'}, status=404)
    except Topic.DoesNotExist:
        return JsonResponse({'error': 'Topic not found'}, status=404)

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
            'supabase_user_id': user.supabase_user_id,
            'plan': user.plan,
            'negative_keywords': user.negative_keywords,
            'positive_keywords': user.positive_keywords,
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
        if 'plan' in data:
            user.plan = data['plan']
        if 'negative_keywords' in data:
            user.negative_keywords = data['negative_keywords']
        if 'positive_keywords' in data:
            user.positive_keywords = data['positive_keywords']
            
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
            topics = request_data.get('topics')
            user_id = request_data.get('user_id')
            
            print(f"Extracted data: email={email}, topics={topics}, user_id={user_id}")
            
            user, created = User.objects.get_or_create(email=email)
            
            if created:
                user.topics = topics
                user.supabase_user_id = user_id
                user.days_since = int(time.time())
                user.save()
                print(f"New user created: {user.id}")
                return JsonResponse({'success': True, 'user_id': user.id, 'message': 'User created successfully'}, status=201)
            else:
                user.topics = topics
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
                        user.plan = "inactive"  # Set the plan to "no plan"
                        print("UPDATED TO: inactive")

                    else:
                        if subscription['items']['data'][0]['price']['id'] == 'price_1PYv2KCHpOkAgMGGyv0S3LW8':
                            user.plan = "paid"  # Set the plan to "basic"
                            print("UPDATED TO: paid")
                        elif subscription['items']['data'][0]['price']['id'] == 'price_1PYv2VCHpOkAgMGGwiAyZpN3':
                            user.plan = "paid"  # Set the plan to "pro"
                            print("UPDATED TO: paid")

                        else:
                            print("SOMETHING WRONG WITH PLAN PRICE ID BROTHER")

                    user.save()

                    print(f"Updated subscription for user {user.email}")
            else:
                print(f"No user found with ID {user_id}")
        else:
            print("User ID not found in customer metadata")
    except stripe.error.StripeError as e:
        print(f"Error retrieving customer: {str(e)}")


import stripe
import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import User  # Adjust this import based on your project structure

@csrf_exempt
@require_http_methods(["POST"])
def cancel_subscription(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')

        # Retrieve the user
        user = User.objects.filter(supabase_user_id=user_id).first()
        if not user:
            return JsonResponse({'error': 'User not found'}, status=404)

        # Set up Stripe API key
        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

        # Find the Stripe customer using the user's email
        customers = stripe.Customer.list(email=user.email)
        if not customers.data:
            return JsonResponse({'error': 'No Stripe customer found for this user'}, status=404)
        
        customer = customers.data[0]

        # Retrieve the customer's subscriptions
        subscriptions = stripe.Subscription.list(customer=customer.id)

        if not subscriptions.data:
            return JsonResponse({'error': 'No active subscription found'}, status=400)

        # Cancel the subscription
        for subscription in subscriptions.data:
            canceled_subscription = stripe.Subscription.delete(subscription.id)

        # Update user's plan in your database
        user.plan = "inactive"
        user.save()

        return JsonResponse({'message': 'Subscription canceled successfully'})

    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# OLD 1NBOX RIP






