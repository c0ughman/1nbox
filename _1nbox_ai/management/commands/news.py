import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from collections import Counter
import numpy as np
from gensim import corpora
from gensim.models import LdaModel
from gensim.parsing.preprocessing import STOPWORDS
import gensim

def preprocess(text):
    result = []
    for token in gensim.utils.simple_preprocess(text):
        if token not in STOPWORDS and len(token) > 3:
            result.append(token)
    return result

def cluster_articles(articles):
    contents = [article['content'] for article in articles]
    processed_docs = [preprocess(doc) for doc in contents]
    
    dictionary = corpora.Dictionary(processed_docs)
    corpus = [dictionary.doc2bow(doc) for doc in processed_docs]

    # Use coherence score to find optimal number of topics
    coherence_scores = []
    max_topics = min(20, len(articles))  # Limit max topics
    for num_topics in range(2, max_topics + 1):
        lda_model = LdaModel(corpus=corpus, id2word=dictionary, num_topics=num_topics, random_state=42)
        coherence_model = gensim.models.CoherenceModel(model=lda_model, texts=processed_docs, dictionary=dictionary, coherence='c_v')
        coherence_scores.append(coherence_model.get_coherence())
    
    optimal_num_topics = coherence_scores.index(max(coherence_scores)) + 2

    lda_model = LdaModel(corpus=corpus, id2word=dictionary, num_topics=optimal_num_topics, random_state=42)
    
    article_topics = [max(lda_model[dictionary.doc2bow(doc)], key=lambda x: x[1])[0] for doc in processed_docs]

    clustered_articles = []
    for i in range(optimal_num_topics):
        cluster_articles = [article for article, topic in zip(articles, article_topics) if topic == i]
        cluster_words = " ".join([article['content'] for article in cluster_articles])
        word_counts = Counter(cluster_words.split())
        
        # Find top words for this topic
        top_words = [word for word, _ in lda_model.show_topic(i, topn=10)]

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
        
        clustered_articles = cluster_articles(articles)

        for cluster in clustered_articles:
            print(f"Cluster {cluster['cluster_id']}:")
            print(f"Top words: {', '.join(cluster['top_words'])}")
            print(f"Number of articles: {len(cluster['articles'])}")
            print(f"Total word count: {cluster['total_word_count']}")
            print(f"Total character count: {cluster['total_char_count']}")
            print(f"Approximate OpenAI tokens: {cluster['openai_tokens']}")
            print("Example articles:")
            for article in cluster['articles'][:6]:  # Displaying 6 example articles
                print(f"- {article['title']}")
            print()
