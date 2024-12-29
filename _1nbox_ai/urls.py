"""
URL configuration for _1nbox_ai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from _1nbox_ai import views
from django.contrib import admin
from django.db import connection

urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/<str:id>/', views.get_user_data),
    path('sign_up/', views.sign_up),
    path('message_received/', views.message_received),
    path('create_topic/', views.create_topic),
    path('update_topic/<int:topic_id>/', views.update_topic),
    path('delete_topic/<int:topic_id>/', views.delete_topic),
    path('update_member/<int:user_id>/', views.update_team_member),
    path('delete_member/<int:user_id>/', views.delete_team_member),
    path('join_member/<int:organization_id>/', views.join_team_member),
    path('invite_member/', views.invite_team_member),
    path('check_pending_invitation/<int:organization_id>/', views.check_pending_invitation),
    path('topic/clusters/<str:id>/', views.get_clusters),
    
    path('initial_signup/', views.initial_signup),
    path('get_user_data/', views.get_user_data),
    path('get_user_organization_data/', views.get_user_organization_data),

    path('delete_member/current/', views.delete_current_user),
    path('update_member/current/', views.update_current_user_name),
    path('delete_organization/<int:organization_id>/', views.delete_organization),
    path('update_organization/<int:organization_id>/name/', views.update_organization_name),
    path('update_organization/<int:organization_id>/plan/', views.update_organization_plan),

    
    path('subscriptions/create/', views.create_subscription),
    path('webhooks/stripe/', views.stripe_webhook),
    path('subscriptions/change/', views.change_subscription),

]
