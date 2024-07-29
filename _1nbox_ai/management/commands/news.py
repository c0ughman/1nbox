import calendar
import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from collections import defaultdict, Counter
import re
from itertools import combinations

def extract_capitalized_words(text):
    sentences = re.split(r'[.!?]+', text)
    words = []
    common_capitalized = set(list(calendar.month_name[1:]) + list(calendar.day_name) + ['I', 'U', 'A'])
    for sentence in sentences:
        sentence_words = sentence.strip().split()
        if len(sentence_words) > 1:
            words.extend([word for word in sentence_words[1:] if word.istitle() and word not in common_capitalized and len(word) > 1])
    return words

def calculate_similarity(set1, set2):
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union) if union else 0

def merge_clusters(clusters, max_clusters, min_common_words):
    while len(clusters) > max_clusters:
        best_merge = (0, 0, 0)
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                common_words = len(clusters[i]['common_words'].intersection(clusters[j]['common_words']))
                if common_words > best_merge[2]:
                    best_merge = (i, j, common_words)
        
        if best_merge[2] < min_common_words:
            break
        
        i, j, _ = best_merge
        new_cluster = {
            'articles': clusters[i]['articles'] + clusters[j]['articles'],
            'common_words': clusters[i]['common_words'].intersection(clusters[j]['common_words'])
        }
        clusters = [cluster for k, cluster in enumerate(clusters) if k not in (i, j)]
        clusters.append(new_cluster)
    
    return clusters

def simple_clustering(articles, min_word_freq=3, max_word_freq=30, min_common_words=3, max_clusters=10, misc_threshold=2):
    all_words = []
    article_words = {}
    for article in articles:
        words = set(extract_capitalized_words(article['content']))
        all_words.extend(words)
        article_words[article['title']] = words
    
    word_counts = Counter(all_words)
    total_articles = len(articles)
    
    valid_words = set([word for word, count in word_counts.items() 
                       if min_word_freq <= count <= max_word_freq])
    
    # Initial clustering
    clusters = []
    for article in articles:
        article_valid_words = article_words[article['title']].intersection(valid_words)
        best_cluster = None
        best_common_words = 0
        
        for cluster in clusters:
            common_words = len(article_valid_words.intersection(cluster['common_words']))
            if common_words > best_common_words:
                best_common_words = common_words
                best_cluster = cluster
        
        if best_common_words >= min_common_words:
            best_cluster['articles'].append(article)
            best_cluster['common_words'].intersection_update(article_valid_words)
        else:
            clusters.append({
                'articles': [article],
                'common_words': article_valid_words
            })
    
    # Merge similar clusters
    clusters = merge_clusters(clusters, max_clusters, min_common_words)
    
    # Miscellaneous cluster
    misc_cluster = {'articles': [], 'common_words': set()}

    # Filter clusters and move small clusters to miscellaneous
    final_clusters = []
    for cluster in clusters:
        if len(cluster['articles']) >= misc_threshold:
            final_clusters.append(cluster)
        else:
            misc_cluster['articles'].extend(cluster['articles'])
    
    # Calculate cluster strength
    for cluster in final_clusters:
        cluster['avg_strength'] = calculate_avg_strength(cluster, article_words)
    
    # Sort clusters by size and strength
    final_clusters.sort(key=lambda x: (len(x['articles']), x['avg_strength']), reverse=True)

    # Add the miscellaneous cluster at the end if it contains any articles
    if misc_cluster['articles']:
        misc_cluster['avg_strength'] = 0
        final_clusters.append(misc_cluster)

    return final_clusters

def calculate_avg_strength(cluster, article_words):
    strengths = []
    for article in cluster['articles']:
        article_words_set = article_words[article['title']]
        if article_words_set:  # Only proceed if article_words_set is not empty
            strength = len(cluster['common_words'].intersection(article_words_set)) / len(article_words_set)
            strengths.append(strength)
    return sum(strengths) / len(strengths) if strengths else 0

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds and display statistics'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--min_word_freq', type=int, default=3, help='Minimum word frequency across all articles')
        parser.add_argument('--max_word_freq', type=int, default=30, help='Maximum word frequency across all articles')
        parser.add_argument('--min_common_words', type=int, default=3, help='Minimum number of common words for clustering')
        parser.add_argument('--max_clusters', type=int, default=10, help='Maximum number of clusters')
        parser.add_argument('--misc_threshold', type=int, default=2, help='Minimum cluster size before moving to miscellaneous')

    def handle(self, *args, **options):
        days_back = options['days']
        min_word_freq = options['min_word_freq']
        max_word_freq = options['max_word_freq']
        min_common_words = options['min_common_words']
        max_clusters = options['max_clusters']
        misc_threshold = options['misc_threshold']

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

        articles = [article for site_articles in all_articles.values() for article in site_articles]

        clustered_articles = simple_clustering(articles, min_word_freq=min_word_freq, max_word_freq=max_word_freq, min_common_words=min_common_words, max_clusters=max_clusters, misc_threshold=misc_threshold)

        for i, cluster in enumerate(clustered_articles, 1):
            print(f"Cluster {i}:")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Common words: {', '.join(cluster['common_words'])}")
            print(f"Average strength: {cluster['avg_strength']:.2f}")
            print("Articles:")
            for article in cluster['articles']:
                print(f"- {article['title']} ({article['link']})")
            print("\n")
