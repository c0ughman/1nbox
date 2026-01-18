import feedparser
from datetime import datetime, timedelta, time as datetime_time
import time
import pytz
from django.core.management.base import BaseCommand
import re
import os
from openai import OpenAI
from collections import Counter
from .models import Topic, Organization, Summary, Comment
import json
import ast
import requests
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from bs4 import BeautifulSoup 
from google import generativeai as genai

import requests
from contextlib import contextmanager
import signal

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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('topic_processing.log'),
        logging.StreamHandler()
    ]
)

###############################################################################
# Function timing decorator and storage
###############################################################################
function_times = {}

def time_function(func):
    """
    Decorator that measures the execution time of a function and accumulates it
    in a global dictionary.
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        function_times[func.__name__] = function_times.get(func.__name__, 0) + elapsed_time
        return result
    return wrapper

###############################################################################
# All functions below decorated with @time_function
###############################################################################

@time_function
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

@time_function
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

@time_function
def get_articles_from_rss(rss_url, days_back=1):
    """
    Fetch articles from a single RSS URL. 
    Returns a list of article dicts with keys:
      title, link, published, summary, content, favicon
    """
    try:
        # Use requests with timeout to fetch the feed
        response = requests.get(rss_url, timeout=15)
        response.raise_for_status()
        
        # Parse the feed content
        feed = feedparser.parse(response.content)

        # Check for parsing errors
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

@time_function
def extract_significant_words(text, title_only=False, all_words=False):
    """
    Extract significant words from text, with options for different extraction modes
    Args:
        text (str): Text to extract words from
        title_only (bool): If True, treats the entire text as a title
        all_words (bool): If True, includes all words regardless of capitalization
    """
    if all_words:
        # For all words mode, we want any word with 2 or more characters
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    elif title_only:
        # For titles, we want all capitalized words since titles have different grammar
        words = re.findall(r'\b[A-Z][a-z]{1,}\b', text)
    else:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        words = []
        for sentence in sentences:
            sentence_words = re.findall(r'\b[A-Z][a-z]{1,}\b', sentence)
            words.extend(sentence_words[1:])  # Exclude the first word of each sentence
    
    words = [word for word in words if word not in INSIGNIFICANT_WORDS]
    return list(dict.fromkeys(words))

@time_function
def sort_words_by_rarity(word_list, word_counts):
    return sorted(word_list, key=lambda x: word_counts[x])

@time_function
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

@time_function
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

@time_function
def calculate_match_percentage(words1, words2):
    common_words = set(words1) & set(words2)
    return len(common_words) / len(words1) if words1 else 0

@time_function
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
            cluster_words = [word for article in cluster['articles'] for word in article['significant_words']]
            if calculate_match_percentage(article['significant_words'], cluster_words) >= join_percentage:
                cluster['articles'].append(article)
                reassigned_articles.append(article)
                break

    # Remove reassigned articles from miscellaneous cluster
    miscellaneous_cluster['articles'] = [article for article in miscellaneous_cluster['articles'] if article not in reassigned_articles]

    if miscellaneous_cluster['articles']:
        valid_clusters.append(miscellaneous_cluster)

    return valid_clusters

@time_function
def merge_clusters_by_percentage(clusters, join_percentage):
    merged = True
    while merged:
        merged = False
        for i, cluster1 in enumerate(clusters):
            for j, cluster2 in enumerate(clusters[i+1:], i+1):
                words1 = [word for article in cluster1['articles'] for word in article['significant_words']]
                words2 = [word for article in cluster2['articles'] for word in article['significant_words']]
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

@time_function
def print_clusters(clusters):
    for i, cluster in enumerate(clusters):
        print(f"CLUSTER {i+1} {{{', '.join(cluster['common_words'])}}}")
        print(f"Number of articles: {len(cluster['articles'])}")
        for article in cluster['articles']:
            print(f"{article['title']}")
            print(f"Significant Words: {', '.join(article['significant_words'])}")
            print()
        print()

@time_function
def estimate_tokens(text):
    return len(text.split())

@time_function
def calculate_cluster_tokens(cluster):
    total_tokens = 0
    for article in cluster['articles']:
        total_tokens += estimate_tokens(article['title'])
        total_tokens += estimate_tokens(article['summary'])
        total_tokens += estimate_tokens(article['content'])
    return total_tokens

@time_function
def limit_cluster_content(cluster, max_tokens=100000):
    """
    Limits cluster content to stay within token limits while preserving the most recent articles.
    
    Args:
        cluster (dict): The cluster containing articles
        max_tokens (int): Maximum number of tokens allowed (default 100000)
    
    Returns:
        dict: A new cluster with articles limited to fit within token limit
    """
    cluster_headers = f"Common words: {', '.join(cluster['common_words'])}\n\n"
    header_tokens = estimate_tokens(cluster_headers)
    
    # Calculate total tokens for the entire cluster
    total_tokens = header_tokens
    for article in cluster['articles']:
        article_content = f"Title: {article['title']}\n"
        article_content += f"URL: {article['link']}\n"
        article_content += f"Summary: {article['summary']}\n"
        article_content += f"Content: {article['content']}\n\n"
        total_tokens += estimate_tokens(article_content)
    
    print(f"Estimated total tokens for cluster: {total_tokens}")
    
    if total_tokens > 180000:
        print("Token count exceeds 180000, splitting cluster in half")
        mid_point = len(cluster['articles']) // 2
        return {
            'common_words': cluster['common_words'],
            'articles': cluster['articles'][:mid_point]  # Return first half of articles
        }
    
    available_tokens = max_tokens - header_tokens - 10000  # Reserve 10000 tokens for prompt and completion
    limited_articles = []
    current_tokens = 0
    
    # Sort articles by publication date (newest first)
    sorted_articles = sorted(cluster['articles'], 
                            key=lambda x: datetime.fromisoformat(x['published'].replace('Z', '+00:00')),
                            reverse=True)
    
    for article in sorted_articles:
        article_content = f"Title: {article['title']}\n"
        article_content += f"URL: {article['link']}\n"
        article_content += f"Summary: {article['summary']}\n"
        article_content += f"Content: {article['content']}\n\n"
        
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
@time_function
def get_openai_response(cluster, max_tokens=4000):
    try:
        openai_key = os.environ.get('OPENAI_KEY')
        if not openai_key:
            logging.error("OpenAI API key not found in environment variables")
            return "Error: OpenAI API key not configured"

        client = OpenAI(api_key=openai_key)

        # Handle extremely large clusters
        if calculate_cluster_tokens(cluster) > 300000:  # If cluster is extremely large
            logging.warning(f"Cluster size exceeds 300k tokens, truncating to newest articles")
            cluster['articles'] = sorted(
                cluster['articles'],
                key=lambda x: datetime.fromisoformat(x['published'].replace('Z', '+00:00')),
                reverse=True
            )[:10]  # Keep only the 10 newest articles

        # Limit cluster content to 124000 tokens before processing
        limited_cluster = limit_cluster_content(cluster, max_tokens=124000)
        
        # Process in chunks if needed
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
        raise  # Retry will handle this

@time_function
def process_cluster_chunk(cluster, client, max_tokens):
    cluster_content = f"Common words: {', '.join(cluster['common_words'])}\n\n"
    current_tokens = 0
    sub_clusters = []
    current_sub_cluster = []

    for article in cluster['articles']:
        article_content = f"Title: {article['title']}\n"
        article_content += f"URL: {article['link']}\n"
        article_content += f"Summary: {article['summary']}\n"
        article_content += f"Content: {article['content']}\n\n"
        
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
        
        prompt = ("You are a News Facts Summarizer. I will give you some articles, and I want you to tell me "
                  "all the facts from each of the articles in a small but fact-dense summary "
                  "including all the dates, names and key factors to provide full context on the events."
                  "also, i want you to add the corresponding url next to every line you put in the summary in parentheses"
                  "Finally, It is required to add a general summary of the cluster with 3-4 sentences about"
                  "what is happening, the context and the overall big picture of the events in the articles. ")

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

@time_function
def get_final_summary(
    cluster_summaries,
    sentences_final_summary,
    topic_prompt=None,
    organization_description=""
):
    """
    Generates a final JSON-based summary of all cluster_summaries using Gemini API.  
    If organization_description is present, instructs Gemini to add an 'Insight:' line 
    at the end of a story's content if relevant to that organization.  
    Returns the raw text response from Gemini (you typically parse it with extract_braces_content, then json.loads).
    """
    logging.info("Preparing to get final summary from Gemini for all cluster summaries")

    # Support both GEMINI_API_KEY and GEMINI_KEY for backwards compatibility
    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GEMINI_KEY')
    if not gemini_key:
        raise ValueError("Gemini API key not found in environment variables. Set GEMINI_API_KEY or GEMINI_KEY.")

    genai.configure(api_key=gemini_key)
    # Use gemini-2.5-flash-lite (cheapest smart model, generally available)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

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
        "      \"content\": \"\u2022 Bulletpoint 1.\\n\\n\u2022 Bulletpoint 2.\\n\\n\u2022 Bulletpoint 3.\"\n"
        "    },\n"
        "    {\n"
        "      \"title\": \"Title 2\",\n"
        "      \"content\": \"\u2022 Bulletpoint 1.\\n\\n\u2022 Bulletpoint 2.\\n\\n\u2022 Bulletpoint 3.\"\n"
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
        logging.info("Organization description provided; instructing Gemini to generate insights.")
        base_prompt += (
            "If there’s a relevant insight or recommended action for this organization specifically: "
            f"{organization_description}"
            "you MUST add a final line to that story's content in this format:\n"
            "\n"
            "Insight: [Your one-sentence insight]\n"
            "\n"
            "The insight must be a piece of information related to the story that would help the business described"
            "in achieving their goals, or preventing or mitigating possible threats, support the business with relevant information."
            "Try to come up with a relevant insight for at least half of the stories if possible."
            "The insight can be relevant economically, strategically, an opportunity, a threat or other."
            "Tie it back to the organization and its specific needs and opportunities."
            "### Insight format\n"
            "If all three checkpoints pass, append **exactly** this string to the end of the "
            "story’s bullet list (inside the same \"content\" value):\n\n"
            "\\n\\nInsight: <one sentence, ≤ 30 words, starting with an action verb>\n\n"
            "✱ The two leading “\\n\\n” characters are mandatory; do NOT add extra spaces or newlines before or after them.\n"
        )

    base_prompt += (
        "Now here are the combined article summaries:\n"
        f"{all_summaries}\n\n"
        "Make sure you follow the JSON structure exactly."
    )

    logging.debug("Sending final summary prompt to Gemini...")

    try:
        response = model.generate_content(base_prompt)
        
        # Check if response was blocked by safety filters
        if hasattr(response, 'candidates') and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason'):
                if candidate.finish_reason == 'SAFETY':
                    logging.error("⚠️ Gemini response blocked by content safety filters")
                    raise ValueError("Response blocked by content safety filters")
                elif candidate.finish_reason == 'RECITATION':
                    logging.error("⚠️ Gemini response blocked due to recitation")
                    raise ValueError("Response blocked due to recitation")
                elif candidate.finish_reason not in [None, 'STOP']:
                    logging.warning(f"⚠️ Unexpected finish_reason: {candidate.finish_reason}")
            
            # Extract text from candidate
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                if len(candidate.content.parts) > 0:
                    return candidate.content.parts[0].text
        
        # Fallback to direct text attribute
        if hasattr(response, 'text'):
            return response.text
        
        # Last resort - try to get text from response
        logging.error(f"Unexpected Gemini response format: {type(response)}")
        logging.error(f"Response attributes: {dir(response)}")
        if hasattr(response, 'candidates'):
            logging.error(f"Candidates: {response.candidates}")
        raise ValueError("Gemini API returned unexpected response format - no text found")
        
    except Exception as e:
        logging.error(f"Gemini API error in get_final_summary: {str(e)}")
        logging.error(f"Error type: {type(e).__name__}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        raise


@time_function
def extract_braces_content(s):
    start_index = s.find('{')
    end_index = s.rfind('}')
        
    if start_index == -1 or end_index == -1:
        # If there is no '{' or '}', return an empty string or handle as needed
        return ""
        
    # Include the end_index in the slice by adding 1
    return s[start_index:end_index + 1]


def repair_json(json_string):
    """
    Attempts to repair common JSON issues from Gemini API responses.
    Handles trailing commas, unescaped quotes, and other common issues.
    """
    import re
    
    if not json_string:
        return json_string
    
    # Remove trailing commas before closing braces/brackets (most common issue)
    json_string = re.sub(r',(\s*[}\]])', r'\1', json_string)
    
    # Fix smart quotes (replace with regular quotes)
    json_string = json_string.replace('"', '"').replace('"', '"')
    json_string = json_string.replace(''', "'").replace(''', "'")
    
    # Fix unescaped backslashes (but preserve escaped ones)
    # This is a simplified approach - we'll handle newlines separately
    json_string = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', json_string)
    
    # Try to fix unescaped newlines and tabs in string values
    # We'll use a state machine to track if we're inside a string
    result = []
    in_string = False
    escape_next = False
    i = 0
    
    while i < len(json_string):
        char = json_string[i]
        
        if escape_next:
            result.append(char)
            escape_next = False
        elif char == '\\':
            result.append(char)
            escape_next = True
        elif char == '"' and (i == 0 or json_string[i-1] != '\\'):
            in_string = not in_string
            result.append(char)
        elif in_string:
            # Inside a string value
            if char == '\n':
                # Escape newlines inside strings
                result.append('\\n')
            elif char == '\t':
                # Escape tabs inside strings
                result.append('\\t')
            elif char == '\r':
                # Escape carriage returns
                result.append('\\r')
            else:
                result.append(char)
        else:
            # Outside string - keep as is
            result.append(char)
        
        i += 1
    
    return ''.join(result)


def parse_json_with_repair(json_string, max_retries=3):
    """
    Attempts to parse JSON, repairing it if necessary.
    Returns parsed JSON or raises an exception if all attempts fail.
    """
    import json
    
    # First, extract JSON from any surrounding text
    json_string = extract_braces_content(json_string)
    
    if not json_string:
        raise ValueError("No JSON content found in response")
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Try parsing as-is first
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            last_error = e
            logging.warning(f"JSON parse attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_retries - 1:
                # Try to repair the JSON
                json_string = repair_json(json_string)
                logging.info(f"Attempting JSON repair (attempt {attempt + 1})...")
            else:
                # Last attempt - log the problematic JSON for debugging
                logging.error(f"Failed to parse JSON after {max_retries} attempts")
                logging.error(f"JSON decode error: {str(e)}")
                logging.error(f"Error position: line {e.lineno}, column {e.colno}")
                # Log a snippet around the error
                if e.lineno and e.colno:
                    lines = json_string.split('\n')
                    error_line_idx = e.lineno - 1
                    if 0 <= error_line_idx < len(lines):
                        error_line = lines[error_line_idx]
                        start = max(0, e.colno - 50)
                        end = min(len(error_line), e.colno + 50)
                        logging.error(f"Problem area: ...{error_line[start:end]}...")
                logging.error(f"Full JSON (first 2000 chars): {json_string[:2000]}")
                raise
    
    # Should never reach here, but just in case
    raise last_error

@time_function
def parse_input(input_string):
    # Safely evaluate the string to a dictionary
    data = ast.literal_eval(input_string)
    
    # Extract the summary and questions
    summary = data.get('summary', '')
    questions = data.get('questions', [])
    
    return summary, questions

@time_function
def generate_cluster_hash(common_words):
    """Generate stable hash from common words to identify a cluster"""
    import hashlib
    words_str = '-'.join(sorted(common_words))
    return hashlib.md5(words_str.encode()).hexdigest()[:12]

# Helper functions for cluster news system

@time_function
def calculate_cluster_difference(current_clusters, previous_clusters):
    """
    Calculate how much the clusters changed.
    Returns a value between 0 (identical) and 1 (completely different).
    Different common_words = different cluster identity.
    
    IMPORTANT: For existing clusters, only counts NEW articles added (not removals).
    We only want to regenerate summaries when there's NEW information, not less information.
    """
    if not previous_clusters:
        return 1.0  # No previous clusters, 100% different
    
    # Create cluster signatures based on common words (cluster identity)
    current_sigs = {
        generate_cluster_hash(cluster['common_words']): set(a['link'] for a in cluster['articles'])
        for cluster in current_clusters
    }
    
    previous_sigs = {
        generate_cluster_hash(cluster['common_words']): set(a['link'] for a in cluster['articles'])
        for cluster in previous_clusters
    }
    
    # Count changes
    current_cluster_ids = set(current_sigs.keys())
    previous_cluster_ids = set(previous_sigs.keys())
    
    new_clusters = len(current_cluster_ids - previous_cluster_ids)
    # NOTE: We still count removed clusters for the "new_clusters" metric
    # but this is about clusters disappearing entirely, not articles being removed
    
    # For clusters that exist in both, check if NEW articles were added
    common_cluster_ids = current_cluster_ids & previous_cluster_ids
    modified_clusters = 0
    
    for cluster_id in common_cluster_ids:
        current_articles = current_sigs[cluster_id]
        previous_articles = previous_sigs[cluster_id]
        
        # Only count NEW articles (additions), ignore removals
        new_articles = current_articles - previous_articles
        
        if len(current_articles) > 0:
            # Calculate percentage of NEW articles in current cluster
            new_percentage = len(new_articles) / len(current_articles)
            
            # If 40% or more of the cluster is new articles, consider it modified
            if new_percentage >= 0.40:
                modified_clusters += 1
    
    # Calculate total change percentage
    # Only count new clusters and modified clusters (not removed clusters for cluster summaries)
    total_clusters = len(current_sigs) if len(current_sigs) > 0 else 1
    changed_clusters = new_clusters + modified_clusters
    change_percentage = changed_clusters / total_clusters
    
    return change_percentage

@time_function
def calculate_summary_difference(current_summaries, previous_summaries):
    """
    Calculate how much the cluster summaries changed.
    Returns a value between 0 (identical) and 1 (completely different).
    """
    import hashlib
    
    if not previous_summaries:
        return 1.0  # No previous summaries, 100% different
    
    # Create hashes of summaries for comparison
    current_hashes = {hashlib.md5(s.encode()).hexdigest() for s in current_summaries}
    previous_hashes = {hashlib.md5(s.encode()).hexdigest() for s in previous_summaries}
    
    # Count new and removed summaries
    new_summaries = len(current_hashes - previous_hashes)
    removed_summaries = len(previous_hashes - current_hashes)
    
    total_summaries = max(len(current_summaries), len(previous_summaries))
    if total_summaries == 0:
        return 0.0
    
    changed_summaries = new_summaries + removed_summaries
    change_percentage = changed_summaries / total_summaries
    
    return change_percentage

@time_function
def clean_clusters_for_storage(clusters):
    """
    Clean clusters to prevent overwhelming the database.
    Only store essential information.
    """
    cleaned_data = []
    for cluster in clusters:
        cleaned_item = {
            "articles": [
                {
                    "title": article["title"],
                    "link": article["link"],
                    "favicon": article.get("favicon", "")
                }
                for article in cluster.get("articles", [])
            ],
            "common_words": cluster.get("common_words", [])
        }
        cleaned_data.append(cleaned_item)
    return cleaned_data

@contextmanager
@time_function
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

@time_function
def process_topic(topic, days_back=1, common_word_threshold=2, top_words_to_consider=3,
                 merge_threshold=2, min_articles=3, join_percentage=0.5,
                 final_merge_percentage=0.5, sentences_final_summary=3, title_only=False, all_words=False):

    try:
        logging.info(f"Starting processing for topic: {topic.name}")
        logging.info(f"Title-only mode: {title_only}")
        logging.info(f"All-words mode: {all_words}")

        # Validate topic configuration
        if not topic.sources:
            logging.warning(f"Topic {topic.name} has no sources, skipping")
            return

        # Initialize article collection
        all_articles = []
        failed_sources = []
        successful_sources = []
        
        # Process each RSS source with timeout and error handling
        for url in topic.sources:
            try:
                with timeout(60):  # 60-second timeout per source
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

        # Log source processing results
        logging.info(f"Successfully processed {len(successful_sources)} sources for topic {topic.name}")
        if failed_sources:
            logging.warning(f"Failed sources for topic {topic.name}: {failed_sources}")

        # Check if we have enough articles to proceed
        if not all_articles:
            logging.warning(f"No articles found for topic {topic.name}, skipping")
            return
        
        number_of_articles = len(all_articles)
        logging.info(f"Total articles collected: {number_of_articles}")
        
        # Cap the total number of articles
        all_articles = all_articles[:777]
        number_of_articles = len(all_articles)
        logging.info(f"⚠️ Article list trimmed to 777 max. Final count: {number_of_articles}")

        try:
            # Extract and count significant words with memory management
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

            # Sort words by rarity for each article
            for article in all_articles:
                try:
                    article['significant_words'] = sort_words_by_rarity(
                        article['significant_words'], word_counts
                    )
                except Exception as e:
                    logging.error(f"Error sorting words for article {article.get('title', 'Unknown')}: {str(e)}")
                    continue

            # Cluster articles with error handling
            try:
                clusters = cluster_articles(
                    all_articles, common_word_threshold, top_words_to_consider, title_only
                )
                merged_clusters = merge_clusters(clusters, merge_threshold)
                clusters_with_min_articles = apply_minimum_articles_and_reassign(
                    merged_clusters, min_articles, join_percentage
                )
                final_clusters = merge_clusters_by_percentage(
                    clusters_with_min_articles, final_merge_percentage
                )

                logging.info(f"Generated {len(final_clusters)} clusters for topic {topic.name}")
                print_clusters(final_clusters)


            except Exception as e:
                logging.error(f"Error in clustering process for topic {topic.name}: {str(e)}")
                return

            cluster_summaries = [
                f"Cluster with common words: {', '.join(cluster['common_words'])}\n\n" +
                "\n\n".join(
                    f"Title: {article['title']}\nURL: {article['link']}\nSummary: {article.get('summary', '')}"
                    for article in cluster['articles']
                )
                for cluster in final_clusters
            ]

            # Generate final summary with error handling
            try:
                final_summary_json = get_final_summary(
                    cluster_summaries,
                    sentences_final_summary,
                    topic.prompt if topic.prompt else None,
                    topic.organization.description if topic.organization.description else ""
                )

                logging.info("----------- LOGGING SUMMARY GENERATION -----------")
                logging.info(f"Organization description: {topic.organization.description}")
                logging.info(f"Raw Gemini response (first 500 chars): {final_summary_json[:500]}...")

                # Parse JSON with repair logic
                final_summary_data = parse_json_with_repair(final_summary_json)

                logging.info(f"Successfully parsed summary JSON: {json.dumps(final_summary_data, indent=2)}")

            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                logging.error(f"Error generating final summary for {topic.name}: {str(e)}")
                logging.error(f"Error type: {type(e).__name__}")
                logging.error(f"Full traceback:\n{error_trace}")
                
                # Log more details about the error
                if "GEMINI_KEY" in str(e) or "API key" in str(e):
                    logging.error("⚠️ GEMINI_KEY environment variable is missing or invalid!")
                elif "rate limit" in str(e).lower() or "quota" in str(e).lower():
                    logging.error("⚠️ Gemini API rate limit or quota exceeded!")
                elif "model" in str(e).lower():
                    logging.error("⚠️ Gemini model error - check if 'gemini-2.5-flash-lite' is available!")
                
                final_summary_data = {
                    "summary": [{"title": "Error", "content": f"Failed to generate summary: {str(e)}"}],
                    "questions": ["What happened?", "Why did it happen?", "What's next?"],
                }

            # Extract questions and clean clusters
            questions = json.dumps(final_summary_data.get('questions', []))

            # Clean clusters to prevent overwhelming the database
            cleaned_data = []
            for item in final_clusters:
                cleaned_item = {
                    "articles": [
                        {
                            "title": article["title"],
                            "link": article["link"],
                            "favicon": article["favicon"]
                        }
                        for article in item.get("articles", [])
                    ],
                    "common_words": item.get("common_words", [])
                }
                cleaned_data.append(cleaned_item)

            # Create the summary in the database with error handling
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
                # Could implement a retry mechanism here if needed

        except Exception as e:
            logging.error(f"Error in main processing loop for topic {topic.name}: {str(e)}")

    except Exception as e:
        logging.error(f"Critical error processing topic {topic.name}: {str(e)}")
        # Could add notification system here for critical errors
    finally:
        logging.info(f"Finished processing topic: {topic.name}")

@time_function
def process_all_topics(days_back=1, common_word_threshold=2, top_words_to_consider=3,
                      merge_threshold=2, min_articles=3, join_percentage=0.5,
                      final_merge_percentage=0.5, sentences_final_summary=3, title_only=False, all_words=False, force=False):
    
    logging.info("==== Starting process_all_topics ====")
    
    # Get all active organizations (no time check - process all every time)
    active_organizations = Organization.objects.exclude(plan='inactive')
    
    logging.info(f"Processing {active_organizations.count()} active organizations")

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
                process_topic(topic, days_back, common_word_threshold, top_words_to_consider,
                              merge_threshold, min_articles, join_percentage,
                              final_merge_percentage, sentences_final_summary, title_only, all_words)
            except Exception as e:
                logging.error(f"❌ Failed to process topic {topic.name}: {str(e)}")
                continue

    logging.info("==== Finished process_all_topics ====")

    # Log total time per function
    logging.info("\n========= TOTAL TIME SPENT PER FUNCTION =========")
    for func_name, total_time in function_times.items():
        logging.info(f"{func_name}: {total_time:.4f} seconds")


###############################################################################
# Main section: run process_all_topics, then log function times
###############################################################################
if __name__ == "__main__":
    process_all_topics()
