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
                print("Found no publication date... will be skipped")
                return None

        def get_articles_from_rss(rss_url, days_back=1):
            feed = feedparser.parse(rss_url)
            articles = []
            cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
            
            for entry in feed.entries:
                pub_date = get_publication_date(entry)
                
                if pub_date and pub_date >= cutoff_date:
                    articles.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': pub_date,
                        'summary': entry.summary if 'summary' in entry else '',
                        'content': entry.content[0].value if 'content' in entry else entry.summary
                    })
                elif not pub_date:
                    self.stdout.write(f"Warning: Missing date for entry '{entry.title}'")
            
            return articles

        def get_articles_from_multiple_sources(rss_urls, days_back=1):
            all_articles = {}
            for url in rss_urls:
                articles = get_articles_from_rss(url, days_back)
                all_articles[url] = articles
            return all_articles

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
        all_articles = get_articles_from_multiple_sources(rss_urls, days_back)

        # Process and print statistics
        total_articles = 0
        articles_per_site = {}
        all_article_list = []

        for url, articles in all_articles.items():
            num_articles = len(articles)
            total_articles += num_articles
            articles_per_site[url] = num_articles
            all_article_list.extend(articles)

        # Find smallest and largest articles
        if all_article_list:
            smallest_article = min(all_article_list, key=lambda x: len(x['content']))
            largest_article = max(all_article_list, key=lambda x: len(x['content']))

        # Print statistics
        self.stdout.write(f"Total number of articles: {total_articles}")
        self.stdout.write("\nNumber of articles per site:")
        for url, count in articles_per_site.items():
            self.stdout.write(f"{url}: {count}")

        if all_article_list:
            self.stdout.write(f"\nSmallest article: '{smallest_article['title']}' ({len(smallest_article['content'])} characters)")
            self.stdout.write(f"Largest article: '{largest_article['title']}' ({len(largest_article['content'])} characters)")

            self.stdout.write("\n10 sample article titles:")
            for article in all_article_list[:10]:
                self.stdout.write(f"- {article['title']}")
        else:
            self.stdout.write("\nNo articles found in the specified timeframe.")
