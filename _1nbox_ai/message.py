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
    topics = ', '.join(user.topics)
    summaries = '\n'.join([Topic.objects.get(name=topic).summary for topic in user.topics])
    return topics, summaries

def format_content_variables(topics, summaries):
    return {
        "1": topics,
        "2": summaries,
        "3": "over 100",
        "4": "Expand on the first news story.\nWhat are the sources of these summaries?\nCan you provide more details on the most recent development?"
    }

def send_message(user, content_variables):
    try:
        if user.messaging_app == 'SMS':
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
                from_=f"whatsapp:{os.environ.get('TWILIO_WHATSAPP_NUMBER')}",
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
        content_variables = format_content_variables(topics, summaries)

        success, result = send_message(user, content_variables)

        if success:
            print(f"Message sent to {user.username} via {user.messaging_app}. SID: {result}")
        else:
            print(f"Failed to send message to {user.username}. Error: {result}")
