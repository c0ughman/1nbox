import feedparser
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
import re
import os
from openai import OpenAI
from collections import Counter
from .models import Topic, User
import json
import ast


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
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': pub_date,
                'summary': entry.summary if 'summary' in entry else '',
                'content': entry.content[0].value if 'content' in entry else entry.get('summary', '')
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

def get_openai_response(cluster, max_tokens=4000):
    openai_key = os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=openai_key)

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
            max_tokens=1000,
            temperature=0.125,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": sub_cluster_content}
            ]
        )
        summaries.append(completion.choices[0].message.content)

    return ' '.join(summaries)

def get_final_summary(topic, cluster_summaries, sentences_final_summary):
    openai_key = os.environ.get('OPENAI_KEY')
    client = OpenAI(api_key=openai_key)

    all_summaries = "\n\n".join(cluster_summaries)

    prompt = ("You are a News Overview Summarizer. I will give you "
              "what happened in the news today and I want you to give a direct and simple summary "
              "for each group of events portrayed. "
              "You will mix up similar topics together to not repeat yourself. "
              f"{topic.prompt}"
              f"Give me {sentences_final_summary} sentences per topic giving a full explanation of the situation. "
              "Additionally, provide three follow-up questions that could be answered with the provided information. "
              "Return your response as a JSON object with two fields: 'summary' and 'questions'. "
              "The structure should be like this {'summary':The full summary as a formatted text, not a dictionary but a text with titles and line breaks,'questions':['question 1', 'question 2', 'question 3']} "
              "The fields MUST be named 'summary' and 'questions' exactly variating from those names is prohibited. Variating from the structure is prohibited"
              "The 'questions' field should be an array of three strings. Thanks a lot.")

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=350,
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

def process_topic(topic, days_back=1, common_word_threshold=2, top_words_to_consider=3,
                  merge_threshold=2, min_articles=3, join_percentage=0.5,
                  final_merge_percentage=0.5, sentences_final_summary=3):

    print(f"RUNNING PROCESS TOPIC FOR --- {topic.name}!!!!!")

    if topic.sources:                  
        all_articles = []
        for url in topic.sources:
            all_articles.extend(get_articles_from_rss(url, days_back))
    
        # Count the number of articles
        topic.number_of_articles = len(all_articles)
    
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
        final_summary_json = get_final_summary(topic, list(cluster_summaries.values()), sentences_final_summary)
        print(final_summary_json)
        final_summary_json = extract_braces_content(final_summary_json)
        print(final_summary_json)
        summary, questions = parse_input(final_summary_json)
        topic.summary = summary
        topic.questions = '\n'.join(questions)             
    
        print(f"SUMMARY for {topic.name}")
        print(topic.summary)
        print(f"QUESTIONS for {topic.name}")
        print(topic.questions)
    
        # Update the Topic instance
        topic.cluster_summaries = cluster_summaries
        if topic.children.exists():
            
            for child in topic.children.all():
                
                child.cluster_summaries = cluster_summaries
                child.number_of_articles = number_of_articles
                child.save()
                
        topic.save()
        
    else:
        
        if topic.cluster_summaries:
            
            final_summary_json = get_final_summary(topic, topic.cluster_summaries, sentences_final_summary)

            print(final_summary_json)
            final_summary_json = extract_braces_content(final_summary_json)
            print(final_summary_json)
            summary, questions = parse_input(final_summary_json)
            topic.summary = summary
            topic.questions = '\n'.join(questions)             
        
            print(f"SUMMARY for {topic.name}")
            print(topic.summary)
            print(f"QUESTIONS for {topic.name}")
            print(topic.questions)

            # Update the Topic instance
            topic.save()

        else: 
            print("!!OJO!! - No sources and no cluster summaries")

def process_all_topics(days_back=1, common_word_threshold=2, top_words_to_consider=3,
                       merge_threshold=2, min_articles=3, join_percentage=0.5,
                       final_merge_percentage=0.5, sentences_final_summary=3):
    # Get topics with children first
    topics_with_children = Topic.objects.filter(children__isnull=False).distinct()
    # Get topics without children
    topics_without_children = Topic.objects.filter(children__isnull=True)

    # Combine the two querysets, topics with children first
    all_topics = list(topics_with_children) + list(topics_without_children)

    for topic in all_topics:
        if User.objects.filter(topics__contains=topic.name).exists():
            process_topic(topic, days_back, common_word_threshold, top_words_to_consider,
                          merge_threshold, min_articles, join_percentage,
                          final_merge_percentage, sentences_final_summary)

if __name__ == "__main__":
    # This block will not be executed when imported as a module
    process_all_topics()
