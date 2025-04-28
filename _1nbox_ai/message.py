import os
import json
import logging
from datetime import datetime, timedelta, time
import pytz
import random

from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User, Summary, Organization

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

            # Process the summary content
            if latest_summary.final_summary:
                if isinstance(latest_summary.final_summary, dict):
                    summary_data = latest_summary.final_summary.get('summary', [])
                    
                    # Reformat bulletpoints
                    for item in summary_data:
                        if 'content' in item:
                            parts = item['content'].split('•')
                            processed_content = parts[0]
                            for part in parts[1:]:
                                if part.strip():
                                    processed_content += '\n\n• ' + part.strip()
                            item['content'] = processed_content
                    latest_summary.final_summary = summary_data
            else:
                latest_summary.final_summary = []

            # Filter out negative keywords if needed
            if topic.negative_keywords:
                negative_list = [word.strip().lower() for word in topic.negative_keywords.split(",")]
                latest_summary.final_summary = [
                    item for item in latest_summary.final_summary 
                    if not any(word in item['content'].lower() for word in negative_list)
                ]

            topic_list.append(topic)

        except Topic.DoesNotExist:
            print(f"Topic '{topic.name}' does not exist and will be skipped.")
            
    return topic_list

def send_email(user, subject, content):
    message = Mail(
        from_email=('feed@trybriefed.com', 'Briefed'),  # <-- this part
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

sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
sg = SendGridAPIClient(sendgrid_api_key)

def send_summaries():
    """
    Main function to process and send summaries for all active organizations.
    """
    logging.info("==== Starting send_summaries ====")

    # Get current UTC time
    now_utc = datetime.now(pytz.utc)
    logging.info(f"Current UTC Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")

    for organization in Organization.objects.exclude(plan="inactive"):
        # 1) Check if summary_time and timezone are available
        if not organization.summary_time or not organization.summary_timezone:
            logging.warning(f"Skipping {organization.name} - Missing summary_time or timezone.")
            continue

        try:
            org_tz = pytz.timezone(organization.summary_timezone)
            local_now = now_utc.astimezone(org_tz)

            org_summary_today = datetime(
                year=local_now.year,
                month=local_now.month,
                day=local_now.day,
                hour=organization.summary_time.hour,
                minute=organization.summary_time.minute,
                second=0,  # Explicitly setting seconds to 0
                tzinfo=org_tz
            )

            # Compare ONLY hours and minutes (ignore seconds)
            if local_now.hour != org_summary_today.hour or local_now.minute != org_summary_today.minute:
                logging.info(f"❌ Skipping {organization.name} - Time did not match (Expected {org_summary_today.strftime('%H:%M')}, Got {local_now.strftime('%H:%M')})")
                continue

            logging.info(f"✅ Time Matched for {organization.name} - Proceeding with email sending.")

        except Exception as e:
            logging.error(f"❌ Time zone check error for {organization.name}: {str(e)}")
            continue

        # 2) If we get here, we want to send the email summary to that org’s users
        topics = get_user_topics_summary(organization)
        if not topics:
            logging.warning(f"❌ No topics found for organization {organization.name}. Skipping email.")
            continue
            
        total_number_of_articles = sum(
            t.summaries.first().number_of_articles 
            for t in topics 
            if t.summaries.first()
        )

        topic_names = [t.name for t in topics]
        users = organization.users.filter(send_email=True)

        if not users:
            logging.warning(f"❌ No users opted to receive emails in {organization.name}. Skipping email.")
            continue

        for user in users:
            context = {
                'user': user,
                'topics': topics,
                'total_number_of_articles': total_number_of_articles,
            }
            email_content = render_to_string('email_template.html', context)

            reading_time = max(1, len(topics))  # At least 1 minute, 1 minute per topic
            
            success, result = send_email(
                user,
                f"Your Daily Edge ({reading_time} min)",
                email_content
            )

            if success:
                logging.info(f"✅ Email sent to {user.email} with status code: {result}")
            else:
                logging.error(f"❌ Failed to send email to {user.email}. Error: {result}")

    logging.info("==== Finished send_summaries ====")

if __name__ == "__main__":
    send_summaries()
