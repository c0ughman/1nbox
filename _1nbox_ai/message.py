import os
import json
import logging
from datetime import datetime, timedelta, time
import pytz

from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from .models import Topic, User, Summary, Organization

logging.basicConfig(
    level=logging.ERROR,
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
    # We'll get the current UTC time once
    now_utc = datetime.now(pytz.utc)
    
    # Iterate over organizations
    for organization in Organization.objects.exclude(plan="inactive"):
        # 1) Check if local time == summary_time
        if not organization.summary_time or not organization.summary_timezone:
            # If we can’t do a time check, skip
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
                tzinfo=org_tz
            )

            # If local time is within ~1 minute of summary_time, proceed
            diff_seconds = abs((local_now - org_summary_today).total_seconds())
            if diff_seconds > 60:
                continue  # skip if not the correct time

        except Exception as e:
            logging.error(f"Time zone check error for organization {organization.name}: {str(e)}")
            continue

        # 2) If we get here, we want to send the email summary to that org’s users
        topics = get_user_topics_summary(organization)
        if not topics:
            logging.warning(f"No topics found for organization {organization.name}")
            continue
            
        total_number_of_articles = sum(
            t.summaries.first().number_of_articles 
            for t in topics 
            if t.summaries.first()
        )
        
        topic_names = [t.name for t in topics]
        
        users = organization.users.filter(send_email=True)
        for user in users:
            context = {
                'user': user,
                'topics': topics,
                'total_number_of_articles': total_number_of_articles,
            }
            email_content = render_to_string('email_template.html', context)

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
