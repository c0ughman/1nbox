from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from _1nbox_ai.models import User, ScheduledTask
from django.http import HttpResponse
from django.shortcuts import render, redirect
from _1nbox_ai.workflow import main
import jwt
import os

supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

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
            t = request_data.get('record', {}).get('time')
            style = request_data.get('record', {}).get('style')
            # Try to get the user with the given ID
            user = User.objects.filter(supabase_user_id=user_id).first()
            if user:
                # Update the fields
                user.phone_number = phone_number
                user.style = style
                user.frequency = frequency
                user.t = t
                user.save()
                print("exists new_settings")
                new_scheduler(user)
            else:
                # Create a new user
                new_user = User.objects.create(supabase_user_id=user_id, phone_number=phone_number, style=style, frequency=frequency, t=t)
                # Create a new scheduler
                print("does not exist new_settings")
                new_scheduler(new_user)


            return JsonResponse({'good': "Everything's good"}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

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

def new_scheduler(user):
    scheduled_task = ScheduledTask.objects.filter(user=user).first()
    if scheduled_task:
        scheduled_task.t = user.t
        scheduled_task.frequency = user.frequency
        scheduled_task.save()
        print("exists new_scheduler")
    else:
        ScheduledTask.objects.create(user=user, t=user.t, frequency=user.frequency)
        print("does not exist new_scheduler")

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