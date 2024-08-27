from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from _1nbox_ai.models import User, Topic
from django.http import HttpResponse
from django.shortcuts import render, redirect
from _1nbox_ai.workflow import main
from _1nbox_ai.answer import generate_answer
from django.views.decorators.http import require_POST, require_http_methods
import jwt
import os
import sys
from django.http import JsonResponse
from django.conf import settings
import stripe
import requests
from supabase import create_client, Client
import time



supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

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
def new_lead(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            print("Full request data:", request_data)
            email = request_data.get('email')
            messaging_app = request_data.get('messaging_app')
            topics = [topic.replace("\n", "") for topic in request_data.get('topics', [])]

            print(f"Extracted data: email={email}, app={messaging_app}, topics={topics}")
            
            try:
                new_user = User.objects.create(email=email, topics=topics, messaging_app=messaging_app, days_since=int(time.time()))
                print(f"User created: {new_user.id}")
                return JsonResponse({'success': True, 'user_id': new_user.id}, status=200)
            except Exception as e:
                print(f"Error creating user: {str(e)}")
                return JsonResponse({'error': str(e)}, status=500)
        except Exception as e:
            print(f"Error processing request: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

            
@csrf_exempt
def new_user(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            print(request_data)
            email = request_data.get('email')
            phone_number = request_data.get('phone_number')
            user_id = request_data.get('user_id')
            
            user = User.objects.filter(email=email).first()
            if user:
                user.phone_number = phone_number
                user.supabase_user_id = user_id
                user.save()
                return JsonResponse({'good': "User updated successfully"}, status=200)
            else:
                return JsonResponse({'error': "User does not exist with this email"}, status=404)
        except Exception as e:
            print(f"Error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

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
def get_user_data_by_email(request, email):
    try:
        user = User.objects.get(email=email)

        summaries_list = []
        for topic in user.topics:
            chosen_topic = Topic.objects.filter(name=topic).first()
            if chosen_topic:
                summaries_list.append(chosen_topic.summary)
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
def get_user_data_by_phone(request, phone_number):
    try:
        user = User.objects.get(phone_number=phone_number)

        summaries_list = []
        for topic in user.topics:
            chosen_topic = Topic.objects.filter(name=topic).first()
            if chosen_topic:
                summaries_list.append(chosen_topic.summary)
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
            user.topics = data['topics']
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

# OLD 1NBOX TERRTORY
    
@csrf_exempt
def new_settings(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            print(request_data)
            user_id = request_data.get('record', {}).get('user_id')
            print(user_id)
            phone_number = request_data.get('record', {}).get('phone_number')
            frequency = request_data.get('record', {}).get('frequency')
            weekday = request_data.get('record', {}).get('weekday')
            plan = request_data.get('record', {}).get('plan')
            t = request_data.get('record', {}).get('time')
            t2 = request_data.get('record', {}).get('time2')
            t3 = request_data.get('record', {}).get('time3')
            t4 = request_data.get('record', {}).get('time4')
            t5 = request_data.get('record', {}).get('time5')
            style = request_data.get('record', {}).get('style')
            time_zone = request_data.get('record', {}).get('time_zone')
            language = request_data.get('record', {}).get('language')
            # Try to get the user with the given ID
            user = User.objects.filter(supabase_user_id=user_id).first()
            if user:
                # Update the fields
                user.phone_number = phone_number
                user.style = style
                user.frequency = frequency
                user.language = language
                user.time_zone = time_zone
                user.plan = plan

                # MAKE WEEKDAY USABLE
                weekdays_list = weekday.split(',') if weekday else ['Friday']
                
                # Define the mapping of weekdays to numbers
                weekdays_mapping = {
                    'monday': 0,
                    'tuesday': 1,
                    'wednesday': 2,
                    'thursday': 3,
                    'friday': 4,
                    'saturday': 5,
                    'sunday': 6
                }
                                
                # Convert the list of weekday names to their corresponding numbers
                numbers_list = [weekdays_mapping.get(day.strip().lower(), 4) for day in weekdays_list if day.strip()]

                user.weekday = str(numbers_list)
                user.t = t
                user.t2 = t2
                user.t3 = t3
                user.t4 = t4
                user.t5 = t5
                user.save()
                print("exists new_settings")
            else:
                # Create a new user
                new_user = User.objects.create(supabase_user_id=user_id, phone_number=phone_number, style=style, frequency=frequency, t=t)
                print("does not exist new_settings")
                
            return JsonResponse({'good': "Everything's good"}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            print(str(e))
            sys.stdout.flush()

    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

@csrf_exempt
def new_keywords(request):
    if request.method == 'POST':
        request_data = json.loads(request.body.decode('utf-8'))
        print(request_data)
        user_id = request_data.get('record', {}).get('user_id')
        print(user_id)
        positive = request_data.get('record', {}).get('positive')
        negative = request_data.get('record', {}).get('negative')

        # Try to get the user with the given ID
        user = User.objects.filter(supabase_user_id=user_id).first()

        if user:
            # Update the fields
            user.positive_keywords = positive
            user.negative_keywords = negative
            user.save()
            print("exists new_keywords")
        else:
            # Create a new user
            User.objects.create(supabase_user_id=user_id, positive_keywords=positive, negative_keywords=negative)
            print("does not exist new_keywords")

        return JsonResponse({'good': "Everything's good"}, status=200)

    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

@csrf_exempt
def process_tokens(request):
    if request.method == 'POST':
        try:
            # Assuming the request body contains JSON data
            data = json.loads(request.body.decode('utf-8'))

            # Accessing JSON parameters
            access_token = data.get('access_token')
            provider_token = data.get('provider_token')
            refresh_token = data.get('refresh_token')
            provider_refresh_token = data.get('provider_refresh_token')

            # Process the tokens as needed (store in the database, etc.)
            # You may want to add more validation and error handling here

            print(access_token)
            print(refresh_token)
            print(provider_token)
            print(provider_refresh_token)

            # Work here refers to whiteboard
            new_tokens(access_token, provider_token, refresh_token, provider_refresh_token)

            return JsonResponse({'status': 'Tokens processed successfully'})

        except json.JSONDecodeError as e:
            # Handle JSON decoding error
            return JsonResponse({'status': 'Error decoding JSON', 'error': str(e)}, status=400)

    return JsonResponse({'status': 'Invalid request'})

def new_tokens(access_token, provider_token, refresh_token, provider_refresh_token):

    decoded = jwt.decode(access_token, options={"verify_signature": False})
    email = decoded['email']
    user_id = decoded['sub']

    user = User.objects.filter(supabase_user_id=user_id).first()

    if user:
        # Update the fields
        user.supabase_user_id = user_id
        user.email = email
        user.access_token = access_token
        user.provider_token = provider_token
        user.refresh_token = refresh_token
        user.provider_refresh_token = provider_refresh_token
        user.save()
        print("exists new_tokens")

    else:
        # Create a new user
        User.objects.create(email = email, supabase_user_id = user_id, access_token=access_token, provider_token=provider_token, refresh_token=refresh_token, provider_refresh_token = provider_refresh_token)
        print("does not exist new_tokens")

    print("User created or updated with tokens")

def oauth_redirect(request):
    return render(request, 'redirect.html') 

def workflow(request):

    user = User.objects.get(supabase_user_id="39de099d-3064-4b34-926b-12324eebcd97")

    return HttpResponse (main(user))


    # TOKEN REFRESHING !!!

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
def create_checkout_session_pro(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        user_email = data.get('user_email')  # Make sure to send this from the frontend

        stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

        # Create a new customer with metadata
        customer = stripe.Customer.create(
            email=user_email,
            metadata={'user_id': user_id}
        )

        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            client_reference_id=user_id,
            payment_method_types=['card'],
            line_items=[{
                'price': 'price_1PYv2VCHpOkAgMGGwiAyZpN3', #pro price ID
                'quantity': 1,
            }],
            mode='subscription',
            success_url='https://www.1nbox-ai.com/home?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://www.1nbox-ai.com/pricing',
        )
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

def update_supabase_plan(user):

    user_id = user.supabase_user_id
    access_token = user.access_token
    refresh_token = user.refresh_token

    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    supabase: Client = create_client(supabase_url, supabase_key)

    try:
        # Attempt to set the session with the current tokens
        supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        print(f"Error setting session: {e}")
        # Attempt to refresh the tokens if the session setting fails
        try:
            response = requests.post(
                f"{supabase_url}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": supabase_key, "Content-Type": "application/json"},
                json={"refresh_token": refresh_token}
            )
            response_data = response.json()
            if response.status_code == 200:
                # Update the user's tokens
                access_token = response_data['access_token']
                refresh_token = response_data['refresh_token']
                user.access_token = access_token
                user.refresh_token = refresh_token
                user.save()  # Save the updated tokens to the database
                # Set the session with the new tokens
                supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            else:
                print(f"Error refreshing token: {response_data}")
                return
        except Exception as refresh_error:
            print(f"Error refreshing token: {refresh_error}")
            return

    # Insert the plan into the Settings table
    try:
        data, count = supabase.table('Settings').update({"plan": user.plan}).eq("user_id", user_id).execute()
        print(data)
        print(count)
    except Exception as insert_error:
        print(f"Error inserting summary: {insert_error}")
