import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
import re
from collections import Counter, defaultdict

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

def clean_and_sort_words(words, word_freq):
    days_of_week = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    months = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"}
    
    words = set(words)
    words = [word for word in words if len(word) > 1 and word not in days_of_week and word not in months]
    return sorted(words, key=lambda word: word_freq[word.lower()])

def extract_capitalized_words(articles):
    all_words = []
    article_words = []

    for article in articles:
        content = article['content']
        title = article['title']
        
        # Find all capitalized words
        words_in_title = re.findall(r'\b[A-Z][a-z]*\b', title)
        words_in_content = re.findall(r'\b[A-Z][a-z]*\b', content)
        
        # Remove words at the beginning of sentences and paragraphs in content
        words_in_content = [
            word for word in words_in_content 
            if not re.search(r'(?:^|\.\s+|\n\s*)' + word, content)
        ]
        
        all_words.extend(words_in_content + words_in_title)
        article_words.append(words_in_content + words_in_title)

    word_freq = Counter(word.lower() for word in all_words)
    return [clean_and_sort_words(words, word_freq) for words in article_words]

def print_article_info(articles, common_word_count, capitalized_word_range):
    capitalized_words_list = extract_capitalized_words(articles)

    # First level clustering
    first_level_clusters = defaultdict(list)
    for article, capitalized_words in zip(articles, capitalized_words_list):
        key = tuple(capitalized_words[:capitalized_word_range])
        first_level_clusters[key].append((article['title'], capitalized_words))

    # Print clusters
    printed_clusters = set()
    for key, articles in first_level_clusters.items():
        if key in printed_clusters:
            continue
        
        common_words = set(key)
        for other_key in first_level_clusters:
            if key == other_key or other_key in printed_clusters:
                continue
            if len(common_words.intersection(other_key)) >= common_word_count:
                common_words.update(other_key)
                articles.extend(first_level_clusters[other_key])
                printed_clusters.add(other_key)
        
        if len(common_words) > 0:
            common_words_str = ' '.join(sorted(common_words))
            print(f"{{ {common_words_str.upper()} }} CLUSTER")
            for title, words in articles:
                print(title)
                print(f"Capitalized Words: {words}")
            print()
        printed_clusters.add(key)

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds and print titles and capitalized words'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
        parser.add_argument('--common-word-count', type=int, default=2, help='Minimum number of common words for clustering')
        parser.add_argument('--capitalized-word-range', type=int, default=3, help='Range of capitalized words to consider for clustering')

    def handle(self, *args, **options):
        days_back = options['days']
        common_word_count = options['common_word_count']
        capitalized_word_range = options['capitalized_word_range']

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

        print_article_info(all_articles, common_word_count, capitalized_word_range)
