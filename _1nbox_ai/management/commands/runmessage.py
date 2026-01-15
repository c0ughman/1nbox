from django.core.management.base import BaseCommand
from _1nbox_ai.message import send_summaries  # Adjust import as necessary

class Command(BaseCommand):
    help = 'Send summaries to all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sending emails to ALL organizations, bypassing time checks (use for testing)',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        if force:
            self.stdout.write(self.style.WARNING('⚠️  FORCE MODE: Sending emails to ALL organizations, bypassing time checks'))
        
        self.stdout.write(self.style.SUCCESS('Starting to send summaries...'))
        try:
            send_summaries(force=force)
            self.stdout.write(self.style.SUCCESS('Summaries sent successfully!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error occurred: {e}'))
