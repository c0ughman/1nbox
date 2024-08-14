import os
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
            topic_list.append(topic_obj)
        except Topic.DoesNotExist:
            print(f"Topic '{topic}' does not exist and will be skipped.")
    
    return topic_list, summaries

def format_content_variables_sms(topic, summary):
    return {
        "1": topic.name,
        "2": summary,
        "3": str(topic.number_of_articles),
        "4": topic.questions,
    }

def format_content_variables(topic, summary):
    # Replace \r with nothing, reduce double backslashes to single backslash, and fix escaped apostrophes
    clean_summary = repr(summary).replace("\\r", "").replace("\\\\", "\\").replace("\\'", "'")
    clean_summary = clean_summary[1:-1]  # Remove the first and last character
    clean_summary = clean_summary.replace("{", "").replace("}", "").replace('"', '').replace("*", "")
    
    clean_questions = repr(topic.questions).replace("\\r", "").replace("\\\\", "\\").replace("\\'", "'")
    clean_questions = clean_questions.replace("{", "").replace("}", "").replace('"', '').replace("*", "")
    
    return {
        "1": topic.name,
        "2": clean_summary,
        "3": str(topic.number_of_articles),
        "4": clean_questions,
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
        topics, summaries = get_user_topics_summary(user)
        for topic, summary in zip(topics, summaries):
            if user.messaging_app == "SMS":
                content_variables = format_content_variables_sms(topic, summary)
            else:
                content_variables = format_content_variables(topic, summary)
                print(content_variables)
            
            success, result = send_message(user, content_variables)
            if success:
                print(f"Message sent to {user.email} for topic {topic.name} via {user.messaging_app}. SID: {result}")
            else:
                print(f"Failed to send message to {user.email} for topic {topic.name}. Error: {result}")
