from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from _1nbox_ai.models import User, Topic, Organization, Summary, Comment
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
        
        # Fetch comments from users in the same organization
        organization_comments = Comment.objects.filter(
            writer__organization=current_user.organization
        ).select_related('writer').order_by('position')
        
        # Build comments data
        comments_data = [{
            'position': comment.position,
            'comment': comment.comment,
            'writer': comment.writer.name,  # Only including writer name as requested
        } for comment in organization_comments]
        
        # Fetch all users in the same organization
        organization_users = User.objects.filter(
            organization=current_user.organization
        ).select_related('organization')
        
        # Build users data with additional fields
        users_data = [{
            'id': org_user.id,
            'email': org_user.email,
            'name': org_user.name,
            'state': org_user.state,
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
        
        # Build the response with additional user fields
        response_data = {
            'user': {
                'id': current_user.id,
                'email': current_user.email,
                'name': current_user.name,
                'state': current_user.state,
                'role': current_user.role,
                'joined_at': current_user.joined_at,
            },
            'users': users_data,
            'organization': {
                'id': current_user.organization.id,
                'name': current_user.organization.name,
                'plan': current_user.organization.plan,
                'status': current_user.organization.status,
                'created_at': current_user.organization.created_at,
                'description': current_user.organization.description,
                'stripe_customer_id': current_user.organization.stripe_customer_id,
                'stripe_subscription_id': current_user.organization.stripe_subscription_id,
            },
            'topics': topics_data,
            'comments': comments_data
        }
        
        return JsonResponse(response_data)
    
    except User.DoesNotExist:
        return JsonResponse({
            'error': 'User not found in database'
        }, status=404)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
            print(f"Internal error: {str(e)}")  # For debugging in MVP
            return JsonResponse({'error': 'An internal error occurred'}, status=500)
            
        return JsonResponse({'success': True, 'id': topic.id})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)



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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
        
        try:
            current_user = User.objects.get(email=email)
            
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
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

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
            print(f"Internal error: {str(e)}")  # For debugging in MVP
            return HttpResponse("An internal error occurred", status=500)
    else:
        return HttpResponse("Only POST requests are allowed.", status=405)

@csrf_exempt
def sign_up(request):
    if request.method == 'POST':
        try:
            request_data = json.loads(request.body.decode('utf-8'))
            print("Full request data:", request_data)
            
            email = request_data.get('email')
            
            print(f"Extracted data: email={email}")
            
            user, created = User.objects.get_or_create(email=email)
            
            if created:
                user.email = email
                user.save()
                print(f"New user created: {user.id}")
                return JsonResponse({'success': True, 'user_id': user.id, 'message': 'User created successfully'}, status=201)
            else:
                user.email = email
                user.save()
                print(f"Existing user updated: {user.id}")
                return JsonResponse({'success': True, 'user_id': user.id, 'message': 'User updated successfully'}, status=200)
        
        except Exception as e:
            print(f"Internal error: {str(e)}")  # For debugging in MVP
            return JsonResponse({'error': 'An internal error occurred'}, status=500)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

stripe.api_key = settings.STRIPE_SECRET_KEY

# Configuration Constants
PLAN_PRICE_MAPPING = {
    'core': 'price_1Qb4GKCHpOkAgMGGcMaNiN9L',
    'executive': 'price_1Qb4GvCHpOkAgMGGSJRK8ZVH',
    'corporate': 'price_1Qb4I2CHpOkAgMGGFBbRBl0J'
}

PLAN_PRICES = {
    'core': 8000,        # $80.00
    'executive': 17000,  # $170.00
    'corporate': 32000   # $320.00
}

# Helper Functions
def get_plan_from_price_id(price_id: str) -> str:
    """Get plan name from Stripe price ID."""
    return next(
        (plan for plan, stripe_price in PLAN_PRICE_MAPPING.items() 
         if stripe_price == price_id),
        'free'
    )

def calculate_proration_amount(current_subscription: stripe.Subscription, new_plan: str) -> int:
    """
    Calculate proration amount for plan change.
    Returns amount in cents.
    """
    try:
        current_price_id = current_subscription['items']['data'][0].price.id
        current_plan = get_plan_from_price_id(current_price_id)
        
        # Get prices in cents
        current_price = int(PLAN_PRICES[current_plan])
        new_price = int(PLAN_PRICES[new_plan])
        
        # Calculate remaining time in current period
        current_period_end = int(current_subscription.current_period_end)
        current_period_start = int(current_subscription.current_period_start)
        total_period = current_period_end - current_period_start
        remaining_time = current_period_end - int(datetime.now().timestamp())
        
        # Calculate prorated amount
        unused_amount = int((remaining_time / total_period) * current_price)
        new_amount = int((remaining_time / total_period) * new_price)
        
        return max(0, new_amount - unused_amount)
    except Exception as e:
        print(f"Error calculating proration: {str(e)}")
        return 0

# Main Views
@csrf_exempt
@require_http_methods(["POST"])
def create_subscription(request):
    """
    Creates or updates a subscription, handling proration automatically.
    """
    try:
        # Parse request data
        try:
            data = json.loads(request.body)
            org_id = data.get('organization_id')
            new_plan = data.get('plan')
            
            if not org_id or not new_plan:
                return JsonResponse({
                    'error': 'organization_id and plan are required'
                }, status=400)
                
            print(f"Processing subscription request: org={org_id}, plan={new_plan}")
        except json.JSONDecodeError as e:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Verify Firebase token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'No valid authorization token'}, status=401)
        
        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            user_email = decoded_token['email']
        except Exception as e:
            return JsonResponse({'error': 'Invalid authorization token'}, status=401)

        # Get organization and verify access
        try:
            organization = Organization.objects.get(id=org_id)
            if not organization.users.filter(email=user_email).exists():
                return JsonResponse({'error': 'Unauthorized access'}, status=403)
        except Organization.DoesNotExist:
            return JsonResponse({'error': 'Organization not found'}, status=404)

        # Handle existing subscription if present
        if organization.stripe_subscription_id:
            try:
                current_subscription = stripe.Subscription.retrieve(
                    organization.stripe_subscription_id
                )
                current_price_id = current_subscription['items']['data'][0].price.id
                current_plan = get_plan_from_price_id(current_price_id)
                
                print(f"Processing change from {current_plan} to {new_plan}")
                #Schedule change for the next period
                stripe.Subscription.modify(
                    organization.stripe_subscription_id,
                    items=[{
                        'id': current_subscription['items']['data'][0].id,
                        'price': PLAN_PRICE_MAPPING[new_plan.lower()],
                    }],
                    proration_behavior='none',
                    billing_cycle_anchor='unchanged',
                )
                    
                organization.plan = new_plan
                organization.save()
                    
                return JsonResponse({
                    'checkout_url': f'https://1nbox.netlify.app/pages/main?success=true&org={org_id}&plan={new_plan}'
                })
                    
            except stripe.error.StripeError as e:
                print(f"Stripe error: {str(e)}")
                return JsonResponse({'error': str(e)}, status=400)
                
        # Handle new subscription creation
        else:
            print(f"Creating new subscription for plan: {new_plan}")
            # Create or get Stripe customer
            if organization.stripe_customer_id:
                customer = stripe.Customer.retrieve(organization.stripe_customer_id)
            else:
                admin_user = organization.users.filter(role='admin').first()
                if not admin_user:
                    return JsonResponse({'error': 'No admin user found'}, status=400)

                customer = stripe.Customer.create(
                    email=admin_user.email,
                    metadata={'organization_id': str(org_id)}
                )
                organization.stripe_customer_id = customer.id
                organization.save()

            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{
                    'price': PLAN_PRICE_MAPPING[new_plan.lower()],
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f'https://1nbox.netlify.app/pages/main?success=true&org={org_id}&plan={new_plan}',
                cancel_url=f'https://1nbox.netlify.app/pages/main?canceled=true&org={org_id}',
                metadata={
                    'organization_id': str(org_id),
                    'plan': new_plan
                }
            )

            return JsonResponse({'checkout_url': checkout_session.url})

    except stripe.error.StripeError as e:
        print(f"Stripe error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    print("Received Stripe webhook")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        print(f"Webhook Event Type: {event.type}")

        if event.type == 'checkout.session.completed':
            session = event.data['object']
            handle_checkout_session_completed(session)
            
        elif event.type == 'customer.subscription.updated':
            subscription = event.data['object']
            handle_subscription_update(subscription)
            
        elif event.type == 'customer.subscription.deleted':
            subscription = event.data['object']
            handle_subscription_deleted(subscription)
            
        elif event.type == 'setup_intent.succeeded':
            setup_intent = event.data['object']
            handle_setup_intent_succeeded(setup_intent)

        return JsonResponse({'status': 'success'})

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

def handle_setup_intent_succeeded(setup_intent):
    """Handle successful setup intent for subscription updates."""
    if 'subscription_id' in setup_intent.metadata:
        subscription_id = setup_intent.metadata['subscription_id']
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                default_payment_method=setup_intent.payment_method,
                payment_behavior='default_incomplete',
            )
            print(f"Updated subscription {subscription_id} with new payment method")
        except Exception as e:
            print(f"Error updating subscription with new payment method: {str(e)}")

