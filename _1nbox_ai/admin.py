from django.contrib import admin
from .models import User, ScheduledTask

admin.site.register(User)
admin.site.register(ScheduledTask)
