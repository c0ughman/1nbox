from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from _1nbox_ai.models import User, Topic, Organization, Summary
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

from firebase_admin import auth
from functools import wraps
from django.http import JsonResponse

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
        except Exception as e:
            return JsonResponse({'error': 'Invalid token'}, status=401)
            
    return wrapped_view

@csrf_exempt
@firebase_auth_required
def initial_signup(request):
    try:
        data = json.loads(request.body)
        firebase_user = request.firebase_user  # This comes from the decorator
        
        # First, create an organization with default free plan
        organization = Organization.objects.create(
            name=data.get('organization_name', f"{firebase_user['email']}'s Organization"),
            plan='free',
            status='active'
        )
        
        # Then create the user
        user = User.objects.create(
            email=firebase_user['email'],
            role='admin',  # First user is admin
            organization=organization  # Link to the organization
        )
        
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role,
                'organization': {
                    'id': organization.id,
                    'name': organization.name,
                    'plan': organization.plan
                }
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_clusters(request, id):
    try:
        topic = Topic.objects.filter(id=id).first()
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
        organization_id = data.get('organization_id')
        negative_keywords = data.get('negative_keywords')
        positive_keywords = data.get('positive_keywords')
    
        all_sources = sources + custom_rss

        if not name:
            return JsonResponse({'success': False, 'error': 'Topic name is required.'}, status=400)
    
        try:
            organization = Organization.objects.get(id=organization_id)
            topic = Topic.objects.create(name=name, sources=all_sources, prompt=prompt, organization=organization, positive_keywords=positive_keywords, negative_keywords=negative_keywords)
            
        except Exception as e:
            print(f"OJO - Counldn't create Topic: {e}")
            
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
        user = User.objects.get(id=id)

        summaries_list = []
        for topic in user.organization.topics.all():
            if topic:
                summaries_list.append(topic.summaries.first().final_summary)
            else:
                print("OJO - Missing a Topic here")
        
        user_data = {
            'email': user.email,
            'supabase_user_id': user.id,
            'plan': user.organization.plan,
            'topics': user.organization.topics.values_list('name', flat=True),
            'summaries_list': summaries_list,
        }
        return JsonResponse(user_data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@csrf_exempt
def sign_up(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            print("Full request data:", request_data)
            
            email = request_data.get('email')
            
            print(f"Extracted data: email={email}, user_id={user_id}")
            
            user, created = User.objects.get_or_create(email=email)
            
            if created:
                user.email = email
                user.save()
                print(f"New user created: {user.id}")
                return JsonResponse({'success': True, 'user_id': user.id, 'message': 'User created successfully'}, status=201)
            else:
                if user_id:
                    user.email = email
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






