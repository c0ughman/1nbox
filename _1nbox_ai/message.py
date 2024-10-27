import os
import json
import logging
from datetime import datetime
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User, Summary, Organization

# Set up logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# SendGrid setup
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

def get_user_topics_summary(organization):
    topic_list = []

    topic_names = ", ".join(organization.topics.all().values_list('name', flat=True))
    print(f"Topics for organization {organization.name} ({organization.id}): {topic_names}")
    
    if not organization.topics:
        print(f"Organization {organization.name} ({organization.id}) has no topics.")
        return []

    for topic in organization.topics.all():
        try:

            latest_summary = topic.summaries.first()
            final_summary = latest_summary.final_summary
            
            # Parse summary field which is a JSON string
            if final_summary and final_summary.strip():
                try:
                    summary_data = json.loads(final_summary)
                    summary = summary_data.get('summary', [])
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON for topic '{topic.name}': {e}")
                    logging.error(f"Raw summary data: {final_summary}")
                    summary = []
            else:
                summary = []

            # Filter out summaries containing negative keywords if specified
            if topic.negative_keywords:
                negative_list = topic.negative_keywords.split(",")
                summary = [
                    item for item in summary 
                    if not any(word.lower() in item['content'].lower() for word in negative_list)
                ]

            # Attach the processed summary to the topic object
            latest_summary.final_summary = summary  
            topic_list.append(topic)
        except Topic.DoesNotExist:
            print(f"Topic '{topic.name}' does not exist and will be skipped.")

    return topic_list

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

    # for all organizations that are paying 
    for organization in Organization.objects.exclude(plan="inactive"):

        # get the topics for the organization
        topics = get_user_topics_summary(organization) 

        total_number_of_articles = 0
        for topic in topics:
            latest_summary = topic.summaries.first()
            total_number_of_articles += latest_summary.number_of_articles

        # for all users in that organization
        users = organization.users.all()
        for user in users:
        
            # Include custom_message in the context
            context = {
                'user': user,
                'topics': topics,
                'total_number_of_articles': total_number_of_articles,
            }
    
            email_content = render_to_string('email_template.html', context)
    
            # Send the email
            topic_names = ", ".join([topic.name for topic in topics])
            success, result = send_email(user, f"Today in {topic_names}", email_content)
            if success:
                print(f"Email sent to {user.email} with status code: {result}")
            else:
                print(f"Failed to send email to {user.email}. Error: {result}")

if __name__ == "__main__":
    send_summaries()
