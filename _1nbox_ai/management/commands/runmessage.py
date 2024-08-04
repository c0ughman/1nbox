from django.core.management.base import BaseCommand
from _1nbox_ai.message import send_summaries  # Adjust import as necessary

class Command(BaseCommand):
    help = 'Send summaries to all users'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting to send summaries...'))
        try:
            send_summaries()
            self.stdout.write(self.style.SUCCESS('Summaries sent successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error occurred: {e}'))
