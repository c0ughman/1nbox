from django.db import models
from django.contrib.postgres.fields import ArrayField
import json

class Topic(models.Model):
    name = models.CharField(max_length=255)
    sources = ArrayField(models.CharField(max_length=255), blank=True, default=list)
    prompt = models.TextField(blank=True, null=True)
    cluster_summaries = models.JSONField(default=dict,blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    questions = models.TextField(blank=True, null=True)
    number_of_articles = models.IntegerField(default=0,blank=True, null=True)
    children = models.ManyToManyField('self', blank=True, related_name='parents')
    custom = models.BooleanField(default=False,blank=True)
    created_by = models.CharField(max_length=255, blank=True, null=True)

    
    def __str__(self):
        return self.name

class User(models.Model):
    email = models.CharField(max_length=255, blank=True, null=True)
    supabase_user_id = models.CharField(max_length=255, null=False, blank=False)
    plan = models.CharField(max_length=255, null=False, default="free", blank=False)
    negative_keywords = models.TextField(blank=True, null=True)
    positive_keywords = models.TextField(blank=True, null=True)
    topics = models.JSONField(default=list,blank=True, null=True)
    days_since = models.IntegerField(default=0,blank=True, null=True)

    def __str__(self):
        return f"{self.email}"
