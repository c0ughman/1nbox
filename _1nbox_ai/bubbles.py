import feedparser
import requests
import re
import pytz
from datetime import datetime, timedelta
import logging
from collections import Counter
import concurrent.futures
from contextlib import contextmanager
import signal

# ---------------------------------------------
#   Logging Configuration (Optional)
# ---------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# ---------------------------------------------
#   Global Timeout Context Manager
# ---------------------------------------------
@contextmanager
def timeout(seconds):
    """
    Raises TimeoutError if the block inside this
    context manager runs longer than `seconds`.
    """
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Timed out after {seconds} seconds")
    
    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

# ---------------------------------------------
#   Functions for RSS Fetching and Article Processing
# ---------------------------------------------
def get_publication_date(entry):
    """Attempt to parse and return a datetime for an RSS entry."""
    if 'published_parsed' in entry:
        return datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
    elif 'updated_parsed' in entry:
        return datetime(*entry.updated_parsed[:6], tzinfo=pytz.utc)
    elif 'published' in entry:
        # This format may vary in real feeds, so you may need more robust checks
        return datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
    elif 'updated' in entry:
        return datetime.strptime(entry.updated, '%a, %d %b %Y %H:%M:%S %Z')
    elif 'dc:date' in entry:
        return datetime.strptime(entry['dc:date'], '%Y-%m-%dT%H:%M:%SZ')
    else:
        return None

def get_articles_from_rss(rss_url, days_back=1):
    """
    Fetch articles from a single RSS URL. 
    Returns a list of article dicts with keys:
      title, link, published, summary, content, favicon
    """
    try:
        response = requests.get(rss_url, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.content)

        if hasattr(feed, 'bozo_exception'):
            logging.error(f"Feed parsing error for {rss_url}: {feed.bozo_exception}")
            return []

        if not hasattr(feed, 'entries'):
            logging.error(f"No entries found in feed for {rss_url}")
            return []

        cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
        articles = []

        for entry in feed.entries:
            try:
                pub_date = get_publication_date(entry)
                if not pub_date or pub_date < cutoff_date:
                    continue

                if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                    continue

                favicon_url = f"https://www.google.com/s2/favicons?domain={rss_url}"

                content = ""
                if hasattr(entry, 'content') and entry.content:
                    content = entry.content[0].value
                elif hasattr(entry, 'summary'):
                    content = entry.summary

                articles.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': str(pub_date),
                    'summary': getattr(entry, 'summary', ''),
                    'content': content,
                    'favicon': favicon_url,
                })
            except Exception as e:
                logging.error(f"Error processing entry in {rss_url}: {str(e)}")
                continue

        return articles
    except requests.exceptions.Timeout:
        logging.error(f"Timeout while fetching {rss_url}")
        return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for {rss_url}: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error processing {rss_url}: {str(e)}")
        return []

def fetch_rss_parallel(urls, days_back):
    """
    Fetch multiple RSS feeds in parallel. Returns:
       all_articles (list), successful_sources (list), failed_sources (list)
    """
    all_articles = []
    failed_sources = []
    successful_sources = []

    def fetch_single_url(url):
        try:
            with timeout(30):  # 30-second timeout per source
                articles = get_articles_from_rss(url, days_back)
                return (url, articles, None)
        except TimeoutError:
            return (url, None, "Timeout")
        except Exception as e:
            return (url, None, str(e))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_single_url, url): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                fetched_url, articles, error = future.result()
                if articles:
                    all_articles.extend(articles)
                    successful_sources.append(fetched_url)
                    logging.info(f"Successfully retrieved {len(articles)} articles from {fetched_url}")
                else:
                    failed_sources.append((fetched_url, error or "No articles retrieved"))
            except Exception as exc:
                logging.error(f"Processing {url} generated an exception: {exc}")
                failed_sources.append((url, str(exc)))

    return all_articles, successful_sources, failed_sources

# ---------------------------------------------
#   Clustering Functions
# ---------------------------------------------
INSIGNIFICANT_WORDS = set([
    'In', 'The', 'Continue', 'Fox', 'News', 'Newstalk', 'Newsweek', 'Is',
    # ... rest of the words ...
])

