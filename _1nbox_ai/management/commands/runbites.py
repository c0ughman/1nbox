from django.core.management.base import BaseCommand
from _1nbox_ai.bites_scheduler import process_bites_subscriptions, cleanup_old_digests


class Command(BaseCommand):
    help = 'Process Bites subscriptions and send digest emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Also cleanup old digests',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Days to keep digests when cleaning up (default: 30)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting Bites subscription processing...')

        process_bites_subscriptions()

        if options['cleanup']:
            self.stdout.write(f"Cleaning up digests older than {options['days']} days...")
            cleanup_old_digests(days_to_keep=options['days'])

        self.stdout.write(self.style.SUCCESS('Bites processing completed'))
