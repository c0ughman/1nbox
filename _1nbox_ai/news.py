import feedparser
from datetime import datetime, timedelta, time
import pytz
from django.core.management.base import BaseCommand
import re
import os
import functools
import time as pytime
import logging
import json
import ast
import requests
from collections import Counter
from bs4 import BeautifulSoup   # <-- ADDED HERE
from tenacity import retry, stop_after_attempt, wait_exponential
from contextlib import contextmanager
import signal

from .models import Topic, Organization, Summary, Comment

# List of insignificant words to exclude
INSIGNIFICANT_WORDS = set([
    'In', 'The', 'Continue', 'Fox', 'News', 'Newstalk', 'Newsweek', 'Is', 
    'Why', 'Do', 'When', 'Where', 'What', 'It', 'Get', 'Examiner', 
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
    'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December',
    'A', 'An', 'And', 'At', 'By', 'For', 'From', 'Has', 'He', 'I', 'Of', 
    'On', 'Or', 'She', 'That', 'This', 'To', 'Was', 'With', 'You',
    'All', 'Are', 'As', 'Be', 'Been', 'But', 'Can', 'Had', 'Have', 'Her', 
    'His', 'If', 'Into', 'More', 'My', 'Not', 'One', 'Our', 'Their', 'They', 'Independent', 'Times',
    'Sign', 'Guardian', 'Follow', 'Shutterstock', 'Conversation', 'Press', 'Associated', 'Link', 'Advertisement',
    'Move', 'Forward', 'New', 'Bloomberg', 'Stock', 'Call', 'Rate', 'Street', 'Full', 'Benzinga',
    'Science', 'Sciences', 'Volume', 'Academy', 'University', 'Images', 'Infobox', 'Read',
    'Pin', 'Post', 'Like', 'Subscribe', 'Stumble', 'Add', 'Brief', 'View', 'While', 'However', 'Country',
    'Even', 'Still', 'Monthly', 'Jan', 'Feb', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    'Miscellaneous', 'Out', 'We', 'Makes', 'Inc', 'Description', 'Connections', 'Wordle', 'Play', 'Mashable', 
    'Mahjong', 'Earnings', 'Call', 'Transcript', 'Market', 'Tracker', 'Business', 'Insider',
    'Thu', 'Euractiv', 'Regulation', 'Today', 'Best', 'Your', 'Early', 'How', 'Report', 'Top', 'Billion', 'Watch',
    'Here', 'Buy', 'Day', 'Man', 'Sales', 'Its', 'High', 'Low', 'Down', 'Says', 'Analyst', 'Before', 'Research', 'Ahead',
    'Off', 'Save', 'Now', 'Video', 'Quarter', 'Since', 'Aims', 'Set', 'Stocks', 'These', 'Market', 'Million', 'Deal', 'Billion', 
])

# Set up logging with force=True to override other configs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('topic_processing.log'),
        logging.StreamHandler()
    ],
    force=True  # <-- Ensures this config is used, so time logs show in terminal
)

def measure_execution_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = pytime.time()
        result = func(*args, **kwargs)
        elapsed = pytime.time() - start_time
        logging.info(f"Function '{func.__name__}' took {elapsed:.2f} seconds to complete.")
        return result
    return wrapper

@measure_execution_time
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

@measure_execution_time
def extract_links_from_description(description):
    """Extracts all links and corresponding text from an article's description."""
    extracted_articles = []
    if description:
        soup = BeautifulSoup(description, 'html.parser')
        for link in soup.find_all('a', href=True):
            title = link.text.strip()
            href = link['href'].strip()
            if title and href:
                extracted_articles.append({
                    'title': title,
                    'link': href,
                    'published': None,
                    'summary': '',
                    'content': '',
                    'favicon': f"https://www.google.com/s2/favicons?domain={href}",
                })
    return extracted_articles

@measure_execution_time
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

                main_article = {
                    'title': entry.title,
                    'link': entry.link,
                    'published': str(pub_date),
                    'summary': getattr(entry, 'summary', ''),
                    'content': content,
                    'favicon': favicon_url,
                }
                articles.append(main_article)

                # Extract additional articles from Google News description
                if "news.google.com" in entry.link and hasattr(entry, 'description'):
                    additional_articles = extract_links_from_description(entry.description)
                    # Filter out unhelpful links
                    filtered_articles = [
                        article_dict for article_dict in additional_articles
                        if "View Full Coverage on Google News" not in article_dict.get('title', '')
                    ]
                    articles.extend(filtered_articles)

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
        logging.error(f"Unexpected error fetching RSS from {rss_url}: {str(e)}")
        return []

