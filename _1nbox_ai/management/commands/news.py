import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from collections import Counter
import numpy as np
from scipy.cluster.hierarchy import dendrogram, linkage
from matplotlib import pyplot as plt

def cluster_articles(articles, num_clusters=6):
    contents = [article['content'] for article in articles]
    
    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(contents)

    num_clusters = min(num_clusters, len(contents))
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    kmeans.fit(X)

    feature_names = vectorizer.get_feature_names_out()
    clustered_articles = []
    for i in range(num_clusters):
        cluster_articles = [article for article, label in zip(articles, kmeans.labels_) if label == i]
        cluster_words = " ".join([article['content'] for article in cluster_articles])
        word_counts = Counter(cluster_words.split())
        
        # Find unique words for this cluster
        unique_words = set(word_counts.keys())
        for j in range(num_clusters):
            if j != i:
                other_cluster_words = " ".join([article['content'] for article, label in zip(articles, kmeans.labels_) if label == j])
                unique_words -= set(other_cluster_words.split())
        
        top_words = [word for word in unique_words if word in feature_names][:10]

        total_word_count = sum(len(article['content'].split()) for article in cluster_articles)
        total_char_count = sum(len(article['content']) for article in cluster_articles)
        openai_tokens = total_char_count // 4  # Approximate conversion

        clustered_articles.append({
            'cluster_id': i+1,
            'top_words': top_words,
            'articles': cluster_articles,
            'total_word_count': total_word_count,
            'total_char_count': total_char_count,
            'openai_tokens': openai_tokens
        })

    return clustered_articles

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
            "https://feeds.npr.org/1014/rss.xml",
            "https://www.theatlantic.com/feed/channel/politics/",
            "https://www.politico.com/rss/politics.xml",
            "https://fivethirtyeight.com/politics/feed/",
            "https://thehill.com/homenews/feed/",
            "https://www.vox.com/rss/policy-and-politics/index.xml",
            "https://www.motherjones.com/politics/feed/",
            "https://reason.com/latest/feed/",
            "https://newrepublic.com/rss.xml",
            "https://washingtonmonthly.com/feed/"
        ]


        # Fetch articles
        all_articles, all_deleted_articles = get_articles_from_multiple_sources(rss_urls, days_back)

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
        
        clustered_articles = cluster_articles(articles)

        for cluster in clustered_articles:
            print(f"Cluster {cluster['cluster_id']}:")
            print(f"Top unique words: {', '.join(cluster['top_words'])}")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Total word count: {cluster['total_word_count']}")
            print(f"Total character count: {cluster['total_char_count']}")
            print(f"Approximate OpenAI tokens: {cluster['openai_tokens']}")
            print("Example articles:")
            for article in cluster['articles'][:3]:
                print(f"- {article['title']}")
            print()

        # Visualize cluster hierarchy
        X = TfidfVectorizer(stop_words='english', max_features=1000, ngram_range=(1, 2)).fit_transform([article['content'] for article in articles])
        linkage_matrix = linkage(X.toarray(), method='ward')
        plt.figure(figsize=(10, 7))
        dendrogram(linkage_matrix)
        plt.title('Hierarchical Clustering Dendrogram')
        plt.xlabel('Article Index')
        plt.ylabel('Distance')
        plt.savefig('cluster_dendrogram.png')
        print("Cluster dendrogram saved as 'cluster_dendrogram.png'")
