from django.core.management.base import BaseCommand
from _1nbox_ai.schedulers import timeLoop

class Command(BaseCommand):
    help = 'Runs timeLoop'

    def handle(self, *args, **kwargs):
        # Call your function here
        timeLoop()