from django.contrib import admin
from .models import (
    Organization, User, Topic, Summary, Comment,
    ChatConversation, ChatMessage, GenieAnalysis,
    BitesSubscription, BitesDigest
)

admin.site.register(Organization)
admin.site.register(User)
admin.site.register(Topic)
admin.site.register(Summary)
admin.site.register(Comment)
admin.site.register(ChatConversation)
admin.site.register(ChatMessage)
admin.site.register(GenieAnalysis)
admin.site.register(BitesSubscription)
admin.site.register(BitesDigest)
