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
    feed = feedparser.parse(rss_url)
    articles = []
    cutoff_date = datetime.now(pytz.utc) - timedelta(days=days_back)
    for entry in feed.entries:
        pub_date = get_publication_date(entry)
        if pub_date and pub_date >= cutoff_date:
            favicon_url = f"https://www.google.com/s2/favicons?domain={rss_url}"
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': str(pub_date),
                'summary': entry.summary if 'summary' in entry else '',
                'content': entry.content[0].value if 'content' in entry else entry.get('summary', ''),
                'favicon': favicon_url
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

def limit_cluster_content(cluster, max_tokens=100000):  # Reduced significantly for safety
    """
    Limits cluster content to stay within token limits while preserving the most recent articles.
    
    Args:
        cluster (dict): The cluster containing articles
        max_tokens (int): Maximum number of tokens allowed
    
    Returns:
        dict: A new cluster with articles limited to fit within token limit
    """
    # Account for prompt overhead and formatting
    overhead_tokens = 1000  # Reserve tokens for prompt and formatting
    available_tokens = max_tokens - overhead_tokens
    
    # Estimate tokens more conservatively
    def estimate_tokens(text):
        # Count words plus extra for special characters and formatting
        return int(len(text.split()) * 1.3)  # 30% overhead for safety
    
    cluster_headers = f"Common words: {', '.join(cluster['common_words'])}\n\n"
    header_tokens = estimate_tokens(cluster_headers)
    available_tokens = available_tokens - header_tokens
    
    # Sort articles by publication date (newest first)
    sorted_articles = sorted(cluster['articles'], 
                           key=lambda x: datetime.fromisoformat(x['published'].replace('Z', '+00:00')),
                           reverse=True)
    
    limited_articles = []
    current_tokens = 0
    
    for article in sorted_articles:
        # Calculate tokens including formatting
        article_content = (
            f"Title: {article['title']}\n"
            f"URL: {article['link']}\n"
            f"Summary: {article['summary']}\n"
            f"Content: {article['content']}\n\n"
        )
        
        article_tokens = estimate_tokens(article_content)
        
        if current_tokens + article_tokens <= available_tokens:
            limited_articles.append(article)
            current_tokens += article_tokens
        else:
            break
    
    return {
        'common_words': cluster['common_words'],
        'articles': limited_articles
    }

def get_openai_response(cluster, max_tokens=4000):
    openai_key = os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=openai_key)

    # Use a more conservative token limit
    limited_cluster = limit_cluster_content(cluster, max_tokens=100000)
    
    cluster_content = f"Common words: {', '.join(limited_cluster['common_words'])}\n\n"
    current_tokens = 0
    sub_clusters = []
    current_sub_cluster = []

    # Reduce max_tokens for sub-clusters to account for overhead
    sub_cluster_max_tokens = 3000  # Reduced from 4000

    for article in limited_cluster['articles']:
        article_content = (
            f"Title: {article['title']}\n"
            f"URL: {article['link']}\n"
            f"Summary: {article['summary']}\n"
            f"Content: {article['content']}\n\n"
        )
        
        article_tokens = len(article_content.split()) * 1.3  # Conservative estimate
        
        if current_tokens + article_tokens > sub_cluster_max_tokens:
            if current_sub_cluster:  # Only append if there's content
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
        
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=4000,  # Reduced from 5000
            temperature=0.125,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": sub_cluster_content}
            ]
        )
        summaries.append(completion.choices[0].message.content)

    return ' '.join(summaries)

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
    
def process_topic(topic, days_back=1, common_word_threshold=2, top_words_to_consider=3,
                  merge_threshold=2, min_articles=3, join_percentage=0.5,
                  final_merge_percentage=0.5, sentences_final_summary=3):
    print(f"RUNNING PROCESS TOPIC FOR --- {topic.name}!!!!!")

    if topic.sources:
        
        all_articles = []
        for url in topic.sources:
            all_articles.extend(get_articles_from_rss(url, days_back))
    
        # Count the number of articles
        number_of_articles = len(all_articles)
    
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
    
        # Merge clusters based on merge_threshold
        merged_clusters = merge_clusters(clusters, merge_threshold)
    
        # Apply minimum articles per cluster and reassign miscellaneous articles
        clusters_with_min_articles = apply_minimum_articles_and_reassign(merged_clusters, min_articles, join_percentage)
    
        # Merge clusters based on join_percentage
        final_clusters = merge_clusters_by_percentage(clusters_with_min_articles, final_merge_percentage)
    
        # Print the clusters
        print_clusters(final_clusters)
        
        # Get OpenAI summaries for each cluster
        cluster_summaries = {}
        for cluster in final_clusters:
            key = ' '.join([word.capitalize() for word in cluster['common_words']])
            summary = get_openai_response(cluster)
            print(summary)
            print("                       ")
            print("                       ")
            print("                       ")
            cluster_summaries[key] = summary
    
        # Get the final summary
        final_summary_json = get_final_summary(list(cluster_summaries.values()), sentences_final_summary)
        print(final_summary_json)
        final_summary_json = extract_braces_content(final_summary_json)
        print(final_summary_json)
        
        # Parse the JSON
        final_summary_data = json.loads(final_summary_json)
        
        # Process each item in the summary
        for item in final_summary_data['summary']:
            image_url = get_image_for_item(item, INSIGNIFICANT_WORDS)
            if image_url:
                item['image'] = image_url
                
        new_summary = Summary.objects.create(
            topic=topic,
            final_summary=final_summary_data,
            clusters=final_clusters,
            cluster_summaries=cluster_summaries,
            number_of_articles=number_of_articles,
        )

        print(f"SUMMARY for {topic.name} created:")
        print(final_summary_data)

    else:
        print("OJO - Topic has no sources")

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
