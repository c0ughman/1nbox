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

def get_topic_summary(user, topic):
    try:
        topic_obj = Topic.objects.get(name=topic)
        summary = topic_obj.summary
        negative = user.negative_keywords
        if negative:
            negative_list = negative.split(",")
            summary_paragraphs = summary.split('\n\n')
            filtered_paragraphs = [
                p for p in summary_paragraphs if not any(word.lower() in p.lower() for word in negative_list)
            ]
            summary = '\n\n'.join(filtered_paragraphs)     
        questions = topic_obj.questions.split('\n')
        return summary, topic_obj.number_of_articles, questions
    except Topic.DoesNotExist:
        print(f"Topic '{topic}' does not exist and will be skipped.")
        return None, 0, []

def format_content_variables(topic, summary, articles, questions):
    random_questions = "\n".join(random.sample(questions, min(3, len(questions)))) if questions else "Expand on the story please.\nHow would this affect the global economy?\nWhat does this mean for the future?"
    return {
        "1": topic,
        "2": repr(summary),
        "3": str(articles),
        "4": random_questions,
    }

def format_content_variables_sms(topic, summary, articles, questions):
    random_questions = "\n".join(random.sample(questions, min(3, len(questions)))) if questions else "Expand on the story please.\nHow would this affect the global economy?\nWhat does this mean for the future?"
    return {
        "1": topic,
        "2": summary,
        "3": str(articles),
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
        for topic in user.topics:
            summary, articles, questions = get_topic_summary(user, topic)
            if summary is None:
                continue  # Skip this topic if it doesn't exist
            
            content_variables = format_content_variables(topic, summary, articles, questions)
            sms_content_variables = format_content_variables_sms(topic, summary, articles, questions)
            
            if user.messaging_app == "SMS":
                success, result = send_message(user, sms_content_variables)
            else:
                success, result = send_message(user, content_variables)
            
            if success:
                print(f"Message sent to {user.email} for topic '{topic}' via {user.messaging_app}. SID: {result}")
            else:
                print(f"Failed to send message to {user.email} for topic '{topic}'. Error: {result}")
