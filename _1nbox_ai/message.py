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

def parse_summary_json(summary_string):
    """Helper function to parse JSON summary and handle common errors"""
    try:
        # Remove any extra escaping that might be present
        summary_string = summary_string.replace('\\"', '"').replace('\\\\', '\\')
        # Parse the JSON
        summary_data = json.loads(summary_string)
        return summary_data.get('summary', [])
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON summary: {e}")
        logging.error(f"Raw summary string: {summary_string}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error parsing summary: {e}")
        return []

def get_user_topics_summary(organization):
    """Get processed summaries for all topics in an organization"""
    topic_list = []
    
    if not organization.topics.exists():
        logging.warning(f"Organization {organization.id} has no topics")
        return []

    for topic in organization.topics.all():
        try:
            latest_summary = topic.summaries.first()
            if not latest_summary:
                logging.warning(f"No summaries found for topic {topic.name}")
                continue

            if latest_summary.final_summary:
                try:
                    # Parse and store the summary
                    summary_list = parse_summary_json(latest_summary.final_summary)
                    
                    # Filter negative keywords if needed
                    if topic.negative_keywords:
                        negative_list = [kw.strip().lower() for kw in topic.negative_keywords.split(",")]
                        summary_list = [
                            item for item in summary_list 
                            if not any(word in item['content'].lower() for word in negative_list)
                        ]
                    
                    # Add processed summary as a property
                    setattr(latest_summary, 'processed_summary', summary_list)
                    topic_list.append(topic)
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse JSON for topic {topic.name}: {e}")
                    continue
            else:
                logging.warning(f"Empty summary for topic {topic.name}")
                
        except Exception as e:
            logging.error(f"Error processing topic {topic.name}: {e}")
            continue

    return topic_list

def send_email(user, subject, content):
    """Send email using SendGrid"""
    message = Mail(
        from_email='news@1nbox-ai.com',
        to_emails=user.email,
        subject=subject,
        html_content=content
    )
    
    try:
        response = sg.send(message)
        logging.info(f"Email sent successfully to {user.email}")
        return True, response.status_code
    except Exception as e:
        logging.error(f"Failed to send email to {user.email}: {e}")
        return False, str(e)

def send_summaries():
    """Main function to send summary emails to all users"""
    try:
        # Get all active organizations
        organizations = Organization.objects.exclude(plan="inactive")
        
        for organization in organizations:
            try:
                # Get processed topics and summaries
                topics = get_user_topics_summary(organization)
                
                if not topics:
                    logging.warning(f"No valid topics found for organization {organization.id}")
                    continue
                
                # Calculate total number of articles
                total_number_of_articles = sum(
                    topic.summaries.first().number_of_articles 
                    for topic in topics 
                    if topic.summaries.exists()
                )

                # Get all users in the organization
                users = organization.users.all()
                
                for user in users:
                    try:
                        # Prepare email context
                        context = {
                            'user': user,
                            'topics': topics,
                            'total_number_of_articles': total_number_of_articles,
                        }
                        
                        # Render email template
                        email_content = render_to_string('email_template.html', context)
                        
                        # Create subject line with topic names
                        topic_names = ", ".join(topic.name for topic in topics)
                        subject = f"Today in {topic_names}"
                        
                        # Send email
                        success, result = send_email(user, subject, email_content)
                        
                        if success:
                            logging.info(f"Email sent to {user.email} with status {result}")
                        else:
                            logging.error(f"Failed to send email to {user.email}: {result}")
                            
                    except Exception as e:
                        logging.error(f"Error processing user {user.email}: {e}")
                        continue
                        
            except Exception as e:
                logging.error(f"Error processing organization {organization.id}: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Fatal error in send_summaries: {e}")
        raise

if __name__ == "__main__":
    send_summaries()
