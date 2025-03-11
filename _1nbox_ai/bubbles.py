import feedparser
import requests
import re
import pytz
from datetime import datetime, timedelta
import logging
from collections import Counter, defaultdict
import concurrent.futures
import json
from bs4 import BeautifulSoup

def get_publication_date(entry):
    """Attempt to parse and return a datetime for an RSS entry."""
    if 'published_parsed' in entry:
        return datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
    elif 'updated_parsed' in entry:
        return datetime(*entry.updated_parsed[:6], tzinfo=pytz.utc)
    else:
        return None

def extract_links_from_description(description):
    """Extracts all links and corresponding text from an article's description."""
    extracted_articles = []
    if description:
        soup = BeautifulSoup(description, 'html.parser')
        for link in soup.find_all('a', href=True):
            title = link.text.strip()
            href = link['href'].strip()
            if title and href:
                extracted_articles.append({"title": title, "link": href})
    return extracted_articles

def get_articles_from_rss(rss_url, days_back=1):
    """Fetch articles from a single RSS URL."""
    try:
        response = requests.get(rss_url, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        
        if not hasattr(feed, 'entries'):
            return []
        
        cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
        articles = []
        
        for entry in feed.entries:
            pub_date = get_publication_date(entry)
            if not pub_date or pub_date < cutoff_date:
                continue
            
            if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                continue
            
            main_article = {"title": entry.title, "link": entry.link}
            articles.append(main_article)
            
            if hasattr(entry, 'description'):
                additional_articles = extract_links_from_description(entry.description)
                articles.extend(additional_articles)
        
        return articles
    except Exception as e:
        logging.error(f"Error fetching {rss_url}: {e}")
        return []

def fetch_rss_parallel(urls, days_back):
    """Fetch multiple RSS feeds in parallel."""
    all_articles = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_articles_from_rss, url, days_back): url for url in urls}
        for future in concurrent.futures.as_completed(futures):
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as e:
                logging.error(f"Fetching error: {e}")
    return all_articles

def extract_capitalized_words(text):
    """Extract capitalized words from a given text."""
    return re.findall(r'\b[A-Z][a-z]+\b', text)

def rank_common_words(articles):
    """Find and rank the most common capitalized words across all article titles."""
    word_counts = Counter()
    
    for article in articles:
        words = extract_capitalized_words(article['title'])
        word_counts.update(words)
    
    return sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

def cluster_articles(articles, min_articles_per_cluster):
    """Cluster articles hierarchically based on common capitalized words."""
    ranked_words = rank_common_words(articles)
    clusters = []
    unclustered_articles = set(articles)
    
    for word, count in ranked_words:
        cluster = {"word": word, "articles": [], "subclusters": []}
        
        for article in list(unclustered_articles):
            if word in extract_capitalized_words(article['title']):
                cluster["articles"].append(article)
                unclustered_articles.remove(article)
                
        if len(cluster["articles"]) >= min_articles_per_cluster:
            clusters.append(cluster)
    
    if unclustered_articles:
        clusters.append({"word": "Miscellaneous", "articles": list(unclustered_articles), "subclusters": []})
    
    for cluster in clusters:
        ranked_subwords = rank_common_words(cluster["articles"])
        subclusters = []
        unclustered_articles = set(cluster["articles"])
        
        for subword, count in ranked_subwords:
            subcluster = {"word": subword, "articles": [], "subclusters": []}
            
            for article in list(unclustered_articles):
                if subword in extract_capitalized_words(article['title']):
                    subcluster["articles"].append(article)
                    unclustered_articles.remove(article)
                    
            if len(subcluster["articles"]) >= min_articles_per_cluster:
                subclusters.append(subcluster)
        
        if unclustered_articles:
            subclusters.append({"word": "Miscellaneous", "articles": list(unclustered_articles), "subclusters": []})
        
        cluster["subclusters"] = subclusters
    
    return clusters

def process_and_cluster_articles(
    rss_urls,
    days_back=1,
    common_word_threshold=2,      # not currently used
    top_words_to_consider=3,      # not currently used
    merge_threshold=2,            # not currently used
    min_articles=2,               # used for min_articles_per_cluster
    join_percentage=0.5,          # not currently used
    final_merge_percentage=0.5,   # not currently used
    title_only=False,             # not currently used
    all_words=False               # not currently used
):    """Fetch articles and apply hierarchical clustering."""
    all_articles = fetch_rss_parallel(rss_urls, days_back)
    return cluster_articles(all_articles, min_articles_per_cluster)

def process_feeds_and_cluster(rss_urls, days_back=1, min_articles_per_cluster=2):
    """Generate a JSON structure from clustered articles."""
    clustered_data = process_and_cluster_articles(rss_urls, days_back, min_articles_per_cluster)
    return json.dumps({"clusters": clustered_data}, indent=4)
