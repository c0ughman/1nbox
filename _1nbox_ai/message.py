import os
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User
from datetime import datetime, timedelta
import json

# SendGrid setup
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

from django.template import Template, Context
from django.conf import settings

from django.template.loader import render_to_string

def render_email_template(user, topics, summaries):
    total_number_of_articles = sum(topic.number_of_articles for topic in topics)
    
    context = {
        'user': user,
        'topics': topics,
        'total_number_of_articles': total_number_of_articles,
    }
    
    return render_to_string('email_template.html', context)

def get_user_topics_summary(user):
    summaries = []
    topic_list = []
    for topic_name in user.topics:
        try:
            topic_obj = Topic.objects.get(name=topic_name)
            summary = json.loads(topic_obj.summary) if topic_obj.summary else []
            if user.negative_keywords:
                negative_list = user.negative_keywords.split(",")
                summary = [
                    item for item in summary 
                    if not any(word.lower() in item['content'].lower() for word in negative_list)
                ]
            topic_obj.summary = summary  # Attach the processed summary to the topic object
            summaries.append(summary)
            topic_list.append(topic_obj)
        except Topic.DoesNotExist:
            print(f"Topic '{topic_name}' does not exist and will be skipped.")
    
    return topic_list, summaries

def format_email_content(user, topics, summaries):
    return render_email_template(user, topics, summaries)

def send_email(user, subject, content):
    message = Mail(
        from_email='news@1nbox-ai.com',
        to_emails=user.email,
        subject=subject,
        html_content=content)
    try:
        response = sg.send(message)
        return True, response.status_code
    except Exception as e:
        return False, str(e)

def send_summaries():
    current_time = datetime.now().timestamp()
    
    for user in User.objects.exclude(plan="over"):
        days_since = (current_time - user.days_since) // (24 * 3600)
        
        topics, summaries = get_user_topics_summary(user)
        email_content = format_email_content(user, topics, summaries)
        success, result = send_email(user, f"Your Daily News Summaries", email_content)
        if success:
            print(f"Email sent to {user.email} with status code: {result}")
        else:
            print(f"Failed to send email to {user.email}. Error: {result}")

if __name__ == "__main__":
    send_summaries()
