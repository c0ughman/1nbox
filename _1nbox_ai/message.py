import os
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User
from datetime import datetime, timedelta

# SendGrid setup
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

from django.template import Template, Context
from django.conf import settings

def render_email_template(user, topics, summaries):
    # Load the HTML template
    with open(os.path.join(settings.BASE_DIR, 'templates/email_template.html'), 'r') as file:
        template_content = file.read()
    
    # Create a Django Template object
    template = Template(template_content)
    
    # Calculate total number of articles
    total_number_of_articles = sum(topic.number_of_articles for topic in topics)
    
    # Prepare the context
    context = Context({
        'user': user,
        'topics': topics,
        'total_number_of_articles': total_number_of_articles,
    })
    
    # Render the template
    return template.render(context)

def get_user_topics_summary(user):
    summaries = []
    topic_list = []
    for topic in user.topics:
        try:
            topic_obj = Topic.objects.get(name=topic)
            summary = topic_obj.summary
            if user.negative_keywords:
                negative_list = user.negative_keywords.split(",")
                summary_paragraphs = summary.split('\n\n')
                filtered_paragraphs = [
                    p for p in summary_paragraphs if not any(word.lower() in p.lower() for word in negative_list)
                ]
                summary = '\n\n'.join(filtered_paragraphs)     
            summaries.append(summary)
            topic_list.append(topic_obj)
        except Topic.DoesNotExist:
            print(f"Topic '{topic}' does not exist and will be skipped.")
    
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
        success, result = send_email(user, f"Your Daily News Summaries for {', '.join(user.topics)}", email_content)
        if success:
            print(f"Email sent to {user.email} with status code: {result}")
        else:
            print(f"Failed to send email to {user.email}. Error: {result}")

if __name__ == "__main__":
    send_summaries()
