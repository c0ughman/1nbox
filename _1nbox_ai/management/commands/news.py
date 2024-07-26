import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds and display statistics'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')

    def handle(self, *args, **options):
        days_back = options['days']

        def get_publication_date(entry):
            if 'published_parsed' in entry:
                return datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
            elif 'updated_parsed' in entry:
                return datetime(*entry.updated_parsed[:6], tzinfo=pytz.utc)
            elif 'published' in entry:
                return datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
            elif 'updated' in entry:
                return datetime.strptime(entry.updated, '%a, %d %b %Y %H:%M:%S %Z')
            elif 'dc:date' in entry:
                return datetime.strptime(entry['dc:date'], '%Y-%m-%dT%H:%M:%SZ')
            else:
                return None

        def get_articles_from_rss(rss_url, days_back=1):
            feed = feedparser.parse(rss_url)
            articles = []
            deleted_articles = []
            cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
            
            for entry in feed.entries:
                pub_date = get_publication_date(entry)
                
                if pub_date and pub_date >= cutoff_date:
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': pub_date,
                        'summary': entry.summary if 'summary' in entry else '',
                        'content': entry.content[0].value if 'content' in entry else entry.summary if 'summary' in entry else ''
                    })
                else:
                    deleted_articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.summary if 'summary' in entry else '',
                        'content': entry.content[0].value if 'content' in entry else entry.summary if 'summary' in entry else ''
                    })
            
            return articles, deleted_articles

        def get_articles_from_multiple_sources(rss_urls, days_back=1):
            all_articles = {}
            all_deleted_articles = {}
            for url in rss_urls:
                print(url)
                articles, deleted_articles = get_articles_from_rss(url, days_back)
                all_articles[url] = articles
                all_deleted_articles[url] = deleted_articles
            return all_articles, all_deleted_articles

        # List of 10 RSS feed URLs focused on politics
        rss_urls = [
            'http://rss.cnn.com/rss/cnn_allpolitics.rss',
            'https://feeds.nbcnews.com/nbcnews/public/politics',
            'http://feeds.foxnews.com/foxnews/politics',
            'http://feeds.washingtonpost.com/rss/politics',
            'https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml',
            'https://www.politico.com/rss/politics.xml',
            'https://thehill.com/homenews/feed/',
            'https://www.npr.org/rss/rss.php?id=1014',
            'http://feeds.bbci.co.uk/news/politics/rss.xml',
            'https://rssfeeds.usatoday.com/UsatodaycomWashington-TopStories'
        ]

        # Fetch articles
        all_articles, all_deleted_articles = get_articles_from_multiple_sources(rss_urls, days_back)

        # Process and print statistics
        total_articles = 0
        articles_per_site = {}
        deleted_articles_per_site = {}
        all_article_list = []
        deleted_article_list = []
        avg_word_count_per_site = {}

        for url, articles in all_articles.items():
            num_articles = len(articles)
            num_deleted_articles = len(all_deleted_articles[url])
            total_articles += num_articles
            articles_per_site[url] = num_articles
            deleted_articles_per_site[url] = num_deleted_articles
            all_article_list.extend(articles)
            deleted_article_list.extend(all_deleted_articles[url])

            total_words = sum(len(article['content'].split()) for article in articles)
            avg_word_count_per_site[url] = total_words / num_articles if num_articles > 0 else 0

        # Find smallest and largest articles
        if all_article_list:
            smallest_article = min(all_article_list, key=lambda x: len(x['content']))
            largest_article = max(all_article_list, key=lambda x: len(x['content']))

        # Calculate total characters, words, and OpenAI tokens
        total_characters = sum(len(article['content']) for article in all_article_list)
        total_words = sum(len(article['content'].split()) for article in all_article_list)
        total_tokens = sum(len(article['content'].split()) // 4 for article in all_article_list)  # Rough estimate

        # Print statistics
        self.stdout.write(f"Total number of articles: {total_articles}")
        self.stdout.write(f"Total characters: {total_characters}")
        self.stdout.write(f"Total words: {total_words}")
        self.stdout.write(f"Total OpenAI tokens (approx): {total_tokens}")

        self.stdout.write("\nNumber of articles per site:")
        for url, count in articles_per_site.items():
            self.stdout.write(f"{url}: {count} (Deleted: {deleted_articles_per_site[url]})")

        self.stdout.write("\nAverage word count per article for each site:")
        for url, avg_word_count in avg_word_count_per_site.items():
            self.stdout.write(f"{url}: {avg_word_count:.2f} words")

        if all_article_list:
            self.stdout.write(f"\nSmallest article: '{smallest_article['title']}' ({len(smallest_article['content'])} characters)")
            self.stdout.write(f"Largest article: '{largest_article['title']}' ({len(largest_article['content'])} characters)")

            self.stdout.write("\n10 sample articles:")
            for article in all_article_list[:10]:
                self.stdout.write(f"- Title: {article['title']}\n  Link: {article['link']}\n  Published: {article['published']}\n  Summary: {article['summary']}\n  Content: {article['content']}\n")
        else:
            self.stdout.write("\nNo articles found in the specified timeframe.")

        self.stdout.write("\n5 sample articles deleted due to missing publication date:")
        for article in deleted_article_list[:5]:
            self.stdout.write(f"- Title: {article['title']}\n  Link: {article['link']}\n  Summary: {article['summary']}\n  Content: {article['content']}\n")