def handle_checkout_session_completed(session):
    """Handle completed checkout session."""
    org_id = session.metadata.get('organization_id')
    plan = session.metadata.get('plan')
    
    if not org_id or not plan:
        print("Missing org_id or plan in session metadata")
        return
        
    try:
        organization = Organization.objects.get(id=org_id)
        organization.plan = plan
        organization.status = 'active'
        organization.stripe_subscription_id = session.subscription
        organization.save()
        
        print(f"Updated organization {org_id} to plan {plan}")
    except Organization.DoesNotExist:
        print(f"Organization not found: {org_id}")
    except Exception as e:
        print(f"Error updating organization: {str(e)}")

def handle_subscription_update(subscription):
    """Handle subscription update event."""
    try:
        customer = stripe.Customer.retrieve(subscription.customer)
        org_id = customer.metadata.get('organization_id')
        
        if not org_id:
            print(f"No organization_id found for customer: {subscription.customer}")
            return
            
        try:
            organization = Organization.objects.get(id=org_id)
            
            # Map Stripe Price ID to plan
            price_id = subscription.items.data[0].price.id
            plan = get_plan_from_price_id(price_id)
            
            organization.plan = plan
            organization.status = 'active'
            organization.stripe_subscription_id = subscription.id
            organization.save()
            
        except Organization.DoesNotExist:
            print(f"Organization not found: {org_id}")
            
    except Exception as e:
        print(f"Error in handle_subscription_update: {str(e)}")
        raise

