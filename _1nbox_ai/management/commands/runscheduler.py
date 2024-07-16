from django.core.management.base import BaseCommand
from _1nbox_ai.schedulers import timeLoop
from django.utils import autoreload

class Command(BaseCommand):
    help = 'Runs timeLoop'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting background task...')
        autoreload.run_with_reloader(timeLoop)
