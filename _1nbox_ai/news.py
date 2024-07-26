import feedparser
from datetime import datetime, timedelta
import pytz

def get_articles_from_rss(rss_url, days_back=1):
    """
    Fetch articles from an RSS feed within a specified timeframe.
    """
    feed = feedparser.parse(rss_url)
    articles = []
    cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
    
    for entry in feed.entries:
        # Parse the published date
        pub_date = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
        
        if pub_date >= cutoff_date:
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': pub_date,
                'summary': entry.summary if 'summary' in entry else '',
                'content': entry.content[0].value if 'content' in entry else entry.summary
            })
    
    return articles

def get_articles_from_multiple_sources(rss_urls, days_back=1):
    """
    Fetch articles from multiple RSS feeds.
    """
    all_articles = {}
    for url in rss_urls:
        articles = get_articles_from_rss(url, days_back)
        all_articles[url] = articles
    return all_articles

# List of 10 RSS feed URLs focused on politics
rss_urls = [
    'http://rss.cnn.com/rss/cnn_allpolitics.rss',
    'https://feeds.nbcnews.com/nbcnews/public/politics',
    'http://feeds.foxnews.com/foxnews/politics',
    'http://feeds.washingtonpost.com/rss/politics',
    'https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml',
    'https://www.politico.com/rss/politics.xml',
    'https://thehill.com/homenews/feed/',
    'https://www.npr.org/rss/rss.php?id=1014',
    'http://feeds.bbci.co.uk/news/politics/rss.xml',
    'https://rssfeeds.usatoday.com/UsatodaycomWashington-TopStories'
]

# Fetch articles
all_articles = get_articles_from_multiple_sources(rss_urls, days_back=1)

# Process and print statistics
total_articles = 0
articles_per_site = {}
all_article_list = []

for url, articles in all_articles.items():
    num_articles = len(articles)
    total_articles += num_articles
    articles_per_site[url] = num_articles
    all_article_list.extend(articles)

# Find smallest and largest articles
if all_article_list:
    smallest_article = min(all_article_list, key=lambda x: len(x['content']))
    largest_article = max(all_article_list, key=lambda x: len(x['content']))

# Print statistics
print(f"Total number of articles: {total_articles}")
print("\nNumber of articles per site:")
for url, count in articles_per_site.items():
    print(f"{url}: {count}")

if all_article_list:
    print(f"\nSmallest article: '{smallest_article['title']}' ({len(smallest_article['content'])} characters)")
    print(f"Largest article: '{largest_article['title']}' ({len(largest_article['content'])} characters)")

    print("\n10 sample article titles:")
    for article in all_article_list[:10]:
        print(f"- {article['title']}")
else:
    print("\nNo articles found in the specified timeframe.")
