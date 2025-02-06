from django.core.management.base import BaseCommand
from ...news import process_all_topics
import traceback

class Command(BaseCommand):
    help = 'Run news processing for all topics'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--common_word_threshold', type=int, default=2, help='Number of common words required for clustering')
        parser.add_argument('--top_words_to_consider', type=int, default=3, help='Number of top words to consider for clustering')
        parser.add_argument('--merge_threshold', type=int, default=2, help='Number of common words required to merge clusters')
        parser.add_argument('--min_articles', type=int, default=3, help='Minimum number of articles per cluster')
        parser.add_argument('--join_percentage', type=float, default=0.5, help='Percentage of matching words required to join clusters from misc')
        parser.add_argument('--final_merge_percentage', type=float, default=0.5, help='Percentage of matching words required or merge clusters')
        parser.add_argument('--sentences_final_summary', type=int, default=3, help='Amount of sentences per topic in the final summary')
        parser.add_argument('--title_only', action='store_true', help='If set, clustering will only use article titles')
        parser.add_argument('--all_words', action='store_true', help='If set, clustering will include all words, not just capitalized ones')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting news processing...'))
        try:
            process_all_topics(
                days_back=options['days'],
                common_word_threshold=options['common_word_threshold'],
                top_words_to_consider=options['top_words_to_consider'],
                merge_threshold=options['merge_threshold'],
                min_articles=options['min_articles'],
                join_percentage=options['join_percentage'],
                final_merge_percentage=options['final_merge_percentage'],
                sentences_final_summary=options['sentences_final_summary'],
                title_only=options['title_only'],
                all_words=options['all_words']
            )
            self.stdout.write(self.style.SUCCESS('News processing completed successfully.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR('Error during news processing:'))
            self.stderr.write(self.style.ERROR(str(e)))
            self.stderr.write(self.style.ERROR(traceback.format_exc()))
