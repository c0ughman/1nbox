import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from collections import defaultdict, Counter
import re

def extract_capitalized_words(text):
    # Extract capitalized words, excluding those at the start of sentences
    sentences = re.split(r'[.!?]+', text)
    words = []
    for sentence in sentences:
        sentence_words = sentence.strip().split()
        if len(sentence_words) > 1:
            words.extend([word for word in sentence_words[1:] if word.istitle()])
    return words

def simple_clustering(articles, min_word_freq=5, max_word_freq=0.3, num_clusters=5):
    # Extract capitalized words from all articles
    all_words = []
    for article in articles:
        all_words.extend(extract_capitalized_words(article['content']))
    
    # Count word frequencies
    word_counts = Counter(all_words)
    total_articles = len(articles)
    
    # Filter words based on frequency
    valid_words = set([word for word, count in word_counts.items() 
                       if min_word_freq <= count <= total_articles * max_word_freq])
    
    # Create clusters
    clusters = defaultdict(list)
    miscellaneous = []
    
    for article in articles:
        article_words = set(extract_capitalized_words(article['content'])) & valid_words
        if not article_words:
            miscellaneous.append(article)
        else:
            best_cluster = None
            max_overlap = 0
            for cluster_id, cluster_articles in clusters.items():
                cluster_words = set.union(*[set(extract_capitalized_words(a['content'])) & valid_words 
                                            for a in cluster_articles])
                overlap = len(article_words & cluster_words)
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_cluster = cluster_id
            
            if best_cluster is not None and len(clusters) >= num_clusters:
                clusters[best_cluster].append(article)
            elif len(clusters) < num_clusters:
                new_cluster_id = len(clusters) + 1
                clusters[new_cluster_id].append(article)
            else:
                miscellaneous.append(article)
    
    # Add miscellaneous cluster
    if miscellaneous:
        clusters['miscellaneous'] = miscellaneous
    
    return clusters

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

        # List of RSS feed URLs (same as before)
        rss_urls = [
            'https://rss.cnn.com/rss/edition.rss',
            'https://feeds.bbci.co.uk/news/rss.xml',
            'http://feeds.reuters.com/reuters/topNews',
            'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
            'https://www.theguardian.com/world/rss',
            'http://rss.cnn.com/rss/cnn_topstories.rss',
            'http://feeds.foxnews.com/foxnews/latest',
            'https://www.aljazeera.com/xml/rss/all.xml',
            'https://news.google.com/rss',
            'https://www.npr.org/rss/rss.php?id=1001',
            'https://www.washingtonpost.com/rss',
            'https://www.wsj.com/xml/rss/3_7085.xml',
            'https://feeds.a.dj.com/rss/RSSWorldNews.xml',
            'https://feeds.skynews.com/feeds/rss/world.xml',
            'https://feeds.nbcnews.com/nbcnews/public/news',
            'https://feeds.feedburner.com/ndtvnews-world-news',
            'https://abcnews.go.com/abcnews/internationalheadlines',
            'https://rss.dw.com/rdf/rss-en-all',
            'https://www.cbsnews.com/latest/rss/world',
            'https://rss.app/feeds/UokAeMGlNa7Cgf9j.xml'
        ]

        all_articles = {}
        for url in rss_urls:
            all_articles[url] = get_articles_from_rss(url, days_back)

        # Flatten the list of articles
        articles = [article for site_articles in all_articles.values() for article in site_articles]

        # Perform simple clustering
        clustered_articles = simple_clustering(articles)

        # Print clustering results
        for cluster_id, cluster_articles in clustered_articles.items():
            print(f"Cluster {cluster_id}:")
            print(f"Number of articles: {len(cluster_articles)}")
            print("Example articles:")
            for article in cluster_articles[:5]:  # Displaying 5 example articles
                print(f"- {article['title']}")
            print()
