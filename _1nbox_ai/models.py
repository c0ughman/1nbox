from django.db import models
from django.contrib.postgres.fields import ArrayField
import json

class Topic(models.Model):
    name = models.CharField(max_length=255)
    sources = ArrayField(models.CharField(max_length=255), blank=True, default=list)
    cluster_summaries = models.JSONField(default=dict,blank=True, null=True)
    summary = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class User(models.Model):
    email = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    supabase_user_id = models.CharField(max_length=255, null=False, blank=False)
    plan = models.CharField(max_length=255, null=False, default="no plan", blank=False)
    negative_keywords = models.TextField(blank=True, null=True)
    positive_keywords = models.TextField(blank=True, null=True)
    style = models.CharField(max_length=255, blank=True, null=True)
    frequency = models.CharField(max_length=255)
    language = models.CharField(max_length=255, default="English", null=False, blank=False)
    time_zone = models.CharField(max_length=255, default="Europe/Madrid", null=False, blank=False)
    weekday = models.CharField(max_length=255, blank=True, null=True)
    t = models.CharField(max_length=255, blank=True, null=True)
    t2 = models.CharField(max_length=255, blank=True, null=True)
    t3 = models.CharField(max_length=255, blank=True, null=True)
    t4 = models.CharField(max_length=255, blank=True, null=True)
    t5 = models.CharField(max_length=255, blank=True, null=True)
    last_run = models.IntegerField(blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    provider_token = models.CharField(max_length=255, blank=True, null=True)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    provider_refresh_token = models.CharField(max_length=255, blank=True, null=True)
    messaging_app = models.CharField(max_length=255, blank=True, null=True)
    topics = models.JSONField(default=list,blank=True, null=True)
    days_since = models.IntegerField(default=0,blank=True, null=True)

    def __str__(self):
        return f"{self.email}"