@measure_execution_time
def extract_significant_words(text, title_only=False, all_words=False):
    if all_words:
        # For all words mode, we want any word with 3 or more letters
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    elif title_only:
        # For titles, we want all capitalized words since titles have different grammar
        words = re.findall(r'\b[A-Z][a-z]{1,}\b', text)
    else:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        words = []
        for sentence in sentences:
            sentence_words = re.findall(r'\b[A-Z][a-z]{1,}\b', sentence)
            # Exclude the first word of each sentence
            words.extend(sentence_words[1:])
    
    words = [word for word in words if word not in INSIGNIFICANT_WORDS]
    return list(dict.fromkeys(words))

@measure_execution_time
def sort_words_by_rarity(word_list, word_counts):
    return sorted(word_list, key=lambda x: word_counts[x])

@measure_execution_time
def cluster_articles(articles, common_word_threshold, top_words_to_consider, title_only=False):
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

@measure_execution_time
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

@measure_execution_time
def calculate_match_percentage(words1, words2):
    common_words = set(words1) & set(words2)
    return len(common_words) / len(words1) if words1 else 0

@measure_execution_time
def apply_minimum_articles_and_reassign(clusters, min_articles, join_percentage):
    miscellaneous_cluster = {'common_words': ['Miscellaneous'], 'articles': []}
    valid_clusters = []

    for cluster in clusters:
        if len(cluster['articles']) >= min_articles:
            valid_clusters.append(cluster)
        else:
            miscellaneous_cluster['articles'].extend(cluster['articles'])

    # Reassign miscellaneous articles to clusters if they meet the join_percentage criteria
    reassigned_articles = []
    for article in miscellaneous_cluster['articles']:
        for cluster in valid_clusters:
            cluster_words = [w for a in cluster['articles'] for w in a['significant_words']]
            if calculate_match_percentage(article['significant_words'], cluster_words) >= join_percentage:
                cluster['articles'].append(article)
                reassigned_articles.append(article)
                break

    # Remove reassigned articles from miscellaneous cluster
    miscellaneous_cluster['articles'] = [
        article for article in miscellaneous_cluster['articles'] 
        if article not in reassigned_articles
    ]

    if miscellaneous_cluster['articles']:
        valid_clusters.append(miscellaneous_cluster)

    return valid_clusters

@measure_execution_time
def merge_clusters_by_percentage(clusters, join_percentage):
    merged = True
    while merged:
        merged = False
        for i, cluster1 in enumerate(clusters):
            for j, cluster2 in enumerate(clusters[i+1:], i+1):
                words1 = [w for a in cluster1['articles'] for w in a['significant_words']]
                words2 = [w for a in cluster2['articles'] for w in a['significant_words']]
                if (calculate_match_percentage(words1, words2) >= join_percentage and
                    calculate_match_percentage(words2, words1) >= join_percentage):
                    merged_cluster = {
                        'common_words': list(set(cluster1['common_words']) & set(cluster2['common_words'])),
                        'articles': cluster1['articles'] + cluster2['articles']
                    }
                    clusters[i] = merged_cluster
                    clusters.pop(j)
                    merged = True
                    break
            if merged:
                break
    return clusters

@measure_execution_time
def print_clusters(clusters):
    for i, cluster in enumerate(clusters):
        print(f"CLUSTER {i+1} {{{', '.join(cluster['common_words'])}}}")
        print(f"Number of articles: {len(cluster['articles'])}")
        for article in cluster['articles']:
            print(f"{article['title']}")
            print(f"Significant Words: {', '.join(article['significant_words'])}\n")
        print()

@measure_execution_time
def estimate_tokens(text):
    return len(text.split())

@measure_execution_time
def calculate_cluster_tokens(cluster):
    total_tokens = 0
    for article in cluster['articles']:
        total_tokens += estimate_tokens(article['title'])
        total_tokens += estimate_tokens(article['summary'])
        total_tokens += estimate_tokens(article['content'])
    return total_tokens

