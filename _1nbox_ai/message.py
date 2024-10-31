import os
import json
import logging
from datetime import datetime
from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User, Summary, Organization

# Set up logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# SendGrid setup
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

def get_user_topics_summary(organization):
    """
    Get summaries for all topics in an organization.
    Returns a list of topics with their processed summaries.
    """
    topic_list = []
    topic_names = ", ".join(organization.topics.all().values_list('name', flat=True))
    print(f"Topics for organization {organization.name} ({organization.id}): {topic_names}")
    
    if not organization.topics.exists():
        print(f"Organization {organization.name} ({organization.id}) has no topics.")
        return []

    for topic in organization.topics.all():
        try:
            latest_summary = topic.summaries.first()
            if not latest_summary:
                continue

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
    """
    Send an email using SendGrid.
    Returns a tuple of (success, result).
    """
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
        logging.error(f"Failed to send email to {user.email}: {str(e)}")
        return False, str(e)

def send_summaries():
    """
    Main function to process and send summaries for all active organizations.
    """
    current_time = datetime.now().timestamp()
    
    # Process all organizations that are paying
    for organization in Organization.objects.exclude(plan="inactive"):
        # Get the topics for the organization
        topics = get_user_topics_summary(organization)
        
        if not topics:
            logging.warning(f"No topics found for organization {organization.name}")
            continue
            
        # Calculate total number of articles
        total_number_of_articles = sum(
            topic.summaries.first().number_of_articles 
            for topic in topics 
            if topic.summaries.first()
        )
        
        # Get topic names for email subject
        topic_names = [topic.name for topic in topics]
        
        # Process all users in the organization
        users = organization.users.all()
        for user in users:
            # Prepare email context
            context = {
                'user': user,
                'topics': topics,
                'total_number_of_articles': total_number_of_articles,
            }
    
            # Generate email content from template
            email_content = render_to_string('email_template.html', context)
    
            # Send the email
            success, result = send_email(
                user,
                f"Today in {', '.join(topic_names)}",
                email_content
            )
            
            if success:
                print(f"Email sent to {user.email} with status code: {result}")
            else:
                logging.error(f"Failed to send email to {user.email}. Error: {result}")

if __name__ == "__main__":
    send_summaries()
