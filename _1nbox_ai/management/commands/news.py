import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
import re
from collections import Counter

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

def extract_significant_words(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    words = []
    for sentence in sentences:
        sentence_words = re.findall(r'\b[A-Z][a-z]{1,}\b', sentence)
        words.extend(sentence_words[1:])  # Exclude the first word of each sentence
    
    insignificant_words = set(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
                               'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                               'September', 'October', 'November', 'December'])
    words = [word for word in words if word not in insignificant_words]
    
    return list(dict.fromkeys(words))

def sort_words_by_rarity(word_list, word_counts):
    return sorted(word_list, key=lambda x: word_counts[x])

def cluster_articles(articles, common_word_threshold, top_words_to_consider):
    clusters = []
    for article in articles:
        found_cluster = False
        for cluster in clusters:
            common_words = set(article['significant_words'][:top_words_to_consider]) & set(cluster['common_words'])
            if len(common_words) >= common_word_threshold:
                cluster['articles'].append(article)
                cluster['common_words'] = list(set(cluster['common_words']) & set(article['significant_words'][:top_words_to_consider]))
                found_cluster = True
                break
        if not found_cluster:
            clusters.append({
                'common_words': article['significant_words'][:top_words_to_consider],
                'articles': [article]
            })
    return clusters

def merge_clusters(clusters, merge_threshold):
    merged = True
    while merged:
        merged = False
        for i, cluster1 in enumerate(clusters):
            for j, cluster2 in enumerate(clusters[i+1:], i+1):
                common_words = set(cluster1['common_words']) & set(cluster2['common_words'])
                if len(common_words) >= merge_threshold:
                    merged_cluster = {
                        'common_words': list(common_words),
                        'articles': cluster1['articles'] + cluster2['articles']
                    }
                    clusters[i] = merged_cluster
                    clusters.pop(j)
                    merged = True
                    break
            if merged:
                break
    return clusters

def apply_minimum_articles(clusters, min_articles):
    miscellaneous_cluster = {'common_words': ['Miscellaneous'], 'articles': []}
    valid_clusters = []

    for cluster in clusters:
        if len(cluster['articles']) >= min_articles:
            valid_clusters.append(cluster)
        else:
            miscellaneous_cluster['articles'].extend(cluster['articles'])

    if miscellaneous_cluster['articles']:
        valid_clusters.append(miscellaneous_cluster)

    return valid_clusters

def print_clusters(clusters):
    for i, cluster in enumerate(clusters):
        print(f"CLUSTER {i+1} {{{', '.join(cluster['common_words'])}}}")
        print(f"Number of articles: {len(cluster['articles'])}")
        for article in cluster['articles']:
            print(f"{article['title']}")
            print(f"Significant Words: {', '.join(article['significant_words'])}")
            print()
        print()

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds, analyze significant words, and cluster articles'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--common_word_threshold', type=int, default=2, help='Number of common words required for clustering')
        parser.add_argument('--top_words_to_consider', type=int, default=3, help='Number of top words to consider for clustering')
        parser.add_argument('--merge_threshold', type=int, default=2, help='Number of common words required to merge clusters')
        parser.add_argument('--min_articles', type=int, default=3, help='Minimum number of articles per cluster')

    def handle(self, *args, **options):
        days_back = options['days']
        common_word_threshold = options['common_word_threshold']
        top_words_to_consider = options['top_words_to_consider']
        merge_threshold = options['merge_threshold']
        min_articles = options['min_articles']

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

        all_articles = []
        for url in rss_urls:
            all_articles.extend(get_articles_from_rss(url, days_back))

        # Extract and count significant words
        word_counts = Counter()
        for article in all_articles:
            title_words = extract_significant_words(article['title'])
            content_words = extract_significant_words(article['content'])
            article['significant_words'] = title_words + [w for w in content_words if w not in title_words]
            word_counts.update(article['significant_words'])

        # Sort words by rarity for each article
        for article in all_articles:
            article['significant_words'] = sort_words_by_rarity(article['significant_words'], word_counts)

        # Cluster articles
        clusters = cluster_articles(all_articles, common_word_threshold, top_words_to_consider)

        # Merge clusters
        merged_clusters = merge_clusters(clusters, merge_threshold)

        # Apply minimum articles per cluster
        final_clusters = apply_minimum_articles(merged_clusters, min_articles)

        # Print results
        print_clusters(final_clusters)