@measure_execution_time
def limit_cluster_content(cluster, max_tokens=100000):
    """
    Limits cluster content to stay within token limits while preserving the most recent articles.
    """
    cluster_headers = f"Common words: {', '.join(cluster['common_words'])}\n\n"
    header_tokens = estimate_tokens(cluster_headers)
    
    total_tokens = header_tokens
    for article in cluster['articles']:
        article_content = (
            f"Title: {article['title']}\nURL: {article['link']}\n"
            f"Summary: {article['summary']}\nContent: {article['content']}\n\n"
        )
        total_tokens += estimate_tokens(article_content)
    
    print(f"Estimated total tokens for cluster: {total_tokens}")
    
    if total_tokens > 180000:
        print("Token count exceeds 180000, splitting cluster in half")
        mid_point = len(cluster['articles']) // 2
        return {
            'common_words': cluster['common_words'],
            'articles': cluster['articles'][:mid_point]
        }
    
    available_tokens = max_tokens - header_tokens - 10000  # Reserve some tokens
    limited_articles = []
    current_tokens = 0
    
    # Sort by date (newest first)
    sorted_articles = sorted(
        cluster['articles'], 
        key=lambda x: datetime.fromisoformat(x['published'].replace('Z', '+00:00')),
        reverse=True
    )
    
    for article in sorted_articles:
        article_content = (
            f"Title: {article['title']}\nURL: {article['link']}\n"
            f"Summary: {article['summary']}\nContent: {article['content']}\n\n"
        )
        article_tokens = estimate_tokens(article_content)
        
        if current_tokens + article_tokens <= available_tokens:
            limited_articles.append(article)
            current_tokens += article_tokens
        else:
            break
    
    print(f"Final token count after limiting: {current_tokens + header_tokens}")
    return {
        'common_words': cluster['common_words'],
        'articles': limited_articles
    }

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
@measure_execution_time
def get_openai_response(cluster, max_tokens=4000):
    try:
        openai_key = os.environ.get('OPENAI_KEY')
        if not openai_key:
            logging.error("OpenAI API key not found in environment variables")
            return "Error: OpenAI API key not configured"

        from openai import OpenAI
        client = OpenAI(api_key=openai_key)

        if calculate_cluster_tokens(cluster) > 300000:
            logging.warning("Cluster size exceeds 300k tokens, truncating to newest articles")
            cluster['articles'] = sorted(
                cluster['articles'],
                key=lambda x: datetime.fromisoformat(x['published'].replace('Z', '+00:00')),
                reverse=True
            )[:10]

        limited_cluster = limit_cluster_content(cluster, max_tokens=124000)
        
        if len(limited_cluster['articles']) < len(cluster['articles']) // 2:
            logging.info("Processing large cluster in multiple chunks")
            chunks = []
            for i in range(0, len(cluster['articles']), 10):
                chunk_cluster = {
                    'common_words': cluster['common_words'],
                    'articles': cluster['articles'][i:i+10]
                }
                chunk_limited = limit_cluster_content(chunk_cluster, max_tokens=124000)
                chunks.append(process_cluster_chunk(chunk_limited, client, max_tokens))
            
            return "\n\n".join(chunks)
        
        return process_cluster_chunk(limited_cluster, client, max_tokens)

    except Exception as e:
        logging.error(f"Error in get_openai_response: {str(e)}")
        raise

@measure_execution_time
def process_cluster_chunk(cluster, client, max_tokens):
    cluster_content = f"Common words: {', '.join(cluster['common_words'])}\n\n"
    current_tokens = 0
    sub_clusters = []
    current_sub_cluster = []

    for article in cluster['articles']:
        article_content = (
            f"Title: {article['title']}\nURL: {article['link']}\n"
            f"Summary: {article['summary']}\nContent: {article['content']}\n\n"
        )
        article_tokens = estimate_tokens(article_content)
        
        if current_tokens + article_tokens > max_tokens:
            sub_clusters.append(current_sub_cluster)
            current_sub_cluster = []
            current_tokens = 0
        
        current_sub_cluster.append(article_content)
        current_tokens += article_tokens

    if current_sub_cluster:
        sub_clusters.append(current_sub_cluster)

    summaries = []
    for sub_cluster in sub_clusters:
        sub_cluster_content = cluster_content + ''.join(sub_cluster)
        
        prompt = (
            "You are a News Facts Summarizer. I will give you some articles, and I want you to tell me "
            "all the facts from each of the articles in a small but fact-dense summary including all the "
            "dates, names and key factors to provide full context on the events. Also, I want you to add "
            "the corresponding url next to every line you put in the summary in parentheses. Finally, "
            "it is required to add a general summary of the cluster with 3-4 sentences about what is "
            "happening, the context and the overall big picture."
        )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=5000,
            temperature=0.125,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": sub_cluster_content}
            ]
        )
        summaries.append(completion.choices[0].message.content)

    return ' '.join(summaries)

