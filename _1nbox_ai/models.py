from django.db import models

class User(models.Model):
    email = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    supabase_user_id = models.CharField(max_length=255, null=False, blank=False)
    last_run = models.IntegerField()
    plan = models.CharField(max_length=255, null=False, default="no plan", blank=False)
    negative_keywords = models.TextField(blank=True, null=True)
    positive_keywords = models.TextField(blank=True, null=True)
    style = models.CharField(max_length=255, blank=True, null=True)
    frequency = models.CharField(max_length=255)
    weekday = models.CharField(max_length=255, blank=True, null=True)
    t = models.CharField(max_length=255, blank=True, null=True)
    t2 = models.CharField(max_length=255, blank=True, null=True)
    t3 = models.CharField(max_length=255, blank=True, null=True)
    t4 = models.CharField(max_length=255, blank=True, null=True)
    t5 = models.CharField(max_length=255, blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    provider_token = models.CharField(max_length=255, blank=True, null=True)
    refresh_token = models.CharField(max_length=255, blank=True, null=True)
    provider_refresh_token = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.email}"


class ScheduledTask(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    t = models.CharField(max_length=255)
    frequency = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.t} - {self.user.email}"
