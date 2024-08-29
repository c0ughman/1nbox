import os
import json
import logging
from datetime import datetime
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User

# Set up logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# SendGrid setup
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

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

    print(f"Topics for user {user.id}: {user.topics}")  # Debugging statement

    if not user.topics:
        print(f"User {user.id} has no topics.")
        return []

    for topic_name in user.topics:
        try:
            topic_obj = Topic.objects.get(name=topic_name)

            # Parse summary field which is a JSON string
            if topic_obj.summary and topic_obj.summary.strip():
                try:
                    summary_data = json.loads(topic_obj.summary)
                    summary = summary_data.get('summary', [])
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON for topic '{topic_name}': {e}")
                    logging.error(f"Raw summary data: {topic_obj.summary}")
                    summary = []
            else:
                summary = []

            # Filter out summaries containing negative keywords if specified
            if user.negative_keywords:
                negative_list = user.negative_keywords.split(",")
                summary = [
                    item for item in summary 
                    if not any(word.lower() in item['content'].lower() for word in negative_list)
                ]

            # Attach the processed summary to the topic object
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

def get_custom_message(days_since):
    messages = {
        3: {
            "title": "How's it going?",
            "content": "We hope you're enjoying your news summaries. Any feedback?",
            "buttontext": "Give Feedback",
            "image": "https://example.com/feedback_image.jpg"
        },
        7: {
            "title": "Loving the news?",
            "content": "We'd love to hear your thoughts on our service so far!",
            "buttontext": "Share Your Experience"
        },
        10: {
            "title": "Quick check-in",
            "content": "Is there anything we can improve? Let us know!",
            "buttontext": "Suggest Improvements"
        },
        14: {
            "title": "Two weeks of news!",
            "content": "You've been with us for two weeks now. How are we doing?",
            "buttontext": "Rate Us"
        },
        20: {
            "title": "You're a news pro!",
            "content": "Thanks for being with us for 20 days. Any topics you'd like to add?",
            "buttontext": "Customize Topics"
        }
    }
    return messages.get(days_since, None)

def send_summaries():
    current_time = datetime.now().timestamp()

    for user in User.objects.exclude(plan="over"):
        # Calculate days since last update
        days_since = int((current_time - user.days_since) // (24 * 3600))

        # Get custom message based on days_since
        custom_message = get_custom_message(days_since)

        # Get summaries for the user
        topics = get_user_topics_summary(user)

        # Include custom_message in the context
        context = {
            'user': user,
            'topics': topics,
            'total_number_of_articles': sum(topic.number_of_articles for topic in topics),
            'custom_message': custom_message
        }

        email_content = render_to_string('email_template.html', context)

        # Send the email
        success, result = send_email(user, f"Today in {','.join(user.topics)}", email_content)
        if success:
            print(f"Email sent to {user.email} with status code: {result}")
        else:
            print(f"Failed to send email to {user.email}. Error: {result}")

if __name__ == "__main__":
    send_summaries()