@measure_execution_time
def get_final_summary(
    cluster_summaries,
    sentences_final_summary,
    topic_prompt=None,
    organization_description=""
):
    import os
    import json
    from openai import OpenAI

    logging.info("Preparing to get final summary from GPT for all cluster summaries")

    openai_key = os.environ.get('OPENAI_KEY')
    if not openai_key:
        raise ValueError("OpenAI API key not found in environment variables.")

    client = OpenAI(api_key=openai_key)

    all_summaries = "\n\n".join(cluster_summaries)

    base_prompt = (
        "You are a News Overview Summarizer. I will provide you with a collection of news article summaries, "
        "and I want you to condense them into a single JSON object with the exact structure shown below. "
        "Your entire output must be valid JSON and use double quotes for all keys and string values, "
        "with no extra text or code blocks outside the JSON.\n\n"

        "You must produce between 2 and 4 main stories (plus a 'miscellaneous' one if needed), each with two properties:\n"
        "1. \"title\": A concise headline that partially explains the situation but remains attention-grabbing.\n"
        "2. \"content\": A concise, bullet-pointed summary (one bullet per key aspect) in a single string, with each bullet "
        "   separated by two newlines (\\n\\n). Use about "
        f"{sentences_final_summary} sentences total per story to fully explain the situation.\n\n"

        "Also produce exactly three short questions a user might naturally ask about these stories.\n\n"

        "Return your output in valid JSON (no code fences, no single quotes) with the structure:\n"
        "{\n"
        "  \"summary\": [\n"
        "    {\n"
        "      \"title\": \"Title 1\",\n"
        "      \"content\": \"• Bulletpoint 1.\\n\\n• Bulletpoint 2.\\n\\n• Bulletpoint 3.\"\n"
        "    },\n"
        "    {\n"
        "      \"title\": \"Title 2\",\n"
        "      \"content\": \"• Bulletpoint 1.\\n\\n• Bulletpoint 2.\\n\\n• Bulletpoint 3.\"\n"
        "    }\n"
        "  ],\n"
        "  \"questions\": [\n"
        "    \"Question one?\",\n"
        "    \"Question two?\",\n"
        "    \"Question three?\"\n"
        "  ],\n"
        "  \"prompt\": \"Original topic prompt here (or empty if none)\"\n"
        "}\n\n"

        "Important:\n"
        "1. All strings and keys must use double quotes.\n"
        "2. There must be no trailing commas or extra fields.\n"
        "3. Do not wrap your JSON in any code fences.\n"
        "4. No single quotes in the JSON.\n\n"
    )

    if topic_prompt:
        base_prompt += (
            "Additional instructions from the topic owner:\n"
            f"{topic_prompt}\n\n"
            "Please incorporate these instructions into your summary.\n"
        )

    if organization_description:
        logging.info("Organization description provided; instructing GPT to generate insights.")
        base_prompt += (
            "If there’s a relevant insight or recommended action for this organization specifically: "
            f"{organization_description}"
            "you MUST add a final line to that story's content in this format:\n"
            "\n"
            "Insight: [Your one-sentence insight]\n"
            "\n"
            "The insight must be a piece of information related to the story that would help the business "
            "in achieving their goals, or preventing or mitigating possible threats. "
            "Try to come up with a relevant insight for at least half of the stories if possible."
        )

    base_prompt += (
        "Now here are the combined article summaries:\n"
        f"{all_summaries}\n\n"
        "Make sure you follow the JSON structure exactly."
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=5000,
        temperature=0.125,
        messages=[
            {"role": "system", "content": base_prompt}
        ]
    )

    return completion.choices[0].message.content

@measure_execution_time
def extract_braces_content(s):
    start_index = s.find('{')
    end_index = s.rfind('}')
    if start_index == -1 or end_index == -1:
        return ""
    return s[start_index:end_index + 1]

@measure_execution_time
def parse_input(input_string):
    data = ast.literal_eval(input_string)
    summary = data.get('summary', '')
    questions = data.get('questions', [])
    return summary, questions

@contextmanager
@measure_execution_time
def timeout(seconds):
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Timed out after {seconds} seconds")

    original_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

