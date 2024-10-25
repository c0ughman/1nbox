from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Organization(models.Model):
    # AutoField id is automatically added by Django, no need to specify
    name = models.CharField(max_length=255)  # Added this as it's usually needed
    plan = models.CharField(max_length=255)
    status = models.CharField(
        max_length=50,
        choices=[
            ('active', 'Active'),
            ('past_due', 'Past Due'),
            ('canceled', 'Canceled'),
        ],
        default='active'
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.plan})"
    
    class Meta:
        ordering = ['-created_at']


class User(models.Model):
    # AutoField id is automatically added by Django
    email = models.CharField(max_length=255, unique=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(
        max_length=50,
        choices=[
            ('admin', 'Admin'),
            ('member', 'Member'),
        ],
        default='member'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='users'
    )
    
    def __str__(self):
        return f"{self.email} ({self.role})"
    
    class Meta:
        ordering = ['-joined_at']


class Topic(models.Model):
    # AutoField id is automatically added by Django
    name = models.CharField(max_length=255)
    sources = ArrayField(
        models.CharField(max_length=255),
        blank=True,
        default=list
    )
    prompt = models.TextField(blank=True, null=True)
    negative_keywords = models.TextField(blank=True, null=True)
    positive_keywords = models.TextField(blank=True, null=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='topics'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']


class Summary(models.Model):
    # AutoField id is automatically added by Django
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='summaries'
    )
    clusters = models.JSONField(default=dict, blank=True, null=True)
    cluster_summaries = models.JSONField(default=dict, blank=True, null=True)
    final_summary = models.JSONField(default=dict, blank=True, null=True)
    questions = models.TextField(blank=True, null=True)
    number_of_articles = models.IntegerField(default=0, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Summary for {self.topic.name} ({self.created_at.date()})"
    
    class Meta:
        ordering = ['-created_at']
