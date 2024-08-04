import os
from twilio.rest import Client
import json
from .models import Topic, User

# Fetch environment variables
def get_twilio_client():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    return Client(account_sid, auth_token)

client = get_twilio_client()

def send_summaries():
    users = User.objects.all()
    for user in users:
        topics = user.topics
        summaries = []
        topic_names = []

        for topic in topics:
            topic_obj = Topic.objects.filter(name=topic).first()
            if topic_obj:
                summaries.append(topic_obj.summary)
                topic_names.append(topic_obj.name)

        if summaries:
            send_message(user, topic_names, summaries)

def send_message(user, topics, summaries):
    topics_text = ", ".join(topics)
    summaries_text = "\n\n".join(summaries)
    example_questions = [
        "Expand on the first news story.",
        "What are the sources of these summaries?",
        "How does this news impact the global economy?"
    ]

    template_data = {
        '1': topics_text,
        '2': summaries_text,
        '3': 'over 100',
        '4': "\n".join(example_questions)
    }

    if user.messaging_app == 'SMS':
        send_sms(user.phone_number, template_data)
    elif user.messaging_app == 'Facebook Messenger':
        send_facebook_message(user.facebook_id, template_data)
    elif user.messaging_app == 'WhatsApp':
        send_whatsapp_message(user.phone_number, template_data)

def send_sms(phone_number, template_data):
    content_sid = os.getenv('TWILIO_CONTENT_SID')
    phone_number_from = os.getenv('TWILIO_PHONE_NUMBER')
    
    client.messages.create(
        content_sid=content_sid,
        from_=phone_number_from,
        to=phone_number,
        content_variables=json.dumps(template_data)  # Convert to JSON string
    )

def send_facebook_message(facebook_id, template_data):
    content_sid = os.getenv('TWILIO_CONTENT_SID')
    messaging_service_sid = os.getenv('TWILIO_MESSAGING_SERVICE_SID')

    client.messages.create(
        content_sid=content_sid,
        messaging_service_sid=messaging_service_sid,
        to=f'messenger:{facebook_id}',
        content_variables=json.dumps(template_data)  # Convert to JSON string
    )

def send_whatsapp_message(phone_number, template_data):
    content_sid = os.getenv('TWILIO_CONTENT_SID')
    whatsapp_number_from = os.getenv('TWILIO_WHATSAPP_NUMBER')

    client.messages.create(
        content_sid=content_sid,
        from_=f'whatsapp:{whatsapp_number_from}',
        to=f'whatsapp:{phone_number}',
        content_variables=json.dumps(template_data)  # Convert to JSON string
    )

# This function can be called at a specific time to trigger the sending of summaries
def scheduled_summary_sender():
    send_summaries()

