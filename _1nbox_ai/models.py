from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class Organization(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
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
    summary_time = models.TimeField(blank=True, null=True)
    summary_timezone = models.CharField(max_length=50, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    industry = models.CharField(max_length=255, blank=True, null=True)
    headquarters = models.CharField(max_length=255, blank=True, null=True)
    employee_count = models.CharField(max_length=100, blank=True, null=True)
    annual_revenue = models.CharField(max_length=100, blank=True, null=True)
    key_products = models.JSONField(default=list, blank=True, null=True)
    competitors = models.JSONField(default=list, blank=True, null=True)
    target_markets = models.JSONField(default=list, blank=True, null=True)
    strategic_priorities = models.JSONField(default=list, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.plan})"

    class Meta:
        ordering = ['-created_at']

class User(models.Model):
    email = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)  # Added name field
    state = models.CharField(max_length=255, blank=True, null=True)  # Added state field
    send_email = models.BooleanField(default=False)  # Added send_email field
    joined_at = models.DateTimeField(default=timezone.now)
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
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']

class Summary(models.Model):
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
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Summary for {self.topic.name} ({self.created_at.date()})"
    
    class Meta:
        ordering = ['-created_at']

class Comment(models.Model):
    comment = models.TextField()
    writer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    position = models.IntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Comment by {self.writer.email} at position {self.position}"

    class Meta:
        ordering = ['position']


class ChatConversation(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_conversations'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_conversations'
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation: {self.title or 'Untitled'} by {self.user.email}"

    class Meta:
        ordering = ['-updated_at']


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]
    DOCUMENT_TYPE_CHOICES = [
        ('executive_brief', 'Executive Brief'),
        ('swot_analysis', 'SWOT Analysis'),
        ('risk_assessment', 'Risk Assessment'),
        ('competitive_intel', 'Competitive Intel'),
        ('trend_report', 'Trend Report'),
        ('stakeholder_brief', 'Stakeholder Brief'),
        ('action_items', 'Action Items'),
        ('market_snapshot', 'Market Snapshot'),
    ]

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
        blank=True,
        null=True
    )
    metadata = models.JSONField(default=dict, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

    class Meta:
        ordering = ['created_at']


class GenieAnalysis(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='genie_analyses'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='genie_analyses'
    )
    query = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    results = models.JSONField(default=dict, blank=True, null=True)
    sources = models.JSONField(default=list, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Analysis: {self.query[:50]}... ({self.status})"

    class Meta:
        ordering = ['-created_at']


class BitesSubscription(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bites_subscriptions'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='bites_subscriptions'
    )
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    delivery_time = models.TimeField(default=timezone.now)
    user_timezone = models.CharField(max_length=50, default='UTC')
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Subscription: {self.user.email} -> {self.topic.name} ({self.frequency})"

    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'topic']


class BitesDigest(models.Model):
    DIGEST_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='bites_digests'
    )
    digest_type = models.CharField(max_length=20, choices=DIGEST_TYPE_CHOICES)
    digest_date = models.DateField()
    content = models.JSONField()
    article_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Digest: {self.topic.name} ({self.digest_type}) - {self.digest_date}"

    class Meta:
        ordering = ['-digest_date']
        unique_together = ['topic', 'digest_type', 'digest_date']