def handle_subscription_deleted(subscription):
    """Handle subscription deletion event."""
    try:
        customer = stripe.Customer.retrieve(subscription.customer)
        org_id = customer.metadata.get('organization_id')
        
        if not org_id:
            return
            
        try:
            organization = Organization.objects.get(id=org_id)
            organization.plan = 'free'
            organization.status = 'canceled'
            organization.stripe_subscription_id = None
            organization.save()
            
        except Organization.DoesNotExist:
            print(f"Organization not found: {org_id}")
    except Exception as e:
        print(f"Error in handle_subscription_deleted: {str(e)}")
        raise
        
@csrf_exempt
@firebase_auth_required
@require_http_methods(["DELETE"])
def delete_current_user(request):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Get the current user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        try:
            # First try to delete the user from Firebase
            user_to_delete = auth.get_user_by_email(email)
            auth.delete_user(user_to_delete.uid)
            print(f"Successfully deleted user {email} from Firebase")
        except auth.UserNotFoundError:
            print(f"User {email} not found in Firebase - continuing with database deletion")
        except Exception as e:
            print(f"Error deleting user from Firebase: {str(e)}")

        # Delete the user from your database
        user.delete()

        return JsonResponse({
            'success': True,
            'message': 'User deleted successfully'
        })

    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["PUT", "PATCH"])
def update_current_user_name(request):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Parse request data
        data = json.loads(request.body)
        new_name = data.get('name')
        
        if not new_name:
            return JsonResponse({
                'success': False,
                'error': 'Name is required'
            }, status=400)

        # Get and update the user
        try:
            user = User.objects.get(email=email)
            user.name = new_name
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Name updated successfully',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name
                }
            })
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["DELETE"])
def delete_organization(request, organization_id):
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
                    'error': 'Only admin users can delete organizations'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Get and delete the organization
        try:
            organization = Organization.objects.get(
                id=organization_id,
                users__email=email  # Ensures user belongs to this organization
            )
            organization.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Organization deleted successfully'
            })
        except Organization.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Organization not found or access denied'
            }, status=404)

    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["PUT", "PATCH"])
