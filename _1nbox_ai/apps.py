from django.apps import AppConfig
import firebase_admin
from firebase_admin import credentials
from django.conf import settings

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '_1nbox_ai'

    def ready(self):
        if not firebase_admin._apps:
            try:
                firebase_creds = settings.FIREBASE_CREDENTIALS
                if firebase_creds and firebase_creds.get('private_key'):
                    cred = credentials.Certificate(firebase_creds)
                    firebase_admin.initialize_app(cred)
                else:
                    print("Warning: Firebase credentials not configured")
            except Exception as e:
                print(f"Warning: Firebase initialization failed: {e}")
