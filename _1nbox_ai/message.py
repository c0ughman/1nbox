import os
import json
from datetime import datetime
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User

# SendGrid setup
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

import re
from collections import Counter

def extract_capitalized_words(title, content):
    # Exclude one-letter words, months, and days of the week
    exclude_words = set(['A', 'I'] + [month.upper() for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']] + [day.upper() for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']])
    
    # Extract capitalized words from title
    title_words = re.findall(r'\b[A-Z][a-zA-Z]*\b', title)
    
    # Extract capitalized words from content (excluding those starting a sentence)
    content_words = re.findall(r'(?<=[.!?]\s)\b[A-Z][a-zA-Z]*\b|\s\b[A-Z][a-zA-Z]*\b', content)
    
    # Combine and filter words
    all_words = [word for word in title_words + content_words if word not in exclude_words and len(word) > 1]
    
    return all_words

def get_top_three_words(words):
    word_counts = Counter(words)
    top_three = word_counts.most_common(3)
    return ', '.join([word for word, _ in top_three])

import requests

def get_wikimedia_image(search_terms):
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": search_terms,
        "srnamespace": "6",  # File namespace
        "srlimit": "1",
        "srwhat": "text",
        "srprop": "url",
    }
    
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if 'query' in data and 'search' in data['query'] and len(data['query']['search']) > 0:
        file_name = data['query']['search'][0]['title']
        file_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{file_name}"
        return file_url
    
    return None

def render_email_template(user, topics):
    total_number_of_articles = sum(topic.number_of_articles for topic in topics)
    
    context = {
        'user': user,
        'topics': topics,
        'total_number_of_articles': total_number_of_articles,
    }
    
    return render_to_string('email_template.html', context)

def get_user_topics_summary(user):
    topic_list = []
    
    for topic_name in user.topics:
        try:
            topic_obj = Topic.objects.get(name=topic_name)
            
            if topic_obj.summary:
                summary = json.loads(topic_obj.summary).get('summary', [])
            else:
                summary = []
            
            if user.negative_keywords:
                negative_list = user.negative_keywords.split(",")
                summary = [
                    item for item in summary 
                    if not any(word.lower() in item['content'].lower() for word in negative_list)
                ]
            
            # Process each item in the summary
            for item in summary:
                capitalized_words = extract_capitalized_words(item['title'], item['content'])
                search_terms = get_top_three_words(capitalized_words)
                image_url = get_wikimedia_image(search_terms)
                item['image_url'] = image_url
            
            topic_obj.summary = summary
            topic_list.append(topic_obj)
        except Topic.DoesNotExist:
            print(f"Topic '{topic_name}' does not exist and will be skipped.")
    
    return topic_list

def format_email_content(user, topics):
    return render_email_template(user, topics)

def send_email(user, subject, content):
    message = Mail(
        from_email='news@1nbox-ai.com',
        to_emails=user.email,
        subject=subject,
        html_content=content
    )
    try:
        response = sg.send(message)
        return True, response.status_code
    except Exception as e:
        return False, str(e)

def send_summaries():
    current_time = datetime.now().timestamp()
    
    for user in User.objects.exclude(plan="over"):
        # Calculate days since last update
        days_since = (current_time - user.days_since) // (24 * 3600)
        
        # Get summaries for the user
        topics = get_user_topics_summary(user)
        email_content = format_email_content(user, topics)
        
        # Send the email
        success, result = send_email(user, f"Today in {','.join(user.topics)}", email_content)
        if success:
            print(f"Email sent to {user.email} with status code: {result}")
        else:
            print(f"Failed to send email to {user.email}. Error: {result}")

if __name__ == "__main__":
    send_summaries()