def update_organization_name(request, organization_id):
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
                    'error': 'Only admin users can update organization names'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Parse request data
        data = json.loads(request.body)
        new_name = data.get('name')
        
        if not new_name:
            return JsonResponse({
                'success': False,
                'error': 'Name is required'
            }, status=400)

        # Get and update the organization
        try:
            organization = Organization.objects.get(
                id=organization_id,
                users__email=email  # Ensures user belongs to this organization
            )
            organization.name = new_name
            organization.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Organization name updated successfully',
                'organization': {
                    'id': organization.id,
                    'name': organization.name
                }
            })
        except Organization.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Organization not found or access denied'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["PUT", "PATCH"])
def update_organization_plan(request, organization_id):
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
                    'error': 'Only admin users can update organization plans'
                }, status=403)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Parse request data
        data = json.loads(request.body)
        new_plan = data.get('plan')
        
        if not new_plan:
            return JsonResponse({
                'success': False,
                'error': 'Plan is required'
            }, status=400)

        # Validate plan value
        valid_plans = ['free', 'paid']  # Add other valid plans as needed
        if new_plan not in valid_plans:
            return JsonResponse({
                'success': False,
                'error': f'Invalid plan. Must be one of: {", ".join(valid_plans)}'
            }, status=400)

        # Get and update the organization
        try:
            organization = Organization.objects.get(
                id=organization_id,
                users__email=email  # Ensures user belongs to this organization
            )
            
            # TODO: Update the plan in Stripe
            # This part would need to be implemented based on your Stripe integration
            
            organization.plan = new_plan
            organization.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Organization plan updated successfully',
                'organization': {
                    'id': organization.id,
                    'name': organization.name,
                    'plan': organization.plan
                }
            })
        except Organization.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Organization not found or access denied'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
@firebase_auth_required  # Using your existing decorator
def get_pricing_organization_data(request):
    """
    Retrieve organization data for the pricing page using Firebase authentication.
    Returns organization ID, plan, and subscription status.
    """
    try:
        # Get Firebase user email from the token (already verified by decorator)
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Fetch user and related organization data efficiently
        user = User.objects.select_related('organization').get(email=email)
        
        # Build response with essential pricing-related data
        response_data = {
            'success': True,
            'organization': {
                'id': user.organization.id,
                'name': user.organization.name,
                'plan': user.organization.plan,
                'status': user.organization.status,
                'stripe_customer_id': user.organization.stripe_customer_id,
                'stripe_subscription_id': user.organization.stripe_subscription_id
            },
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role
            }
        }
        
        return JsonResponse(response_data)
    
    except User.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'User not found in database'
        }, status=404)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

@csrf_exempt
@firebase_auth_required
@require_http_methods(["POST"])
def add_comment(request):
    try:
        # Get the Firebase user from the decorator
        firebase_user = request.firebase_user
        email = firebase_user['email']
        
        # Get current user
        try:
            current_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)

        # Parse request data
        data = json.loads(request.body)
        comment_text = data.get('comment')
        position = data.get('position')
        writer_id = data.get('writer')
        
        # Validate required fields
        if not all([comment_text, position, writer_id]):
            return JsonResponse({
                'success': False,
                'error': 'comment, position, and writer are required fields'
            }, status=400)

        # Verify the writer_id matches the current user
        if int(writer_id) != current_user.id:
            return JsonResponse({
                'success': False,
                'error': 'Cannot create comments for other users'
            }, status=403)

        # Create the comment
        comment = Comment.objects.create(
            comment=comment_text,
            position=position,
            writer=current_user
        )

        return JsonResponse({
            'success': True,
            'comment': {
                'id': comment.id,
                'comment': comment.comment,
                'position': comment.position,
                'writer': current_user.name or current_user.email,
                'created_at': comment.created_at
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"Internal error: {str(e)}")  # For debugging in MVP
        return JsonResponse({'error': 'An internal error occurred'}, status=500)

# OLD 1NBOX RIP





















