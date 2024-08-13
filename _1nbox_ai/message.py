import os
import random
from django.conf import settings
from twilio.rest import Client
import json
from .models import Topic, User

# Twilio client setup
account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

def get_user_topics_summary(user):
    summaries = []
    topic_list = []
    total_articles = 0
    all_questions = []

    for topic in user.topics:
        try:
            topic_obj = Topic.objects.get(name=topic)
            # make negative keywords into a list to iterate
            summary = topic_obj.summary
            negative = user.negative_keywords
            if negative:
                negative_list = negative.split(",")
                summary_paragraphs = topic_obj.summary.split('\n\n')
                filtered_paragraphs = [
                    p for p in summary_paragraphs if not any(word.lower() in p.lower() for word in negative_list)
                ]
                summary = '\n\n'.join(filtered_paragraphs)     
            summaries.append(summary)
            topic_list.append(topic)
            total_articles += topic_obj.number_of_articles
            all_questions.extend(topic_obj.questions.split('\n'))
        except Topic.DoesNotExist:
            print(f"Topic '{topic}' does not exist and will be skipped.")
    
    summaries_str = '\n'.join(summaries)
    topics = ', '.join(topic_list)
    
    return topics, summaries_str, total_articles, all_questions, len(user.topics)

def format_content_variables_sms(topics, summaries, total_articles, all_questions, topic_count):
    random_questions = "\n".join(random.sample(all_questions, min(3, len(all_questions)))) if topic_count > 1 else "Expand on the first story please.\nHow would this affect the global economy?\nWhat does this mean for the future?"
    return {
        "1": topics,
        "2": summaries,
        "3": str(total_articles),
        "4": random_questions,
    }

def format_content_variables(topics, summaries, total_articles, all_questions, topic_count):
    random_questions = "\n".join(random.sample(all_questions, min(3, len(all_questions)))) if topic_count > 1 else "Expand on the first story please.\nHow would this affect the global economy?\nWhat does this mean for the future?"
    return {
        "1": topics,
        "2": repr(summaries),
        "3": str(total_articles),
        "4": random_questions,
    }

def send_message(user, content_variables):
    try:
        if user.messaging_app == 'SMS' or user.messaging_app == 'iMessage':
            message = client.messages.create(
                content_sid=os.environ.get('TWILIO_CONTENT_SID'),
                to=user.phone_number,
                messaging_service_sid=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                content_variables=json.dumps(content_variables)
            )
        elif user.messaging_app == 'Facebook Messenger':
            message = client.messages.create(
                content_sid=os.environ.get('TWILIO_CONTENT_SID'),
                to=f'messenger:{"FACEBOOK ID DOES NOT EXIST"}',
                messaging_service_sid=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                content_variables=json.dumps(content_variables)
            )
        elif user.messaging_app == 'WhatsApp':
            message = client.messages.create(
                content_sid=os.environ.get('TWILIO_CONTENT_SID'),
                to=f"whatsapp:{user.phone_number}",
                from_=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                content_variables=json.dumps(content_variables)
            )
        else:
            return False, "Invalid messaging app"
        
        return True, message.sid
    except Exception as e:
        return False, str(e)

def send_summaries():
    for user in User.objects.all():
        topics, summaries, total_articles, all_questions, topic_count = get_user_topics_summary(user)
        content_variables = format_content_variables(topics, summaries, total_articles, all_questions, topic_count)
        sms_content_variables = format_content_variables_sms(topics, summaries, total_articles, all_questions, topic_count)
        if user.messaging_app == "SMS":
            success, result = send_message(user, sms_content_variables)
        else:
            success, result = send_message(user, content_variables)
        if success:
            print(f"Message sent to {user.email} via {user.messaging_app}. SID: {result}")
        else:
            print(f"Failed to send message to {user.email}. Error: {result}")
