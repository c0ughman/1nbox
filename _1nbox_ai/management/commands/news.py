import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from collections import defaultdict, Counter
import re
import spacy
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

nlp = spacy.load("en_core_web_sm")

def preprocess(text):
    return ' '.join([word.lower() for word in re.findall(r'\w+', text)])

def extract_key_topics(articles, top_n=50):
    all_text = ' '.join([article['content'] for article in articles])
    doc = nlp(all_text)
    
    # Prioritize capitalized words
    capitalized_words = re.findall(r'\b(?!(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b)[A-Z][a-z]+', all_text)
    capitalized_words = [word for word in capitalized_words if len(word) > 1]
    
    entities = [ent.text for ent in doc.ents if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT']]
    nouns = [token.text for token in doc if token.pos_ == 'NOUN']
    
    key_words = Counter(capitalized_words + entities + nouns)
    common_words = set(['said', 'year', 'day', 'time', 'people', 'way', 'man', 'woman'])
    key_topics = [word for word, count in key_words.most_common(top_n) 
                  if word.lower() not in common_words and len(word) > 1]
    
    return key_topics

def calculate_cluster_similarity(cluster_vectors):
    if len(cluster_vectors) < 2:
        return 1.0
    similarities = cosine_similarity(cluster_vectors.todense())  # Convert to dense
    return np.mean(similarities)

def cluster_articles(articles, max_features=1000, min_df=0.01, max_df=0.5, n_clusters=None, min_cluster_size=5, similarity_threshold=0.3):
    key_topics = extract_key_topics(articles)
    vectorizer = TfidfVectorizer(vocabulary=key_topics, max_df=max_df, min_df=min_df)
    tfidf_matrix = vectorizer.fit_transform([article['content'] for article in articles])
    
    if n_clusters is None:
        n_clusters = min(20, len(articles) // 10)
    
    kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=1000)
    cluster_labels = kmeans.fit_predict(tfidf_matrix)
    
    clustered_articles = defaultdict(list)
    for article, label, vector in zip(articles, cluster_labels, tfidf_matrix):
        clustered_articles[label].append((article, vector))
    
    result = []
    feature_names = vectorizer.get_feature_names_out()
    miscellaneous_cluster = []
    
    for cluster_id, cluster_data in clustered_articles.items():
        cluster_articles, cluster_vectors = zip(*cluster_data)
        
        similarity_score = calculate_cluster_similarity(cluster_vectors)
        
        if len(cluster_articles) < min_cluster_size or similarity_score < similarity_threshold:
            miscellaneous_cluster.extend(cluster_articles)
            continue
        
        cluster_tfidf = np.sum(cluster_vectors, axis=0)
        top_keywords = [feature_names[i] for i in cluster_tfidf.argsort()[::-1][:10]]
        cluster_info = {
            'cluster_id': cluster_id,
            'top_keywords': top_keywords,
            'articles': [article for article, _ in cluster_data]
        }
        result.append(cluster_info)
    
    if miscellaneous_cluster:
        result.append({
            'cluster_id': 'miscellaneous',
            'top_keywords': [],
            'articles': miscellaneous_cluster
        })
    
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
        parser.add_argument('--similarity-threshold', type=float, default=0.3, help='Minimum similarity score for clusters')

    def handle(self, *args, **options):
        days_back = options['days']
        min_df = options['min_df']
        max_df = options['max_df']
        n_clusters = options['n_clusters']
        min_cluster_size = options['min_cluster_size']
        similarity_threshold = options['similarity_threshold']

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
            'https://www.nbcnews.com/id/3032091/device/rss/rss.xml',
            'https://rss.msnbc.msn.com/id/3032506/device/rss/rss.xml'
        ]

        all_articles = {url: get_articles_from_rss(url, days_back) for url in rss_urls}

        dataset_stats = calculate_dataset_stats(all_articles)
        self.stdout.write(self.style.SUCCESS('Dataset Statistics:'))
        self.stdout.write(f"Total articles: {dataset_stats['total_articles']}")
        self.stdout.write(f"Articles per source: {dataset_stats['articles_per_source']}")
        self.stdout.write(f"Average article size per source: {dataset_stats['avg_article_size_per_source']}")
        self.stdout.write(f"Average article size general: {dataset_stats['avg_article_size_general']}")

        flattened_articles = [article for articles in all_articles.values() for article in articles]
        
        clusters = cluster_articles(flattened_articles, min_df=min_df, max_df=max_df, n_clusters=n_clusters,
                                    min_cluster_size=min_cluster_size, similarity_threshold=similarity_threshold)

        self.stdout.write(self.style.SUCCESS('Clustered Articles:'))
        for cluster in clusters:
            self.stdout.write(f"Cluster ID: {cluster['cluster_id']}")
            self.stdout.write(f"Top words: {cluster['top_words']}")
            self.stdout.write(f"Number of articles: {len(cluster['articles'])}")
            self.stdout.write(f"Total word count: {cluster['total_word_count']}")
            self.stdout.write(f"Total character count: {cluster['total_char_count']}")
            self.stdout.write(f"OpenAI tokens: {cluster['openai_tokens']}")
            self.stdout.write(f"Similarity score: {cluster['similarity_score']:.2f}")
            self.stdout.write('-' * 80)

        if not n_clusters:
            tfidf_matrix = TfidfVectorizer(max_df=max_df, min_df=min_df).fit_transform([article['content'] for article in flattened_articles])
            optimal_clusters = determine_optimal_clusters(tfidf_matrix, max_clusters=20)
            self.stdout.write(self.style.SUCCESS(f'Optimal number of clusters: {optimal_clusters}'))
