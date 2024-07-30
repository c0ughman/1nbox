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
import warnings

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

def preprocess(text):
    return ' '.join([word.lower() for word in re.findall(r'\w+', text)])

def extract_key_topics(articles, top_n=50):
    all_text = ' '.join([article['content'] for article in articles])
    doc = nlp(all_text)
    
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
    cluster_vectors_dense = np.array([v.toarray()[0] for v in cluster_vectors])
    similarities = cosine_similarity(cluster_vectors_dense)
    return np.mean(similarities)

def cluster_articles(articles, max_features=1000, min_df=0.01, max_df=0.5, n_clusters=None, min_cluster_size=5, similarity_threshold=0.3):
    key_topics = extract_key_topics(articles)
    vectorizer = TfidfVectorizer(vocabulary=key_topics, max_df=max_df, min_df=min_df, lowercase=False)
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
        top_word_indices = cluster_tfidf.argsort()[0, -5:].tolist()[0]
        top_words = [feature_names[i] for i in top_word_indices]
        
        total_word_count = sum(len(article['content'].split()) for article in cluster_articles)
        total_char_count = sum(len(article['content']) for article in cluster_articles)
        openai_tokens = total_char_count // 4
        
        result.append({
            'cluster_id': cluster_id + 1,
            'top_words': top_words,
            'articles': cluster_articles,
            'total_word_count': total_word_count,
            'total_char_count': total_char_count,
            'openai_tokens': openai_tokens,
            'similarity_score': similarity_score
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
            'similarity_score': 0.0
        })
    
    return result

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
            print(f"Warning: Missing date for entry '{entry.title}'")

    return articles

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

        rss_urls = [
            'https://rss.cnn.com/rss/edition.rss',
            'https://feeds.bbci.co.uk/news/rss.xml',
            'http://feeds.reuters.com/reuters/topNews',
            'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
            'https://www.theguardian.com/world/rss',
            # Add more RSS feed URLs here
        ]

        all_articles = []
        for url in rss_urls:
            all_articles.extend(get_articles_from_rss(url, days_back))

        clustered_articles = cluster_articles(
            all_articles,
            min_df=min_df,
            max_df=max_df,
            n_clusters=n_clusters,
            min_cluster_size=min_cluster_size,
            similarity_threshold=similarity_threshold
        )

        for cluster in clustered_articles:
            print(f"Cluster {cluster['cluster_id']}:")
            print(f"Top words: {', '.join(cluster['top_words'])}")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Total word count: {cluster['total_word_count']}")
            print(f"Total character count: {cluster['total_char_count']}")
            print(f"Approximate OpenAI tokens: {cluster['openai_tokens']}")
            print(f"Similarity score: {cluster['similarity_score']:.4f}")
            print("Example articles:")
            for article in cluster['articles'][:6]:
                print(f"- {article['title']}")
            print()

if __name__ == '__main__':
    Command().handle()
