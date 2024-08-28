import logging
import json
from .models import Topic, User

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def get_user_topics_summary(user):
    logging.info(f"Processing topics for user {user.id}: {user.topics}")
    topic_list = []

    for topic_name in user.topics:
        logging.debug(f"Processing topic: {topic_name}")
        try:
            topic_obj = Topic.objects.get(name=topic_name)
            logging.debug(f"Found topic object: {topic_obj}")

            if topic_obj.summary:
                logging.debug(f"Raw summary for topic '{topic_name}': {topic_obj.summary}")
                try:
                    summary_data = json.loads(topic_obj.summary)
                    summary = summary_data.get('summary', [])
                    logging.debug(f"Parsed summary: {summary}")
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error for topic '{topic_name}': {e}")
                    summary = []
            else:
                logging.warning(f"No summary found for topic '{topic_name}'")
                summary = []

            if user.negative_keywords:
                negative_list = user.negative_keywords.split(",")
                logging.debug(f"Filtering with negative keywords: {negative_list}")
                summary = [
                    item for item in summary 
                    if not any(word.lower() in item['content'].lower() for word in negative_list)
                ]
                logging.debug(f"Filtered summary: {summary}")

            topic_obj.summary = summary
            topic_list.append(topic_obj)
        except Topic.DoesNotExist:
            logging.warning(f"Topic '{topic_name}' does not exist and will be skipped.")
        except Exception as e:
            logging.exception(f"Unexpected error processing topic '{topic_name}': {e}")

    return topic_list

def send_summaries():
    logging.info("Starting send_summaries function")
    current_time = datetime.now().timestamp()

    for user in User.objects.exclude(plan="over"):
        logging.info(f"Processing user: {user.id}")
        try:
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
                logging.info(f"Email sent to {user.email} with status code: {result}")
            else:
                logging.error(f"Failed to send email to {user.email}. Error: {result}")
        except Exception as e:
            logging.exception(f"Unexpected error processing user {user.id}: {e}")

if __name__ == "__main__":
    send_summaries()
