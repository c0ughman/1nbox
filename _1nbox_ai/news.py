import feedparser
from datetime import datetime, timedelta
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
    'Here', 'Buy', 'Day', 'Man'
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
    try:
        # Use requests with timeout to fetch the feed
        response = requests.get(rss_url, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse the feed content
        feed = feedparser.parse(response.content)
        
        # Check if the feed parsing was successful
        if hasattr(feed, 'bozo_exception'):
            logging.error(f"Feed parsing error for {rss_url}: {feed.bozo_exception}")
            return []
            
        articles = []
        cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
        
        # Add feed validation
        if not hasattr(feed, 'entries'):
            logging.error(f"Invalid feed structure for {rss_url}")
            return []
            
        for entry in feed.entries:
            try:
                pub_date = get_publication_date(entry)
                if pub_date and pub_date >= cutoff_date:
                    # Validate required fields
                    if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
                        logging.warning(f"Missing required fields in entry from {rss_url}")
                        continue
                        
                    favicon_url = f"https://www.google.com/s2/favicons?domain={rss_url}"
                    
                    # Safely get content with fallbacks
                    content = ''
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
                        'favicon': favicon_url
                    })
                elif not pub_date:
                    logging.warning(f"Missing date for entry '{entry.title}' in {rss_url}")
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
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
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

def sort_words_by_rarity(word_list, word_counts):
    return sorted(word_list, key=lambda x: word_counts[x])

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

def calculate_match_percentage(words1, words2):
    common_words = set(words1) & set(words2)
    return len(common_words) / len(words1) if words1 else 0

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

def print_clusters(clusters):
    for i, cluster in enumerate(clusters):
        print(f"CLUSTER {i+1} {{{', '.join(cluster['common_words'])}}}")
        print(f"Number of articles: {len(cluster['articles'])}")
        for article in cluster['articles']:
            print(f"{article['title']}")
            print(f"Significant Words: {', '.join(article['significant_words'])}")
            print()
        print()

def estimate_tokens(text):
    return len(text.split())

def calculate_cluster_tokens(cluster):
    total_tokens = 0
    for article in cluster['articles']:
        total_tokens += estimate_tokens(article['title'])
        total_tokens += estimate_tokens(article['summary'])
        total_tokens += estimate_tokens(article['content'])
    return total_tokens

def limit_cluster_content(cluster, max_tokens=100000):  # Reduced from 124000 to 100000
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
    
    if total_tokens > 180000:  # Reduced from 220000 to 180000
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

def get_final_summary(cluster_summaries, sentences_final_summary, topic_prompt=None):
    openai_key = os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=openai_key)

    all_summaries = "\n\n".join(cluster_summaries)

    base_prompt = (
        "You are a News Overview Summarizer. I will provide you with a collection of news summaries, "
        "and I want you to condense this into a JSON object containing a list of stories. "
        "Limit it to 2-4 main stories, and add a miscellaneous one at the end if applicable. "
        "Each story should have a title and content. "
        "The title should be a concise and exciting headline that grabs the reader's attention and makes them want to read on. "
        "It should partially explain the situation while leaving some curiosity. "
        "The content must be a brief but complete summary of the story in text, "
        "formatted with bulletpoints. "
        "Each bulletpoint should be a key aspect of the story, and all bulletpoints should be part of a single text string. "
        f"Generate the content using {sentences_final_summary} sentences per story to fully explain the situation. "
    )

    if topic_prompt:
        base_prompt += (
            f"\n\nAdditional instructions from the topic owner: {topic_prompt}\n"
            "Please incorporate these instructions into your summary generation."
        )

    base_prompt += (
        "\nAlso give me three short questions that you could answer with the information in the summaries, to give users an idea of what to ask"
        "\nReturn your response in the following JSON structure: "
        "{'summary': [{'title': 'Title 1', 'content': '• Bulletpoint 1.\n\n• Bulletpoint 2.\n\n• Bulletpoint 3.'}, "
        "{'title': 'Title 2', 'content': '• Bulletpoint 1.\n\n• Bulletpoint 2.\n\n• Bulletpoint 3.'}, ...],"
        "'questions': ['Question one?', 'Question two?', 'Question three?'],"
        "'prompt': 'Original topic prompt if provided'}"
        "\nEnsure each story's content is a single text string with bulletpoints separated by spaces or new lines."
        "\nMake sure the questions are in that precise format, and expand properly upon the summaries."
    )

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=5000,
        temperature=0.125,
        messages=[
            {"role": "system", "content": base_prompt},
            {"role": "user", "content": all_summaries}
        ]
    )
    
    return completion.choices[0].message.content

