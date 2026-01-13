import os
import json
import logging
from datetime import datetime, timedelta
import pytz

from django.template.loader import render_to_string
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from .models import Topic, User, Organization, BitesSubscription, BitesDigest
from .bites_views import generate_digest_content

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bites_scheduler.log'),
        logging.StreamHandler()
    ]
)


def get_or_generate_digest(topic, frequency):
    today = datetime.now().date()

    existing = BitesDigest.objects.filter(
        topic=topic,
        digest_type=frequency,
        digest_date=today
    ).first()

    if existing:
        logging.info(f"Using cached digest for {topic.name} ({frequency})")
        return existing.content, existing.article_count

    logging.info(f"Generating new digest for {topic.name} ({frequency})")
    result = generate_digest_content(topic, frequency)

    if not result:
        logging.warning(f"No content generated for {topic.name}")
        return None, 0

    BitesDigest.objects.update_or_create(
        topic=topic,
        digest_type=frequency,
        digest_date=today,
        defaults={
            'content': result['content'],
            'article_count': result['article_count']
        }
    )

    return result['content'], result['article_count']


def send_bites_email(user, topic, digest_content, frequency):
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
    if not sendgrid_api_key:
        logging.error("SendGrid API key not found")
        return False

    sg = SendGridAPIClient(sendgrid_api_key)

    period = "Daily" if frequency == "daily" else "Weekly"
    subject = f"Your {period} {topic.name} Digest"

    summary = digest_content.get('summary', '')
    sections = digest_content.get('sections', [])

    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #1a1a1a; font-size: 24px; margin-bottom: 8px; }}
            h2 {{ color: #444; font-size: 18px; margin-top: 24px; margin-bottom: 12px; border-bottom: 1px solid #eee; padding-bottom: 8px; }}
            .summary {{ background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 24px; }}
            .section {{ margin-bottom: 20px; }}
            .headline {{ font-weight: 600; color: #1a1a1a; }}
            .article {{ margin: 8px 0; padding-left: 12px; border-left: 3px solid #007bff; }}
            .article a {{ color: #007bff; text-decoration: none; }}
            .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #eee; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <h1>{topic.name} - {period} Digest</h1>
        <div class="summary">{summary}</div>
    """

    for section in sections:
        category = section.get('category', 'News')
        headline = section.get('headline', '')
        section_summary = section.get('summary', '')
        key_articles = section.get('key_articles', [])

        html_content += f"""
        <div class="section">
            <h2>{category}</h2>
            <p class="headline">{headline}</p>
            <p>{section_summary}</p>
        """

        for article in key_articles[:3]:
            title = article.get('title', '')
            url = article.get('url', '#')
            why = article.get('why_important', '')
            html_content += f"""
            <div class="article">
                <a href="{url}">{title}</a>
                <br><small>{why}</small>
            </div>
            """

        html_content += "</div>"

    html_content += f"""
        <div class="footer">
            <p>You're receiving this because you subscribed to {frequency} digests for {topic.name}.</p>
            <p><a href="https://trybriefed.com/pages/main">Manage your subscriptions</a></p>
        </div>
    </body>
    </html>
    """

    message = Mail(
        from_email=('feed@trybriefed.com', 'Briefed Bites'),
        to_emails=user.email,
        subject=subject,
        html_content=html_content
    )

    try:
        response = sg.send(message)
        logging.info(f"Email sent to {user.email} with status {response.status_code}")
        return True
    except Exception as e:
        logging.error(f"Failed to send email to {user.email}: {str(e)}")
        return False


def process_bites_subscriptions():
    logging.info("==== Starting Bites subscription processing ====")

    now_utc = datetime.now(pytz.utc)
    logging.info(f"Current UTC time: {now_utc.strftime('%Y-%m-%d %H:%M')}")

    active_subs = BitesSubscription.objects.filter(is_active=True).select_related('user', 'topic')

    processed_count = 0
    sent_count = 0

    for subscription in active_subs:
        try:
            tz = pytz.timezone(subscription.timezone)
            local_now = now_utc.astimezone(tz)

            if (local_now.hour != subscription.delivery_time.hour or
                local_now.minute != subscription.delivery_time.minute):
                continue

            if subscription.frequency == 'weekly' and local_now.weekday() != 0:
                continue

            logging.info(f"Processing subscription for {subscription.user.email} - {subscription.topic.name}")
            processed_count += 1

            digest_content, article_count = get_or_generate_digest(
                subscription.topic,
                subscription.frequency
            )

            if not digest_content:
                logging.warning(f"No digest content for {subscription.topic.name}")
                continue

            success = send_bites_email(
                subscription.user,
                subscription.topic,
                digest_content,
                subscription.frequency
            )

            if success:
                subscription.last_sent_at = now_utc
                subscription.save()
                sent_count += 1
                logging.info(f"Successfully sent digest to {subscription.user.email}")

        except Exception as e:
            logging.error(f"Error processing subscription {subscription.id}: {str(e)}")
            continue

    logging.info(f"==== Finished: Processed {processed_count}, Sent {sent_count} ====")


def cleanup_old_digests(days_to_keep=30):
    cutoff_date = datetime.now().date() - timedelta(days=days_to_keep)
    deleted_count, _ = BitesDigest.objects.filter(digest_date__lt=cutoff_date).delete()
    logging.info(f"Cleaned up {deleted_count} old digests")


if __name__ == "__main__":
    process_bites_subscriptions()