def extract_significant_words(text, title_only=False, all_words=False):
    """
    Extract significant words from text, with options for different extraction modes:
      - `title_only=True` uses only capitalized words in the text as significant.
      - `all_words=True` ignores case and extracts all words of length >= 3.
    """
    if not text:
        return []

    if all_words:
        # Extract all words >= 3 letters, ignoring case
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        # Convert them all to title-case or keep them lower? We'll keep them as found.
        # But typically you'd standardize them, e.g. `word.lower()`.
        # For clustering, do whatever works best for your needs:
        # words = [w.lower() for w in words]
    elif title_only:
        # Extract only "TitleCased" words (first letter uppercase, rest lowercase)
        words = re.findall(r'\b[A-Z][a-z]{1,}\b', text)
    else:
        # A rough approach: for each sentence, extract capitalized words (excluding first word if it's capitalized).
        sentences = re.split(r'(?<=[.!?])\s+', text)
        words = []
        for sentence in sentences:
            sentence_words = re.findall(r'\b[A-Z][a-z]{1,}\b', sentence)
            if sentence_words:
                # Skip the first word in each sentence if it's capitalized
                words.extend(sentence_words[1:])
    
    # Remove 'INSIGNIFICANT_WORDS'
    words = [word for word in words if word not in INSIGNIFICANT_WORDS]
    # Remove duplicates but preserve order
    return list(dict.fromkeys(words))

def sort_words_by_rarity(word_list, word_counts):
    """
    Sort words so that the rarest words (lowest counts) appear first.
    """
    return sorted(word_list, key=lambda x: word_counts[x])

def cluster_articles(articles, common_word_threshold, top_words_to_consider):
    """
    Initial pass at clustering articles. Two articles join the same cluster if they share
    at least `common_word_threshold` words among their top `top_words_to_consider` words.
    """
    clusters = []
    for article in articles:
        found_cluster = False
        for cluster in clusters:
            common_words = set(article['significant_words'][:top_words_to_consider]) & set(cluster['common_words'])
            if len(common_words) >= common_word_threshold:
                cluster['articles'].append(article)
                # Update the cluster's common words to the intersection
                cluster['common_words'] = list(
                    set(cluster['common_words']) & set(article['significant_words'][:top_words_to_consider])
                )
                found_cluster = True
                break
        if not found_cluster:
            clusters.append({
                'common_words': article['significant_words'][:top_words_to_consider],
                'articles': [article]
            })
    return clusters

def merge_clusters(clusters, merge_threshold):
    """
    Merge any clusters that share at least `merge_threshold` words in common.
    """
    merged = True
    while merged:
        merged = False
        i = 0
        while i < len(clusters):
            j = i + 1
            while j < len(clusters):
                common_words = set(clusters[i]['common_words']) & set(clusters[j]['common_words'])
                if len(common_words) >= merge_threshold:
                    merged_cluster = {
                        'common_words': list(common_words),
                        'articles': clusters[i]['articles'] + clusters[j]['articles']
                    }
                    clusters[i] = merged_cluster
                    clusters.pop(j)
                    merged = True
                else:
                    j += 1
            if merged:
                # Restart merging process from the beginning
                break
            i += 1
    return clusters

def calculate_match_percentage(words1, words2):
    """
    Calculate ratio of common words / number of words in words1.
    """
    common_words = set(words1) & set(words2)
    return len(common_words) / len(words1) if words1 else 0

def apply_minimum_articles_and_reassign(clusters, min_articles, join_percentage):
    """
    Any cluster with < `min_articles` articles is considered 'Miscellaneous'.
    Then we try to reassign those articles to other valid clusters if they match
    above `join_percentage`, otherwise they stay in 'Miscellaneous'.
    """
    miscellaneous_cluster = {'common_words': ['Miscellaneous'], 'articles': []}
    valid_clusters = []

    for cluster in clusters:
        if len(cluster['articles']) >= min_articles:
            valid_clusters.append(cluster)
        else:
            miscellaneous_cluster['articles'].extend(cluster['articles'])

    # Try to reassign from misc to existing clusters
    reassigned_articles = []
    for article in miscellaneous_cluster['articles']:
        for cluster in valid_clusters:
            cluster_words = [
                w for c_article in cluster['articles']
                for w in c_article['significant_words']
            ]
            if calculate_match_percentage(article['significant_words'], cluster_words) >= join_percentage:
                cluster['articles'].append(article)
                reassigned_articles.append(article)
                break

    miscellaneous_cluster['articles'] = [
        a for a in miscellaneous_cluster['articles'] if a not in reassigned_articles
    ]
    if miscellaneous_cluster['articles']:
        valid_clusters.append(miscellaneous_cluster)

    return valid_clusters