@measure_execution_time
def process_topic(
    topic,
    days_back=1,
    common_word_threshold=2,
    top_words_to_consider=3,
    merge_threshold=2,
    min_articles=3,
    join_percentage=0.5,
    final_merge_percentage=0.5,
    sentences_final_summary=3,
    title_only=False,
    all_words=False
):
    try:
        logging.info(f"Starting processing for topic: {topic.name}")
        logging.info(f"Title-only mode: {title_only}")
        logging.info(f"All-words mode: {all_words}")

        if not topic.sources:
            logging.warning(f"Topic {topic.name} has no sources, skipping")
            return

        all_articles = []
        failed_sources = []
        successful_sources = []
        
        for url in topic.sources:
            try:
                with timeout(60):
                    articles = get_articles_from_rss(url, days_back)
                    if articles:
                        all_articles.extend(articles)
                        successful_sources.append(url)
                        logging.info(f"Successfully retrieved {len(articles)} articles from {url}")
                    else:
                        failed_sources.append((url, "No articles retrieved"))
            except TimeoutError:
                logging.error(f"Timeout processing source {url}")
                failed_sources.append((url, "Timeout"))
                continue
            except Exception as e:
                logging.error(f"Error fetching RSS from {url}: {str(e)}")
                failed_sources.append((url, str(e)))
                continue

        logging.info(f"Successfully processed {len(successful_sources)} sources for topic {topic.name}")
        if failed_sources:
            logging.warning(f"Failed sources for topic {topic.name}: {failed_sources}")

        if not all_articles:
            logging.warning(f"No articles found for topic {topic.name}, skipping")
            return

        number_of_articles = len(all_articles)
        logging.info(f"Total articles collected: {number_of_articles}")

        try:
            word_counts = Counter()
            for article in all_articles:
                try:
                    if title_only:
                        article['significant_words'] = extract_significant_words(
                            article['title'], title_only=True, all_words=all_words
                        )
                    else:
                        title_words = extract_significant_words(
                            article['title'], title_only=False, all_words=all_words
                        )
                        content_words = extract_significant_words(
                            article['content'], title_only=False, all_words=all_words
                        )
                        article['significant_words'] = title_words + [
                            w for w in content_words if w not in title_words
                        ]
                    word_counts.update(article['significant_words'])
                except Exception as e:
                    logging.error(f"Error processing words for article {article.get('title', 'Unknown')}: {str(e)}")
                    continue

            for article in all_articles:
                try:
                    article['significant_words'] = sort_words_by_rarity(
                        article['significant_words'], word_counts
                    )
                except Exception as e:
                    logging.error(f"Error sorting words for article {article.get('title', 'Unknown')}: {str(e)}")
                    continue

            try:
                clusters = cluster_articles(all_articles, common_word_threshold, top_words_to_consider, title_only)
                merged_clusters = merge_clusters(clusters, merge_threshold)
                clusters_with_min_articles = apply_minimum_articles_and_reassign(merged_clusters, min_articles, join_percentage)
                final_clusters = merge_clusters_by_percentage(clusters_with_min_articles, final_merge_percentage)

                logging.info(f"Generated {len(final_clusters)} clusters for topic {topic.name}")
                print_clusters(final_clusters)

            except Exception as e:
                logging.error(f"Error in clustering process for topic {topic.name}: {str(e)}")
                return

            cluster_summaries = {}
            for cluster in final_clusters:
                try:
                    key = ' '.join([word.capitalize() for word in cluster['common_words']])
                    summary = get_openai_response(cluster)
                    cluster_summaries[key] = summary
                    logging.info(f"Generated summary for cluster: {key}")
                except Exception as e:
                    logging.error(f"Failed to generate summary for cluster {key}: {str(e)}")
                    cluster_summaries[key] = "Error generating summary for this cluster"

            try:
                final_summary_json = get_final_summary(
                    list(cluster_summaries.values()),
                    sentences_final_summary,
                    topic.prompt if topic.prompt else None,
                    topic.organization.description if topic.organization.description else ""
                )

                logging.info("----------- LOGGING SHIT -----------")
                logging.info(f"Organization description: {topic.organization.description}")
                logging.info(f"Raw OpenAI response: {final_summary_json}")

                final_summary_json = extract_braces_content(final_summary_json)
                logging.info(f"After extracting braces: {final_summary_json}")

                final_summary_data = json.loads(final_summary_json)
                logging.info(f"Parsed summary JSON: {json.dumps(final_summary_data, indent=2)}")

            except Exception as e:
                logging.error(f"Error generating final summary for {topic.name}: {str(e)}")
                final_summary_data = {
                    "summary": [{"title": "Error", "content": "Failed to generate summary"}],
                    "questions": ["What happened?", "Why did it happen?", "What's next?"],
                }

            questions = json.dumps(final_summary_data.get('questions', []))

            cleaned_data = []
            for item in final_clusters:
                cleaned_item = {
                    "articles": [
                        {
                            "title": art["title"],
                            "link": art["link"],
                            "favicon": art["favicon"]
                        }
                        for art in item.get("articles", [])
                    ],
                    "common_words": item.get("common_words", [])
                }
                cleaned_data.append(cleaned_item)

            try:
                new_summary = Summary.objects.create(
                    topic=topic,
                    final_summary=final_summary_data,
                    clusters=cleaned_data,
                    cluster_summaries=cluster_summaries,
                    number_of_articles=number_of_articles,
                    questions=questions
                )
                logging.info(f"Successfully created summary for topic {topic.name}")
                print(f"SUMMARY for {topic.name} created:")
                print(final_summary_data)

            except Exception as e:
                logging.error(f"Database error creating summary for {topic.name}: {str(e)}")

        except Exception as e:
            logging.error(f"Error in main processing loop for topic {topic.name}: {str(e)}")

    except Exception as e:
        logging.error(f"Critical error processing topic {topic.name}: {str(e)}")
    finally:
        logging.info(f"Finished processing topic: {topic.name}")

