import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
import re
import os
from openai import OpenAI
from collections import Counter
from .models import Topic, Organization, Summary
import json
import ast
import requests


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
    'Miscellaneous',


])

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
        feed = feedparser.parse(rss_url)
        if hasattr(feed, 'status') and feed.status != 200:
            print(f"Warning: RSS feed {rss_url} returned status {feed.status}")
            return []
            
        articles = []
        cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
        
        for entry in feed.entries:
            try:
                pub_date = get_publication_date(entry)
                if pub_date and pub_date >= cutoff_date:
                    favicon_url = f"https://www.google.com/s2/favicons?domain={rss_url}"
                    article = {
                        'title': entry.get('title', 'No Title'),
                        'link': entry.get('link', ''),
                        'published': str(pub_date),
                        'summary': entry.get('summary', ''),
                        'content': entry.get('content', [{'value': entry.get('summary', '')}])[0].get('value', ''),
                        'favicon': favicon_url
                    }
                    articles.append(article)
            except Exception as e:
                print(f"Error processing entry in {rss_url}: {str(e)}")
                continue
                
        return articles
    except Exception as e:
        print(f"Error fetching RSS feed {rss_url}: {str(e)}")
        return []

def extract_significant_words(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    words = []
    for sentence in sentences:
        sentence_words = re.findall(r'\b[A-Z][a-z]{1,}\b', sentence)
        words.extend(sentence_words[1:])  # Exclude the first word of each sentence
    
    words = [word for word in words if word not in INSIGNIFICANT_WORDS]
    
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

def get_openai_response(cluster, max_tokens=4000):
    openai_key = os.environ.get('OPENAI_KEY')
    if not openai_key:
        print("Warning: No OpenAI key found")
        return "Error: OpenAI key not configured"
        
    client = OpenAI(api_key=openai_key)

    def chunk_content(articles, max_chars=12000):  # OpenAI context limit approx
        chunks = []
        current_chunk = []
        current_length = 0
        
        for article in articles:
            article_content = (
                f"Title: {article.get('title', '')}\n"
                f"URL: {article.get('link', '')}\n"
                f"Summary: {article.get('summary', '')}\n"
                f"Content: {article.get('content', '')}\n\n"
            )
            
            content_length = len(article_content)
            
            if current_length + content_length > max_chars:
                chunks.append(current_chunk)
                current_chunk = [article_content]
                current_length = content_length
            else:
                current_chunk.append(article_content)
                current_length += content_length
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks

    def get_summary_for_chunk(chunk_content, retries=3):
        prompt = ("You are a News Facts Summarizer. Summarize these articles with key facts, "
                 "dates, names, and context. Include URLs in parentheses for each fact. "
                 "End with a 3-4 sentence overview of the big picture.")
        
        for attempt in range(retries):
            try:
                completion = client.chat.completions.create(
                    model="gpt-4-0125-preview",  # Use the latest model
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": chunk_content}
                    ],
                    max_tokens=2000,  # Reduced to ensure we stay within limits
                    temperature=0.125,
                )
                return completion.choices[0].message.content
            except Exception as e:
                if attempt == retries - 1:
                    print(f"Failed to get OpenAI response after {retries} attempts: {str(e)}")
                    return f"Error summarizing content: {str(e)}"
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        
        return "Error: Failed to generate summary"

    # Process in chunks
    chunks = chunk_content(cluster['articles'])
    summaries = []
    
    for chunk in chunks:
        chunk_content = f"Common words: {', '.join(cluster['common_words'])}\n\n" + ''.join(chunk)
        summary = get_summary_for_chunk(chunk_content)
        summaries.append(summary)
    
    # Combine summaries if we had multiple chunks
    if len(summaries) > 1:
        combined_summary = "\n\nContinued...\n\n".join(summaries)
        # Get a final summary if we had multiple chunks
        final_summary = get_summary_for_chunk(f"Please provide a unified summary of these related summaries:\n\n{combined_summary}")
        return final_summary
    
    return summaries[0] if summaries else "No content to summarize"


