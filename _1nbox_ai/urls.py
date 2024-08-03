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
from _1nbox_ai import workflow
from _1nbox_ai import schedulers
from django.db import connection

urlpatterns = [
    path('admin/', admin.site.urls),
    path('new_lead/', views.new_lead),
    path('new_user/', views.new_user),
    path('user/<str:supabase_user_id>/', views.get_user_data),
    path('new_settings/', views.new_settings),
    path('new_keywords/', views.new_keywords),
    path('redirect/', views.oauth_redirect, name='redirect'),
    path('process_tokens/', views.process_tokens, name='process_tokens'),
    path('workflow/', views.workflow, name='workflow'),
    path('stripe_webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('create_checkout_session/', views.create_checkout_session, name='create_checkout_session'),
    path('create_checkout_session_pro/', views.create_checkout_session_pro, name='create_checkout_session_pro')

]
