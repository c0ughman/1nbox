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
                if firebase_creds:
                    cred = credentials.Certificate(firebase_creds)
                    firebase_admin.initialize_app(cred)
                    print("Firebase initialized successfully")
                else:
                    print("Warning: Firebase credentials not configured - authentication features disabled")
            except Exception as e:
                print(f"Warning: Firebase initialization failed: {e}")
                # Don't crash the app if Firebase fails to initialize
                import traceback
                traceback.print_exc()
