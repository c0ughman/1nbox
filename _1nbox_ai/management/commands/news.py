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
    for sentence in sentences:
        sentence_words = sentence.strip().split()
        if len(sentence_words) > 1:
            words.extend([word for word in sentence_words[1:] if word.istitle()])
    return words

def calculate_similarity(set1, set2):
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union) if union else 0

def merge_clusters(clusters):
    while len(clusters) > 10:
        max_similarity = 0
        merge_pair = None
        for i, j in combinations(range(len(clusters)), 2):
            similarity = calculate_similarity(clusters[i]['common_words'], clusters[j]['common_words'])
            if similarity > max_similarity:
                max_similarity = similarity
                merge_pair = (i, j)
        
        if merge_pair is None:
            break
        
        i, j = merge_pair
        new_cluster = {
            'articles': clusters[i]['articles'] + clusters[j]['articles'],
            'common_words': clusters[i]['common_words'].intersection(clusters[j]['common_words'])
        }
        new_cluster['avg_strength'] = calculate_avg_strength(new_cluster)
        
        clusters = [cluster for k, cluster in enumerate(clusters) if k not in merge_pair]
        clusters.append(new_cluster)
    
    return clusters

def calculate_avg_strength(cluster):
    strengths = []
    for article in cluster['articles']:
        article_words_set = set(extract_capitalized_words(article['content']))
        strength = len(cluster['common_words'].intersection(article_words_set)) / len(article_words_set)
        strengths.append(strength)
    return sum(strengths) / len(strengths) if strengths else 0

def simple_clustering(articles, min_word_freq=5, max_word_freq=0.3, similarity_threshold=0.3, min_cluster_size=5, min_common_words=5):
    all_words = []
    article_words = {}
    for article in articles:
        words = set(extract_capitalized_words(article['content']))
        all_words.extend(words)
        article_words[article['title']] = words
    
    word_counts = Counter(all_words)
    total_articles = len(articles)
    
    valid_words = set([word for word, count in word_counts.items() 
                       if min_word_freq <= count <= total_articles * max_word_freq])
    
    clusters = []
    miscellaneous = []
    
    for article in articles:
        article_valid_words = article_words[article['title']].intersection(valid_words)
        if len(article_valid_words) < min_common_words:
            miscellaneous.append(article)
        else:
            added_to_cluster = False
            for cluster in clusters:
                similarity = calculate_similarity(article_valid_words, cluster['common_words'])
                if similarity >= similarity_threshold:
                    cluster['articles'].append(article)
                    cluster['common_words'].intersection_update(article_valid_words)
                    added_to_cluster = True
                    break
            
            if not added_to_cluster:
                clusters.append({
                    'articles': [article],
                    'common_words': article_valid_words
                })
    
    # Remove small clusters and clusters with few common words
    for cluster in clusters[:]:
        if len(cluster['articles']) < min_cluster_size or len(cluster['common_words']) < min_common_words:
            miscellaneous.extend(cluster['articles'])
            clusters.remove(cluster)
    
    # Calculate cluster strength
    for cluster in clusters:
        cluster['avg_strength'] = calculate_avg_strength(cluster)
    
    # Merge clusters until we have 10 or fewer
    clusters = merge_clusters(clusters)
    
    # Sort clusters by size and strength
    clusters.sort(key=lambda x: (len(x['articles']), x['avg_strength']), reverse=True)
    
    # Add miscellaneous cluster
    if miscellaneous:
        clusters.append({
            'articles': miscellaneous,
            'common_words': set(['Various topics']),
            'avg_strength': 0
        })
    
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
        for i, cluster in enumerate(clustered_articles, 1):
            print(f"Cluster {i}:")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Common words: {', '.join(cluster['common_words'])}")
            print(f"Average cluster strength: {cluster['avg_strength']:.2%}")
            print("Example articles:")
            for article in cluster['articles'][:5]:  # Displaying 5 example articles
                print(f"- {article['title']}")
            print()