def get_final_summary(cluster_summaries, sentences_final_summary):
    openai_key = os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=openai_key)

    all_summaries = "\n\n".join(cluster_summaries)

    prompt = (
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
        "Return your response in the following JSON structure: "
        "{'summary': [{'title': 'Title 1', 'content': '• Bulletpoint 1.\n\n• Bulletpoint 2.\n\n• Bulletpoint 3.'}, "
        "{'title': 'Title 2', 'content': '• Bulletpoint 1.\n\n• Bulletpoint 2.\n\n• Bulletpoint 3.'}, ...]}."
        "Ensure each story's content is a single text string with bulletpoints separated by spaces or new lines."
    )


    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=5000,
        temperature=0.125,
        messages=[
            {"role": "system", "content": prompt},
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

def extract_capitalized_words(text, insignificant_words):
    words = re.findall(r'\b[A-Z][a-z]+\b', text)
    return [word for word in words if word not in insignificant_words and len(word) > 1]

def get_sorted_unique_words(words):
    word_counts = Counter(words)
    return sorted(word_counts, key=word_counts.get, reverse=True)

def get_wikimedia_image(search_terms, max_retries=3):
    base_url = "https://commons.wikimedia.org/w/api.php"
    
    for attempt in range(max_retries):
        try:
            params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": f"{' '.join(search_terms)} filetype:bitmap",
                "srnamespace": "6",
                "srlimit": "1"
            }
            
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("query", {}).get("search"):
                return None
                
            file_name = data["query"]["search"][0]["title"]
            
            image_info_params = {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url",
                "titles": file_name
            }
            
            image_info_response = requests.get(base_url, params=image_info_params, timeout=10)
            image_info_response.raise_for_status()
            image_data = image_info_response.json()
            
            pages = image_data.get("query", {}).get("pages", {})
            for page in pages.values():
                if "imageinfo" in page and page["imageinfo"]:
                    return page["imageinfo"][0]["url"]
                    
            return None
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Failed to fetch image after {max_retries} attempts: {str(e)}")
                return None
            time.sleep(2 ** attempt)  # Exponential backoff
            continue
            
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
    
