import calendar
import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from collections import defaultdict, Counter
import re
from itertools import combinations
import math
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def extract_capitalized_words(text):
    sentences = re.split(r'[.!?]+', text)
    words = []
    common_capitalized = set(list(calendar.month_name[1:]) + list(calendar.day_name) + ['I', 'U', 'A'])
    for sentence in sentences:
        sentence_words = sentence.strip().split()
        if len(sentence_words) > 1:
            words.extend([word for word in sentence_words[1:] if word.istitle() and word not in common_capitalized and len(word) > 1])
    return words

def calculate_tfidf(word_counts, total_docs):
    word_tfidf = {}
    for word, count in word_counts.items():
        tf = count
        idf = math.log(total_docs / (count + 1))
        word_tfidf[word] = tf * idf
    return word_tfidf

def vectorize_article(article, word_tfidf, all_words):
    article_words = set(extract_capitalized_words(article['content']))
    vector = [word_tfidf.get(word, 0) if word in article_words else 0 for word in all_words]
    return vector

def cluster_articles(articles, n_clusters=10):
    # Preprocessing
    all_words = []
    word_counts = Counter()
    for article in articles:
        words = extract_capitalized_words(article['content'])
        all_words.extend(words)
        word_counts.update(words)

    # Word Weighting
    word_tfidf = calculate_tfidf(word_counts, len(articles))
    all_words = list(word_tfidf.keys())

    # Article Vectorization
    article_vectors = [vectorize_article(article, word_tfidf, all_words) for article in articles]

    # Initial Clustering
    kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42)
    initial_clusters = kmeans.fit_predict(article_vectors)

    # Refined Clustering
    final_clusters = [[] for _ in range(n_clusters)]
    for i, cluster in enumerate(initial_clusters):
        final_clusters[cluster].append(i)

    # Post-processing
    merged_clusters = merge_similar_clusters(final_clusters, article_vectors)
    
    # Prepare results
    clustered_articles = []
    for cluster in merged_clusters:
        cluster_articles = [articles[i] for i in cluster]
        common_words = set.intersection(*[set(extract_capitalized_words(article['content'])) for article in cluster_articles])
        clustered_articles.append({
            'articles': cluster_articles,
            'common_words': common_words,
            'avg_strength': calculate_avg_strength(cluster_articles, common_words)
        })

    # Sort clusters by size and strength
    clustered_articles.sort(key=lambda x: (len(x['articles']), x['avg_strength']), reverse=True)

    return clustered_articles

def merge_similar_clusters(clusters, vectors, similarity_threshold=0.5):
    merged = []
    for cluster in clusters:
        if len(cluster) == 0:
            continue
        cluster_vector = np.mean([vectors[i] for i in cluster], axis=0)
        merged_to_existing = False
        for existing_cluster in merged:
            existing_vector = np.mean([vectors[i] for i in existing_cluster], axis=0)
            if cosine_similarity([cluster_vector], [existing_vector])[0][0] > similarity_threshold:
                existing_cluster.extend(cluster)
                merged_to_existing = True
                break
        if not merged_to_existing:
            merged.append(cluster)
    return merged

def calculate_avg_strength(cluster_articles, common_words):
    strengths = []
    for article in cluster_articles:
        article_words = set(extract_capitalized_words(article['content']))
        strength = len(common_words.intersection(article_words)) / len(article_words) if article_words else 0
        strengths.append(strength)
    return sum(strengths) / len(strengths) if strengths else 0

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds and display statistics'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--n_clusters', type=int, default=10, help='Number of initial clusters')

    def handle(self, *args, **options):
        days_back = options['days']
        n_clusters = options['n_clusters']

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

        clustered_articles = cluster_articles(articles, n_clusters=n_clusters)

        for i, cluster in enumerate(clustered_articles, 1):
            print(f"Cluster {i}:")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Common words: {', '.join(cluster['common_words'])}")
            print(f"Average cluster strength: {cluster['avg_strength']:.2%}")
            print("Example articles:")
            for article in cluster['articles'][:5]:
                print(f"- {article['title']}")
            print()