def extract_braces_content(s):
    start_index = s.find('{')
    end_index = s.rfind('}')
        
    if start_index == -1 or end_index == -1:
        # If there is no '{' or '}', return an empty string or handle as needed
        return ""
        
    # Include the end_index in the slice by adding 1
    return s[start_index:end_index + 1]

def parse_input(input_string):
    # Safely evaluate the string to a dictionary
    data = ast.literal_eval(input_string)
    
    # Extract the summary and questions
    summary = data.get('summary', '')
    questions = data.get('questions', [])
    
    return summary, questions


# WIKIMEDIA STUFF HERE
'''
def extract_capitalized_words(text, insignificant_words):
    words = re.findall(r'\b[A-Z][a-z]+\b', text)
    return [word for word in words if word not in insignificant_words and len(word) > 1]

def get_sorted_unique_words(words):
    word_counts = Counter(words)
    return sorted(word_counts, key=word_counts.get, reverse=True)

def get_wikimedia_image(search_terms):
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": f"{' '.join(search_terms)} filetype:bitmap",
        "srnamespace": "6",
        "srlimit": "1"
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if data["query"]["search"]:
        file_name = data["query"]["search"][0]["title"]
        image_info_params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url",
            "titles": file_name
        }
        image_info_response = requests.get(base_url, params=image_info_params)
        image_data = image_info_response.json()
        
        pages = image_data["query"]["pages"]
        for page in pages.values():
            if "imageinfo" in page:
                return page["imageinfo"][0]["url"]
    
    return None

def get_image_for_item(item, insignificant_words):
    words = extract_capitalized_words(item['title'] + ' ' + item['content'], insignificant_words)
    sorted_words = get_sorted_unique_words(words)
    
    # Get top 5 common words
    top_5_words = sorted_words[:5]
    
    # Search for 4 most common, then 3, then 2
    for i in range(min(4, len(sorted_words)), 1, -1):
        search_terms = sorted_words[:i]
        image_url = get_wikimedia_image(search_terms)
        if image_url:
            # Check if at least two of the top 5 words are present in the file name
            matching_words = [word for word in top_5_words if word.lower() in image_url.lower()]
            if len(matching_words) >= 3:
                print(f"Found image for terms: {' '.join(search_terms)}")
                print(f"Image URL: {image_url}")
                print(f"Matching words in filename: {', '.join(matching_words)}")
                return image_url
    
    return None

'''

@contextmanager
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

            # Generate summaries for each cluster with retry mechanism
            cluster_summaries = {}
            for cluster in final_clusters:
                try:
                    key = ' '.join([word.capitalize() for word in cluster['common_words']])
                    summary = get_openai_response(cluster)  # This has built-in retry
                    cluster_summaries[key] = summary
                    logging.info(f"Generated summary for cluster: {key}")
                except Exception as e:
                    logging.error(f"Failed to generate summary for cluster {key}: {str(e)}")
                    cluster_summaries[key] = "Error generating summary for this cluster"

            # Generate final summary with error handling
            try:
                final_summary_json = get_final_summary(
                    list(cluster_summaries.values()),
                    sentences_final_summary,
                    topic.prompt if topic.prompt else None
                )
                final_summary_json = extract_braces_content(final_summary_json)
                final_summary_data = json.loads(final_summary_json)

            except Exception as e:
                logging.error(f"Error generating final summary for {topic.name}: {str(e)}")
                final_summary_data = {
                    "summary": [{"title": "Error", "content": "Failed to generate summary"}],
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

def process_all_topics(days_back=1, common_word_threshold=2, top_words_to_consider=3,
                      merge_threshold=2, min_articles=3, join_percentage=0.5,
                      final_merge_percentage=0.5, sentences_final_summary=3, title_only=False, all_words=False):
    logging.info("Starting process_all_topics")
    logging.info(f"Title-only mode: {title_only}")
    logging.info(f"All-words mode: {all_words}")
    
    try:
        active_organizations = Organization.objects.exclude(plan='inactive')
        
        for organization in active_organizations:
            logging.info(f"Processing organization: {organization.name}")
            
            try:
                Comment.objects.filter(writer__organization=organization).delete()
                logging.info(f"Deleted comments for organization: {organization.name}")
            except Exception as e:
                logging.error(f"Error deleting comments for {organization.name}: {str(e)}")
            
            for topic in organization.topics.all():
                try:
                    process_topic(topic, days_back, common_word_threshold, top_words_to_consider,
                                merge_threshold, min_articles, join_percentage,
                                final_merge_percentage, sentences_final_summary, title_only)
                except Exception as e:
                    logging.error(f"Failed to process topic {topic.name}: {str(e)}")
                    continue
                
    except Exception as e:
        logging.critical(f"Critical error in process_all_topics: {str(e)}")
    finally:
        logging.info("Finished process_all_topics")

if __name__ == "__main__":
    # This block will not be executed when imported as a module
    process_all_topics()
