from django.core.management.base import BaseCommand
from django.db import transaction
from _1nbox_ai.models import (
    User, Organization, Topic, Summary, Comment,
    ChatConversation, ChatMessage, GenieAnalysis,
    BitesSubscription, BitesDigest
)
from firebase_admin import auth
import os


class Command(BaseCommand):
    help = 'Clear all users, organizations, and related data from database and Firebase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--firebase-only',
            action='store_true',
            help='Only clear Firebase users, keep database data',
        )
        parser.add_argument(
            '--database-only',
            action='store_true',
            help='Only clear database data, keep Firebase users',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt (use with caution)',
        )

    def handle(self, *args, **options):
        firebase_only = options.get('firebase_only', False)
        database_only = options.get('database_only', False)
        confirm = options.get('confirm', False)

        if firebase_only and database_only:
            self.stdout.write(self.style.ERROR('Cannot use --firebase-only and --database-only together'))
            return

        # Show what will be deleted
        if not confirm:
            self.stdout.write(self.style.WARNING('=' * 60))
            self.stdout.write(self.style.WARNING('WARNING: This will delete ALL data!'))
            self.stdout.write(self.style.WARNING('=' * 60))
            
            if not firebase_only:
                org_count = Organization.objects.count()
                user_count = User.objects.count()
                topic_count = Topic.objects.count()
                summary_count = Summary.objects.count()
                
                self.stdout.write(f'\nDatabase counts:')
                self.stdout.write(f'  - Organizations: {org_count}')
                self.stdout.write(f'  - Users: {user_count}')
                self.stdout.write(f'  - Topics: {topic_count}')
                self.stdout.write(f'  - Summaries: {summary_count}')
            
            if not database_only:
                try:
                    # Try to get Firebase user count (approximate)
                    self.stdout.write(f'\nFirebase: Will attempt to delete all users')
                except Exception as e:
                    self.stdout.write(f'\nFirebase: Error checking users - {e}')
            
            self.stdout.write(self.style.WARNING('\nThis action CANNOT be undone!'))
            response = input('\nType "DELETE ALL" to confirm: ')
            
            if response != 'DELETE ALL':
                self.stdout.write(self.style.ERROR('Operation cancelled.'))
                return

        # Clear Firebase users
        if not database_only:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write('Clearing Firebase users...')
            self.stdout.write('=' * 60)
            
            try:
                firebase_users_deleted = self.clear_firebase_users()
                self.stdout.write(self.style.SUCCESS(f'✓ Deleted {firebase_users_deleted} Firebase users'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error clearing Firebase: {str(e)}'))
                self.stdout.write(self.style.WARNING('Continuing with database cleanup...'))

        # Clear database data
        if not firebase_only:
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write('Clearing database data...')
            self.stdout.write('=' * 60)
            
            try:
                with transaction.atomic():
                    counts = self.clear_database_data()
                    
                    self.stdout.write(self.style.SUCCESS('\n✓ Database cleared successfully!'))
                    self.stdout.write(f'  - Organizations deleted: {counts["organizations"]}')
                    self.stdout.write(f'  - Users deleted: {counts["users"]}')
                    self.stdout.write(f'  - Topics deleted: {counts["topics"]}')
                    self.stdout.write(f'  - Summaries deleted: {counts["summaries"]}')
                    self.stdout.write(f'  - Comments deleted: {counts["comments"]}')
                    self.stdout.write(f'  - Chat conversations deleted: {counts["chat_conversations"]}')
                    self.stdout.write(f'  - Chat messages deleted: {counts["chat_messages"]}')
                    self.stdout.write(f'  - Genie analyses deleted: {counts["genie_analyses"]}')
                    self.stdout.write(f'  - Bites subscriptions deleted: {counts["bites_subscriptions"]}')
                    self.stdout.write(f'  - Bites digests deleted: {counts["bites_digests"]}')
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n✗ Error clearing database: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
                return

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✓ All data cleared successfully!'))
        self.stdout.write('=' * 60)
        self.stdout.write('\nYou can now start fresh with a new initial user.')

    def clear_firebase_users(self):
        """Delete all Firebase users"""
        deleted_count = 0
        
        try:
            # Check if Firebase is initialized
            if not os.environ.get('FIREBASE_PROJECT_ID'):
                self.stdout.write(self.style.WARNING('Firebase not configured, skipping Firebase cleanup'))
                return 0
            
            # List all users and delete them
            # Firebase Admin SDK paginates results, so we need to iterate
            page = auth.list_users()
            
            while page:
                for user in page.users:
                    try:
                        auth.delete_user(user.uid)
                        deleted_count += 1
                        self.stdout.write(f'  Deleted Firebase user: {user.email} ({user.uid})')
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'  Failed to delete {user.email}: {str(e)}'))
                
                # Get next page if available
                page = page.get_next_page() if page.has_next_page else None
            
            return deleted_count
            
        except Exception as e:
            # If Firebase isn't initialized or there's an error, log it
            self.stdout.write(self.style.WARNING(f'Firebase cleanup error: {str(e)}'))
            return deleted_count

    def clear_database_data(self):
        """Delete all database data"""
        counts = {
            'organizations': 0,
            'users': 0,
            'topics': 0,
            'summaries': 0,
            'comments': 0,
            'chat_conversations': 0,
            'chat_messages': 0,
            'genie_analyses': 0,
            'bites_subscriptions': 0,
            'bites_digests': 0,
        }
        
        # Delete in order to respect foreign key constraints
        # Note: Due to CASCADE relationships, deleting Organizations will delete
        # related Users, Topics, etc. But we'll count them first for reporting
        
        # Count before deletion
        counts['organizations'] = Organization.objects.count()
        counts['users'] = User.objects.count()
        counts['topics'] = Topic.objects.count()
        counts['summaries'] = Summary.objects.count()
        counts['comments'] = Comment.objects.count()
        counts['chat_conversations'] = ChatConversation.objects.count()
        counts['chat_messages'] = ChatMessage.objects.count()
        counts['genie_analyses'] = GenieAnalysis.objects.count()
        counts['bites_subscriptions'] = BitesSubscription.objects.count()
        counts['bites_digests'] = BitesDigest.objects.count()
        
        # Delete all data
        # Deleting organizations will cascade delete users, topics, summaries, etc.
        Organization.objects.all().delete()
        
        # Delete any remaining data that might not have been cascade deleted
        # (though there shouldn't be any)
        Comment.objects.all().delete()
        ChatMessage.objects.all().delete()
        ChatConversation.objects.all().delete()
        GenieAnalysis.objects.all().delete()
        BitesSubscription.objects.all().delete()
        BitesDigest.objects.all().delete()
        
        return counts

