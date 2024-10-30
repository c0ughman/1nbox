from django.apps import AppConfig
import firebase_admin
from firebase_admin import credentials
from django.conf import settings

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '_1nbox_ai'


    def ready(self):
        # Initialize Firebase if not already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