@measure_execution_time
def process_all_topics(
    days_back=1,
    common_word_threshold=2,
    top_words_to_consider=3,
    merge_threshold=2,
    min_articles=3,
    join_percentage=0.5,
    final_merge_percentage=0.5,
    sentences_final_summary=3,
    title_only=False,
    all_words=False
):
    logging.info("==== Starting process_all_topics ====")
    
    now_utc = datetime.now(pytz.utc)
    logging.info(f"Current UTC Time: {now_utc.strftime('%H:%M')}")

    valid_org_ids = []
    all_orgs = Organization.objects.exclude(plan='inactive')

    for org in all_orgs:
        if not org.summary_time or not org.summary_timezone:
            logging.warning(f"Skipping {org.name} - Missing summary_time or timezone.")
            continue

        try:
            org_tz = pytz.timezone(org.summary_timezone)
            local_now = now_utc.astimezone(org_tz)

            if not isinstance(org.summary_time, time):
                logging.error(f"Invalid summary_time for {org.name}: {org.summary_time}")
                continue

            expected_hour = org.summary_time.hour
            expected_minute = org.summary_time.minute - 30
            if expected_minute < 0:
                expected_hour -= 1
                expected_minute += 60

            logging.info(
                f"Org: {org.name} | Local Now: {local_now.strftime('%H:%M')} "
                f"| Expected Run Time: {expected_hour:02d}:{expected_minute:02d}"
            )

            if local_now.hour == expected_hour and local_now.minute == expected_minute:
                logging.info(f"✅ Running process for {org.name} (Time Matched)")
                valid_org_ids.append(org.id)
            else:
                logging.info(f"❌ Skipping {org.name} - Time did not match")
        except Exception as e:
            logging.error(f"❌ Time zone check error for {org.name}: {str(e)}")

    active_organizations = all_orgs.filter(id__in=valid_org_ids)

    for organization in active_organizations:
        logging.info(f"🔄 Processing organization: {organization.name}")

        try:
            Comment.objects.filter(writer__organization=organization).delete()
            logging.info(f"🗑️ Deleted comments for organization: {organization.name}")
        except Exception as e:
            logging.error(f"❌ Error deleting comments for {organization.name}: {str(e)}")

        try:
            seven_days_ago = datetime.now(pytz.utc) - timedelta(days=7)
            old_summaries = Summary.objects.filter(
                topic__organization=organization,
                created_at__lt=seven_days_ago
            )
            deletion_count = old_summaries.count()
            old_summaries.delete()
            logging.info(f"🗑️ Deleted {deletion_count} old summaries for {organization.name}")
        except Exception as e:
            logging.error(f"❌ Error deleting old summaries for {organization.name}: {str(e)}")

        for topic in organization.topics.all():
            try:
                process_topic(
                    topic,
                    days_back,
                    common_word_threshold,
                    top_words_to_consider,
                    merge_threshold,
                    min_articles,
                    join_percentage,
                    final_merge_percentage,
                    sentences_final_summary,
                    title_only,
                    all_words
                )
            except Exception as e:
                logging.error(f"❌ Failed to process topic {topic.name}: {str(e)}")
                continue

    logging.info("==== Finished process_all_topics ====")

if __name__ == "__main__":
    process_all_topics()
