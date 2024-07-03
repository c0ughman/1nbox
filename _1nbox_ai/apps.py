from django.apps import AppConfig

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '_1nbox_ai'


    def ready(self):
        # Your code to run when the server starts
        pass
        
