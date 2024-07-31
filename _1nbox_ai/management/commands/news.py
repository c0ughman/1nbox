import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans, DBSCAN
from sklearn.preprocessing import normalize
from sklearn.metrics.pairwise import cosine_similarity
from collections import defaultdict, Counter
import re
import spacy
import numpy as np
from hdbscan import HDBSCAN

nlp = spacy.load("en_core_web_sm")

def preprocess(text):
    return ' '.join([word.lower() for word in re.findall(r'\w+', text)])

def extract_key_topics(articles, top_n=100):  # Increased from 50 to 100
    all_text = ' '.join([article['content'] for article in articles])
    doc = nlp(all_text)
    entities = [ent.text.lower() for ent in doc.ents if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT']]
    nouns = [token.text.lower() for token in doc if token.pos_ == 'NOUN']
    key_words = Counter(entities + nouns)
    common_words = set(['said', 'year', 'day', 'time', 'people', 'way', 'man', 'woman'])
    key_topics = [word for word, count in key_words.most_common(top_n) 
                  if word not in common_words and len(word) > 1]
    return key_topics

def reassign_low_similarity_articles(clustered_articles, tfidf_matrix, cluster_labels, centroids, similarity_threshold=0.1):
    miscellaneous_cluster = []
    
    for cluster in clustered_articles:
        if cluster['cluster_id'] == 'Miscellaneous':
            continue
        
        cluster_articles = cluster['articles']
        cluster_matrix = tfidf_matrix[cluster_labels == cluster['cluster_id']]
        centroid = centroids[cluster['cluster_id']]
        
        similarities = cosine_similarity(cluster_matrix, centroid.reshape(1, -1)).flatten()
        
        new_cluster_articles = []
        for article, similarity in zip(cluster_articles, similarities):
            if similarity >= similarity_threshold:
                new_cluster_articles.append(article)
            else:
                miscellaneous_cluster.append(article)
        
        cluster['articles'] = new_cluster_articles
    
    # Add or update the miscellaneous cluster
    misc_cluster = next((c for c in clustered_articles if c['cluster_id'] == 'Miscellaneous'), None)
    if misc_cluster:
        misc_cluster['articles'].extend(miscellaneous_cluster)
    else:
        clustered_articles.append({
            'cluster_id': 'Miscellaneous',
            'top_words': ['miscellaneous'],
            'articles': miscellaneous_cluster,
            'total_word_count': sum(len(article['content'].split()) for article in miscellaneous_cluster),
            'total_char_count': sum(len(article['content']) for article in miscellaneous_cluster),
            'openai_tokens': sum(len(article['content']) for article in miscellaneous_cluster) // 4,
        })
    
    return clustered_articles

def cluster_articles(articles, max_features=1000, min_df=0.01, max_df=0.5, n_clusters=None, min_cluster_size=5):
    key_topics = extract_key_topics(articles)
    vectorizer = TfidfVectorizer(vocabulary=key_topics, max_df=max_df, min_df=min_df)
    tfidf_matrix = vectorizer.fit_transform([article['content'] for article in articles])
    tfidf_matrix = normalize(tfidf_matrix, norm='l2', axis=1)
    
    if n_clusters is None:
        n_clusters = min(20, len(articles) // 10)
    
    # Try HDBSCAN first
    hdbscan = HDBSCAN(min_cluster_size=min_cluster_size, min_samples=1)
    cluster_labels = hdbscan.fit_predict(tfidf_matrix)
    
    # If HDBSCAN doesn't work well (too many noise points), fall back to MiniBatchKMeans
    if (cluster_labels == -1).sum() / len(cluster_labels) > 0.5:
        kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=1000)
        cluster_labels = kmeans.fit_predict(tfidf_matrix)
        centroids = kmeans.cluster_centers_
    else:
        centroids = np.array([tfidf_matrix[cluster_labels == i].mean(axis=0).A1 
                              for i in range(cluster_labels.max() + 1)])
    
    clustered_articles = defaultdict(list)
    for article, label in zip(articles, cluster_labels):
        clustered_articles[label].append(article)
    
    result = []
    feature_names = vectorizer.get_feature_names_out()
    miscellaneous_cluster = []
    
    for cluster_id, cluster_articles in clustered_articles.items():
        if cluster_id == -1 or len(cluster_articles) < min_cluster_size:
            miscellaneous_cluster.extend(cluster_articles)
            continue
        
        cluster_tfidf = tfidf_matrix[cluster_labels == cluster_id]
        top_word_indices = cluster_tfidf.sum(0).argsort()[0, -5:].tolist()[0]
        top_words = [feature_names[i] for i in top_word_indices]
        
        total_word_count = sum(len(article['content'].split()) for article in cluster_articles)
        total_char_count = sum(len(article['content']) for article in cluster_articles)
        openai_tokens = total_char_count // 4
        
        result.append({
            'cluster_id': cluster_id,
            'top_words': top_words,
            'articles': cluster_articles,
            'total_word_count': total_word_count,
            'total_char_count': total_char_count,
            'openai_tokens': openai_tokens,
        })
    
    if miscellaneous_cluster:
        total_word_count = sum(len(article['content'].split()) for article in miscellaneous_cluster)
        total_char_count = sum(len(article['content']) for article in miscellaneous_cluster)
        openai_tokens = total_char_count // 4
        
        result.append({
            'cluster_id': 'Miscellaneous',
            'top_words': ['miscellaneous'],
            'articles': miscellaneous_cluster,
            'total_word_count': total_word_count,
            'total_char_count': total_char_count,
            'openai_tokens': openai_tokens,
        })
    
    result = reassign_low_similarity_articles(result, tfidf_matrix, cluster_labels, centroids)
    
    return result


def determine_optimal_clusters(tfidf_matrix, max_clusters):
    inertias = []
    for k in range(2, max_clusters + 1):
        kmeans = KMeans(n_clusters=k, random_state=42)
        kmeans.fit(tfidf_matrix)
        inertias.append(kmeans.inertia_)
    
    # Find elbow point
    optimal_clusters = 2
    for i in range(1, len(inertias) - 1):
        if (inertias[i-1] - inertias[i]) / (inertias[i] - inertias[i+1]) < 0.5:
            optimal_clusters = i + 2
            break
    
    return optimal_clusters

def calculate_dataset_stats(all_articles):
    total_articles = sum(len(articles) for articles in all_articles.values())
    articles_per_source = {url: len(articles) for url, articles in all_articles.items()}
    avg_article_size_per_source = {url: sum(len(article['content']) for article in articles) / len(articles) if articles else 0 
                                   for url, articles in all_articles.items()}
    avg_article_size_general = sum(len(article['content']) for articles in all_articles.values() for article in articles) / total_articles if total_articles else 0
    
    return {
        'total_articles': total_articles,
        'articles_per_source': articles_per_source,
        'avg_article_size_per_source': avg_article_size_per_source,
        'avg_article_size_general': avg_article_size_general
    }

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds, cluster them, and display statistics'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--min-df', type=float, default=0.01, help='Minimum document frequency for TF-IDF')
        parser.add_argument('--max-df', type=float, default=0.5, help='Maximum document frequency for TF-IDF')
        parser.add_argument('--n-clusters', type=int, help='Number of clusters (if not specified, determined automatically)')
        parser.add_argument('--min-cluster-size', type=int, default=5, help='Minimum number of articles per cluster')

    def handle(self, *args, **options):
        days_back = options['days']
        min_df = options['min_df']
        max_df = options['max_df']
        n_clusters = options['n_clusters']
        min_cluster_size = options['min_cluster_size']

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

        # List of RSS feed URLs
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

        # Calculate dataset statistics
        dataset_stats = calculate_dataset_stats(all_articles)

        # Print dataset statistics
        print("Dataset Statistics:")
        print(f"Total number of articles: {dataset_stats['total_articles']}")
        print("Number of articles per news source:")
        for source, count in dataset_stats['articles_per_source'].items():
            print(f"- {source}: {count}")
        print("Average article size per news source (in characters):")
        for source, avg_size in dataset_stats['avg_article_size_per_source'].items():
            print(f"- {source}: {avg_size:.2f}")
        print(f"Average article size in general: {dataset_stats['avg_article_size_general']:.2f} characters")
        print()

         # Clustering
        articles = [article for site_articles in all_articles.values() for article in site_articles]
        
        clustered_articles = cluster_articles(
            articles, 
            min_df=options['min_df'], 
            max_df=options['max_df'], 
            n_clusters=options['n_clusters'], 
            min_cluster_size=options['min_cluster_size']
        )

        for cluster in clustered_articles:
            print(f"Cluster {cluster['cluster_id']}:")
            print(f"Top words: {', '.join(cluster['top_words'])}")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Total word count: {cluster['total_word_count']}")
            print(f"Total character count: {cluster['total_char_count']}")
            print(f"Approximate OpenAI tokens: {cluster['openai_tokens']}")
            print("Example articles:")
            for article in cluster['articles'][:6]:
                print(f"- {article['title']}")
            print()
