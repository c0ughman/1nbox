from django.contrib import admin
from .models import Organization, User, Topic, Summary, Comment

admin.site.register(Organization)
admin.site.register(User)
admin.site.register(Topic)
admin.site.register(Summary)
admin.site.register(Comment)