def merge_clusters_by_percentage(clusters, join_percentage):
    """
    Merge clusters if they match each other above `join_percentage`.
    """
    merged = True
    while merged:
        merged = False
        i = 0
        while i < len(clusters):
            j = i + 1
            while j < len(clusters):
                words1 = [
                    w for article in clusters[i]['articles']
                    for w in article['significant_words']
                ]
                words2 = [
                    w for article in clusters[j]['articles']
                    for w in article['significant_words']
                ]
                if (calculate_match_percentage(words1, words2) >= join_percentage and
                    calculate_match_percentage(words2, words1) >= join_percentage):
                    merged_cluster = {
                        'common_words': list(set(clusters[i]['common_words']) & set(clusters[j]['common_words'])),
                        'articles': clusters[i]['articles'] + clusters[j]['articles']
                    }
                    clusters[i] = merged_cluster
                    clusters.pop(j)
                    merged = True
                else:
                    j += 1
            if merged:
                break
            i += 1
    return clusters

# ---------------------------------------------
#   Main Clustering Workflow Function
# ---------------------------------------------
def process_feeds_and_cluster(
    rss_urls,
    days_back=1,
    common_word_threshold=2,
    top_words_to_consider=3,
    merge_threshold=2,
    min_articles=3,
    join_percentage=0.5,
    final_merge_percentage=0.5,
    title_only=False,
    all_words=False
):
    """
    High-level function that:
      1. Fetches articles from all `rss_urls` in parallel
      2. Extracts significant words for each article
      3. Clusters articles based on common words
      4. Returns `cleaned_data` (a list of cluster dicts with articles + common_words)
    """
    # 1. Fetch RSS feeds in parallel
    all_articles, successful_sources, failed_sources = fetch_rss_parallel(rss_urls, days_back)
    
    if not all_articles:
        logging.warning("No articles found from the provided RSS URLs.")
        return {
            "clusters": [],
            "failed_sources": failed_sources
        }
    
    logging.info(f"Total articles collected: {len(all_articles)}")
    
    # 2. Extract significant words
    word_counts = Counter()

    def extract_words_for_article(article):
        # Decide how to get significant_words
        if title_only:
            sig_words = extract_significant_words(article['title'], title_only=True, all_words=all_words)
        else:
            title_words = extract_significant_words(article['title'], title_only=False, all_words=all_words)
            content_words = extract_significant_words(article['content'], title_only=False, all_words=all_words)
            # Combine them, ensuring we don't double-count the same word in the same article
            sig_words = title_words + [w for w in content_words if w not in title_words]
        return (article, sig_words)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_article = {executor.submit(extract_words_for_article, a): a for a in all_articles}
        for future in concurrent.futures.as_completed(future_to_article):
            article = future_to_article[future]
            try:
                article_obj, sig_words = future.result()
                article_obj['significant_words'] = sig_words
                word_counts.update(sig_words)
            except Exception as exc:
                logging.error(f"Word extraction failed: {exc}")
                article['significant_words'] = []

    # 3. Sort words by rarity within each article
    for article in all_articles:
        if 'significant_words' in article:
            article['significant_words'] = sort_words_by_rarity(article['significant_words'], word_counts)

    # 4. Perform clustering
    try:
        clusters = cluster_articles(all_articles, common_word_threshold, top_words_to_consider)
        clusters = merge_clusters(clusters, merge_threshold)
        clusters = apply_minimum_articles_and_reassign(clusters, min_articles, join_percentage)
        clusters = merge_clusters_by_percentage(clusters, final_merge_percentage)

        # 5. Build the final cleaned_data structure
        cleaned_data = []
        for cluster in clusters:
            cluster_dict = {
                "articles": [
                    {
                        "title": article["title"],
                        "link": article["link"],
                        "favicon": article["favicon"],
                    }
                    for article in cluster.get("articles", [])
                ],
                "common_words": cluster.get("common_words", [])
            }
            cleaned_data.append(cluster_dict)

        return {
            "clusters": cleaned_data,
            "failed_sources": failed_sources
        }

    except Exception as e:
        logging.error(f"Error in clustering process: {str(e)}")
        return {
            "clusters": [],
            "failed_sources": failed_sources,
            "error": str(e)
        }
