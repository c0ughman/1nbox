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
        words = re.findall(r'\b[A-Z][a-z]*\b', content) + re.findall(r'\b[A-Z][a-z]*\b', title)
        all_words.extend(words)
        article_words.append(words)

    word_freq = Counter(word.lower() for word in all_words)
    return [clean_and_sort_words(words, word_freq) for words in article_words]

def print_article_info(articles):
    capitalized_words_list = extract_capitalized_words(articles)
    for article, capitalized_words in zip(articles, capitalized_words_list):
        print(article['title'])
        print(f"Capitalized Words: {capitalized_words}")
        print()

class Command(BaseCommand):
    help = 'Fetch articles from RSS feeds and print titles and capitalized words'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Number of days to look back')

    def handle(self, *args, **options):
        days_back = options['days']

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

        print_article_info(all_articles)