def process_topic(topic, days_back=1, common_word_threshold=2, top_words_to_consider=3,
                  merge_threshold=2, min_articles=3, join_percentage=0.5,
                  final_merge_percentage=0.5, sentences_final_summary=3):
    """
    Process a topic to generate news summaries with complete error handling and resilience.
    Will always create a summary entry in the database, even in error conditions.
    """
    try:
        print(f"Processing topic: {topic.name}")
        
        if not topic.sources:
            print(f"Warning: No sources for topic {topic.name}")
            empty_summary = {
                "summary": [{
                    "title": "No News Sources",
                    "content": "• This topic has no configured news sources to monitor."
                }]
            }
            Summary.objects.create(
                topic=topic,
                final_summary=json.dumps(empty_summary),
                clusters=[],
                cluster_summaries={},
                number_of_articles=0,
            )
            return
            
        # Collect articles from all sources
        all_articles = []
        for url in topic.sources:
            try:
                articles = get_articles_from_rss(url, days_back)
                all_articles.extend(articles)
            except Exception as e:
                print(f"Error processing source {url}: {str(e)}")
                continue
                
        if not all_articles:
            print(f"Warning: No articles found for topic {topic.name}")
            empty_summary = {
                "summary": [{
                    "title": "No Recent News",
                    "content": "• No new articles were found for this topic in the specified time period."
                }]
            }
            Summary.objects.create(
                topic=topic,
                final_summary=json.dumps(empty_summary),
                clusters=[],
                cluster_summaries={},
                number_of_articles=0,
            )
            return

        # Process articles and extract significant words
        try:
            word_counts = Counter()
            for article in all_articles:
                try:
                    title_words = extract_significant_words(article.get('title', ''))
                    content_words = extract_significant_words(article.get('content', ''))
                    article['significant_words'] = title_words + [w for w in content_words if w not in title_words]
                    word_counts.update(article['significant_words'])
                except Exception as e:
                    print(f"Error processing article words: {str(e)}")
                    article['significant_words'] = []
            
            # Sort words by rarity
            for article in all_articles:
                try:
                    article['significant_words'] = sort_words_by_rarity(article['significant_words'], word_counts)
                except Exception as e:
                    print(f"Error sorting words: {str(e)}")
                    continue

            # Create initial clusters
            try:
                clusters = cluster_articles(all_articles, common_word_threshold, top_words_to_consider)
            except Exception as e:
                print(f"Error in initial clustering: {str(e)}")
                clusters = [{'common_words': ['Error'], 'articles': all_articles}]

            # Merge clusters
            try:
                merged_clusters = merge_clusters(clusters, merge_threshold)
            except Exception as e:
                print(f"Error merging clusters: {str(e)}")
                merged_clusters = clusters

            # Apply minimum articles requirement
            try:
                clusters_with_min_articles = apply_minimum_articles_and_reassign(
                    merged_clusters, min_articles, join_percentage
                )
            except Exception as e:
                print(f"Error applying minimum articles: {str(e)}")
                clusters_with_min_articles = merged_clusters

            # Final cluster merging
            try:
                final_clusters = merge_clusters_by_percentage(
                    clusters_with_min_articles, final_merge_percentage
                )
            except Exception as e:
                print(f"Error in final cluster merging: {str(e)}")
                final_clusters = clusters_with_min_articles

            # Generate summaries for each cluster
            cluster_summaries = {}
            for cluster in final_clusters:
                try:
                    key = ' '.join([word.capitalize() for word in cluster['common_words']])
                    summary = get_openai_response(cluster)
                    if summary:
                        cluster_summaries[key] = summary
                except Exception as e:
                    print(f"Error generating cluster summary: {str(e)}")
                    cluster_summaries[key] = "Error generating summary for this cluster."

            # Generate final summary
            try:
                if cluster_summaries:
                    final_summary_json = get_final_summary(
                        list(cluster_summaries.values()), 
                        sentences_final_summary
                    )
                    final_summary_json = extract_braces_content(final_summary_json)
                    final_summary_data = json.loads(final_summary_json)
                else:
                    final_summary_data = {
                        "summary": [{
                            "title": "Processing Error",
                            "content": "• An error occurred while generating summaries."
                        }]
                    }
            except Exception as e:
                print(f"Error in final summary generation: {str(e)}")
                final_summary_data = {
                    "summary": [{
                        "title": "Summary Generation Error",
                        "content": "• An error occurred while generating the final summary.\n• Raw articles were collected but could not be processed."
                    }]
                }

            # Process images for each summary item
            try:
                for item in final_summary_data['summary']:
                    try:
                        image_url = get_image_for_item(item, INSIGNIFICANT_WORDS)
                        if image_url:
                            item['image'] = image_url
                    except Exception as e:
                        print(f"Error getting image for summary item: {str(e)}")
                        continue
            except Exception as e:
                print(f"Error in image processing: {str(e)}")

            # Save to database with transaction
            try:
                from django.db import transaction
                with transaction.atomic():
                    new_summary = Summary.objects.create(
                        topic=topic,
                        final_summary=json.dumps(final_summary_data),
                        clusters=final_clusters,
                        cluster_summaries=cluster_summaries,
                        number_of_articles=len(all_articles),
                    )
                print(f"Successfully created summary for {topic.name}")
                return new_summary
            except Exception as e:
                print(f"Error saving summary to database: {str(e)}")
                # Try one more time with minimal data
                try:
                    Summary.objects.create(
                        topic=topic,
                        final_summary=json.dumps({
                            "summary": [{
                                "title": "Database Error",
                                "content": "• The summary was generated but could not be saved properly.\n• Please try again later."
                            }]
                        }),
                        clusters=[],
                        cluster_summaries={},
                        number_of_articles=len(all_articles),
                    )
                except Exception as final_e:
                    print(f"Critical error saving to database: {str(final_e)}")

        except Exception as e:
            print(f"Error in main processing loop: {str(e)}")
            error_summary = {
                "summary": [{
                    "title": "Processing Error",
                    "content": f"• An error occurred while processing this topic's news feed.\n• Error: {str(e)}"
                }]
            }
            try:
                Summary.objects.create(
                    topic=topic,
                    final_summary=json.dumps(error_summary),
                    clusters=[],
                    cluster_summaries={},
                    number_of_articles=0,
                )
            except Exception as db_error:
                print(f"Could not save error summary: {str(db_error)}")

    except Exception as outer_e:
        print(f"Critical error in process_topic for {topic.name}: {str(outer_e)}")
        try:
            Summary.objects.create(
                topic=topic,
                final_summary=json.dumps({
                    "summary": [{
                        "title": "Critical Error",
                        "content": "• A critical error occurred while processing this topic.\n• Please contact support if this persists."
                    }]
                }),
                clusters=[],
                cluster_summaries={},
                number_of_articles=0,
            )
        except Exception as final_e:
            print(f"Could not save critical error summary: {str(final_e)}")

def process_all_topics(days_back=1, common_word_threshold=2, top_words_to_consider=3,
                       merge_threshold=2, min_articles=3, join_percentage=0.5,
                       final_merge_percentage=0.5, sentences_final_summary=3):
                           
       # Get all organizations that are not inactive
    active_organizations = Organization.objects.exclude(plan='inactive')       # Check for how we will handle inactive later
    
    # Process topics for all active organizations
    for organization in active_organizations:
        for topic in organization.topics.all():
            process_topic(topic, days_back, common_word_threshold, top_words_to_consider,
                         merge_threshold, min_articles, join_percentage,
                         final_merge_percentage, sentences_final_summary)
                
if __name__ == "__main__":
    # This block will not be executed when imported as a module
    process_all_topics()
