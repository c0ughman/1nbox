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

from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

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
def get_user_organization_data(request):
    try:
        # Get Firebase user email from the token
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Fetch current user and related data with select_related and prefetch_related
        current_user = User.objects.select_related('organization').prefetch_related(
            'organization__topics',
            'organization__topics__summaries'
        ).get(email=email)
        
        # Fetch all users in the same organization
        organization_users = User.objects.filter(
            organization=current_user.organization
        ).select_related('organization')
        
        # Build users data
        users_data = [{
            'id': org_user.id,
            'email': org_user.email,
            'role': org_user.role,
            'joined_at': org_user.joined_at,
        } for org_user in organization_users]
        
        # Build topics data with their latest summaries
        topics_data = []
        for topic in current_user.organization.topics.all():
            latest_summary = topic.summaries.first()  # Gets the latest summary due to Meta ordering
            topic_data = {
                'id': topic.id,
                'name': topic.name,
                'sources': topic.sources,
                'prompt': topic.prompt,
                'negative_keywords': topic.negative_keywords,
                'positive_keywords': topic.positive_keywords,
                'created_at': topic.created_at,
            }
            
            if latest_summary:
                topic_data['latest_summary'] = {
                    'id': latest_summary.id,
                    'clusters': latest_summary.clusters,
                    'cluster_summaries': latest_summary.cluster_summaries,
                    'final_summary': latest_summary.final_summary,
                    'questions': latest_summary.questions,
                    'number_of_articles': latest_summary.number_of_articles,
                    'created_at': latest_summary.created_at,
                }
            else:
                topic_data['latest_summary'] = None
            
            topics_data.append(topic_data)
        
        # Build the response
        response_data = {
            'user': {
                'id': current_user.id,
                'email': current_user.email,
                'role': current_user.role,
                'joined_at': current_user.joined_at,
            },
            'users': users_data,  # Added all users in the organization
            'organization': {
                'id': current_user.organization.id,
                'name': current_user.organization.name,
                'plan': current_user.organization.plan,
                'status': current_user.organization.status,
                'created_at': current_user.organization.created_at,
            },
            'topics': topics_data
        }
        
        return JsonResponse(response_data)
    
    except User.DoesNotExist:
        return JsonResponse({
            'error': 'User not found in database'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)


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

@firebase_auth_required
def get_user_data(request):
    try:
        # Get Firebase user email from the token
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Fetch user and related organization from your database
        user = User.objects.select_related('organization').get(email=email)
        
        return JsonResponse({
            'email': user.email,
            'organization': {
                'name': user.organization.name,
                'plan': user.organization.plan
            }
        })
    except User.DoesNotExist:
        return JsonResponse({
            'error': 'User not found in database'
        }, status=404)
    except Exception as e:
        return JsonResponse({
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

# TOPIC MANAGEMENT

@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def create_topic(request):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Check if user exists and is admin
        try:
            user = User.objects.get(email=email)
            if user.role != 'admin':
                return JsonResponse({
                    'success': False, 
                    'error': 'Only admin users can create topics'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Proceed with existing topic creation logic
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
            topic = Topic.objects.create(
                name=name, 
                sources=all_sources, 
                prompt=prompt, 
                organization=organization, 
                positive_keywords=positive_keywords, 
                negative_keywords=negative_keywords
            )
            
        except Exception as e:
            print(f"OJO - Couldn't create Topic: {e}")
            
        return JsonResponse({'success': True, 'id': topic.id})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@firebase_auth_required
@require_http_methods(["PUT", "PATCH"])
def update_topic(request, topic_id):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Check if user exists and is admin
        try:
            user = User.objects.get(email=email)
            if user.role != 'admin':
                return JsonResponse({
                    'success': False, 
                    'error': 'Only admin users can update topics'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Parse request data
        data = json.loads(request.body)
        name = data.get('name')
        sources = data.get('sources', [])
        custom_rss = data.get('customRss', [])
        prompt = data.get('customPrompt')
        organization_id = data.get('organization_id')
        negative_keywords = data.get('negative_keywords')
        positive_keywords = data.get('positive_keywords')
        
        # Get the topic and verify it belongs to the user's organization
        try:
            topic = Topic.objects.get(
                id=topic_id, 
                organization_id=organization_id,
                organization=user.organization  # Extra check to ensure topic belongs to user's org
            )
        except Topic.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Topic not found or access denied'
            }, status=404)

        # Update the topic fields
        if name:
            topic.name = name
        
        if sources is not None or custom_rss is not None:
            all_sources = sources + custom_rss
            topic.sources = all_sources
            
        if prompt is not None:
            topic.prompt = prompt
            
        if negative_keywords is not None:
            topic.negative_keywords = negative_keywords
            
        if positive_keywords is not None:
            topic.positive_keywords = positive_keywords

        # Save the changes
        topic.save()

        return JsonResponse({
            'success': True,
            'id': topic.id,
            'message': 'Topic updated successfully'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["DELETE"])
def delete_topic(request, topic_id):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Check if user exists and is admin
        try:
            user = User.objects.get(email=email)
            if user.role != 'admin':
                return JsonResponse({
                    'success': False, 
                    'error': 'Only admin users can delete topics'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Get the topic and verify it belongs to the user's organization
        try:
            topic = Topic.objects.get(
                id=topic_id,
                organization=user.organization  # Ensures topic belongs to user's org
            )
        except Topic.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Topic not found or access denied'
            }, status=404)

        # Delete the topic
        topic.delete()

        return JsonResponse({
            'success': True,
            'message': 'Topic deleted successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



# TEAM MANAGEMENT

@csrf_exempt
@firebase_auth_required
@require_http_methods(["PUT", "PATCH"])
def update_team_member(request, user_id):
    print("Started updating team member")
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Check if current user exists and is admin
        try:
            current_user = User.objects.get(email=email)
            if current_user.role != 'admin':
                return JsonResponse({
                    'success': False, 
                    'error': 'Only admin users can update team members'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Parse request data
        data = json.loads(request.body)
        new_email = data.get('email')
        new_role = data.get('role')
        
        # Validate role if provided
        if new_role and new_role not in ['admin', 'member']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid role. Must be either "admin" or "member"'
            }, status=400)

        # Get the team member to update and verify they belong to the same organization
        try:
            team_member = User.objects.get(
                id=user_id,
                organization=current_user.organization  # Ensures user belongs to same org
            )
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Team member not found or access denied'
            }, status=404)

        # Prevent self-role modification
        if team_member.id == current_user.id and new_role and new_role != current_user.role:
            return JsonResponse({
                'success': False,
                'error': 'Cannot modify your own role'
            }, status=403)

        # Update the user fields
        if new_email:
            # Check if email already exists
            if User.objects.filter(email=new_email).exclude(id=user_id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Email already exists'
                }, status=400)
            team_member.email = new_email
            
        if new_role:
            team_member.role = new_role

        # Save the changes
        team_member.save()

        return JsonResponse({
            'success': True,
            'id': team_member.id,
            'message': 'Team member updated successfully'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["DELETE"])
def delete_team_member(request, user_id):
    print("Started deleting team member")
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Check if current user exists and is admin
        try:
            current_user = User.objects.get(email=email)
            if current_user.role != 'admin':
                return JsonResponse({
                    'success': False, 
                    'error': 'Only admin users can delete team members'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Prevent self-deletion
        if str(user_id) == str(current_user.id):
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete your own account'
            }, status=403)

        # Get the team member to delete and verify they belong to the same organization
        try:
            team_member = User.objects.get(
                id=user_id,
                organization=current_user.organization  # Ensures user belongs to same org
            )
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Team member not found or access denied'
            }, status=404)

        try:
            # First try to delete the user from Firebase
            user_to_delete = auth.get_user_by_email(team_member.email)
            auth.delete_user(user_to_delete.uid)
            print(f"Successfully deleted user {team_member.email} from Firebase")
        except auth.UserNotFoundError:
            print(f"User {team_member.email} not found in Firebase - continuing with database deletion")
        except Exception as e:
            print(f"Error deleting user from Firebase: {str(e)}")
            # Optionally, you could choose to return an error here
            # For now, we'll continue with the database deletion

        # Delete the team member from your database
        team_member.delete()

        return JsonResponse({
            'success': True,
            'message': 'Team member deleted successfully from database and Firebase'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def check_pending_invitation(request, organization_id):
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)

        # Check for pending user
        pending_user = User.objects.filter(
            email=email,
            organization_id=organization_id,
            state='pending'
        ).exists()
        
        return JsonResponse({
            'success': True,
            'has_pending_invitation': pending_user
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def join_team_member(request, organization_id):
    try:
        # Get Firebase user email from the token
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        if not email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)

        # Look for pending user in the organization
        try:
            user = User.objects.get(
                email=email,
                organization_id=organization_id,
                state='pending'
            )
            
            # Update user status to active
            user.state = 'active'
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Successfully joined organization',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'organization': {
                        'id': user.organization.id,
                        'name': user.organization.name,
                        'plan': user.organization.plan
                    }
                }
            })

        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'No pending invitation found for this email'
            }, status=404)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def send_email(email, organization_name, organization_id):
    """
    Send an invitation email using SendGrid.
    """
    sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
    
    context = {
        'organization_name': organization_name,
        'join_url': f"https://1nbox.netlify.app/pages/join.html?org={organization_id}"
    }
    
    content = render_to_string('invitation.html', context)
    
    message = Mail(
        from_email='news@1nbox-ai.com',
        to_emails=email,
        subject=f"You've been invited to join {organization_name} on 1nbox",
        html_content=content
    )
    
    try:
        response = sg.send(message)
        return True, response.status_code
    except Exception as e:
        print(f"Failed to send email to {email}: {str(e)}")
        return False, str(e)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def invite_team_member(request):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Check if current user exists and is admin
        try:
            current_user = User.objects.get(email=email)
            if current_user.role != 'admin':
                return JsonResponse({
                    'success': False, 
                    'error': 'Only admin users can invite team members'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Get invitation data
        data = json.loads(request.body)
        new_member_email = data.get('email')
        
        if not new_member_email:
            return JsonResponse({
                'success': False,
                'error': 'Email is required'
            }, status=400)
            
        # Check if user already exists in this organization
        if User.objects.filter(
            email=new_member_email,
            organization=current_user.organization
        ).exists():
            return JsonResponse({
                'success': False,
                'error': 'User already exists in this organization'
            }, status=400)
            
        # Create new pending user
        new_user = User.objects.create(
            email=new_member_email,
            organization=current_user.organization,
            role='member',
            state='pending'
        )
        
        # Send invitation email
        email_success, email_result = send_email(
            new_member_email,
            current_user.organization.name,
            current_user.organization.id
        )
        
        if not email_success:
            # Delete the user if email fails
            new_user.delete()
            return JsonResponse({
                'success': False,
                'error': f'Failed to send invitation email: {email_result}'
            }, status=500)

        return JsonResponse({
            'success': True,
            'message': 'Invitation sent successfully',
            'user_id': new_user.id
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

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


'''

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


'''

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






