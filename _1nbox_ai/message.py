import os
from django.conf import settings
from twilio.rest import Client
import json
import datetime
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
    # Clean the summary and questions as before
    clean_summary = repr(summary).replace("\\r", "").replace("\\\\", "\\").replace("\\'", "'").replace("#", "")
    clean_summary = clean_summary[1:-1]  # Remove the first and last character
    clean_summary = clean_summary.replace("{", "").replace("}", "").replace('"', '').replace("*", "")
    
    clean_questions = repr(topic.questions).replace("\\r", "").replace("\\\\", "\\").replace("\\'", "'")
    clean_questions = clean_questions.replace("{", "").replace("}", "").replace('"', '').replace("*", "")
    
    # Split the summary if it exceeds 1200 characters
    if len(clean_summary) > 1200:
        split_index = clean_summary.rfind('\n\n', 0, 1200)
        if split_index == -1:
            split_index = clean_summary.rfind('\n', 0, 1200)
        if split_index == -1:
            split_index = 1200
        
        part1 = f"(1/2) {clean_summary[:split_index].strip()}"
        part2 = f"(2/2) {clean_summary[split_index:].strip()}"
        
        return [
            {
                "1": topic.name,
                "2": part1,
                "3": str(topic.number_of_articles),
                "4": clean_questions,
            },
            {
                "1": topic.name,
                "2": part2,
                "3": str(topic.number_of_articles),
                "4": clean_questions,
            }
        ]
    else:
        return [{
            "1": topic.name,
            "2": clean_summary,
            "3": str(topic.number_of_articles),
            "4": clean_questions,
        }]

def send_message(user, content_variables, content_sid):
    try:
        if user.messaging_app == 'SMS' or user.messaging_app == 'iMessage':
            message = client.messages.create(
                content_sid=content_sid,
                to=user.phone_number,
                messaging_service_sid=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                content_variables=json.dumps(content_variables)
            )
        elif user.messaging_app == 'Facebook Messenger':
            message = client.messages.create(
                content_sid=content_sid,
                to=f'messenger:{"FACEBOOK ID DOES NOT EXIST"}',
                messaging_service_sid=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                content_variables=json.dumps(content_variables)
            )
        elif user.messaging_app == 'WhatsApp':
            message = client.messages.create(
                content_sid=content_sid,
                to=f"whatsapp:{user.phone_number}",
                from_=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                content_variables=json.dumps(content_variables)
            )
        else:
            return False, "Invalid messaging app"
        
        return True, message.sid
    except Exception as e:
        return False, str(e)

def send_create_account_message(user):
    content_variables = {
        "1": user.phone_number.replace("+","%2B")
    }
    return send_message(user, content_variables, "HX3ace8e6497b0adaa4622c2669a0b67ce")

def send_feedback_check_message(user):
    return send_message(user, {}, "HXd3fa82c1be7b5acd001e5ed47a68fac0")

def send_trial_ending_message(user):

    if user.supabase_user_id:
        content_variables = {"1": f"?query_id={user.supabase_user_id}"}
    else:
        content_variables = {"1": f"?query_number={user.phone_number}"}

    
    return send_message(user, content_variables, "HX331d52f7b607a6ca4042cd9680c84080")

def send_trial_over_message(user):
    if user.supabase_user_id:
        content_variables = {"1": f"?query_id={user.supabase_user_id}&checkout=True"}
    else:
        content_variables = {"1": f"?query_number={user.phone_number}"}
    
    return send_message(user, content_variables, "HX17b76d4c2ab3c9f990572b9320e9ae50")

def send_miss_you_discount_message(user):
    if user.supabase_user_id:
        content_variables = {"1": f"?query_id={user.supabase_user_id}&checkout=True&discount_code=MISSME"}
    else:
        content_variables = {"1": f"?query_number={user.phone_number}"}
    
    return send_message(user, content_variables, "HX8b623bdc661dd54066ac97e51dded4c9")

def send_summaries():
    current_time = datetime.now().timestamp()
    
    for user in User.objects.exclude(plan="over"):
        days_since = (current_time - user.days_since) // (24 * 3600)
        
        # Set plan to "over" if 14 days have passed and plan is "no plan"
        if days_since >= 14 and user.plan == "no plan":
            user.plan = "over"
            user.save()
            continue
        
        # Send special messages based on days_since
        if user.plan == "no plan":
            if days_since == 3:
                send_create_account_message(user)
            elif days_since == 7:
                send_feedback_check_message(user)
            elif days_since == 10:
                send_trial_ending_message(user)
            elif days_since == 14:
                send_trial_over_message(user)
        
        # Send miss you discount message regardless of plan
        if days_since == 20:
            send_miss_you_discount_message(user)
        
        # Send regular summaries only if days_since is less than 14
        if days_since < 14:
            topics, summaries = get_user_topics_summary(user)
            for topic, summary in zip(topics, summaries):
                if user.messaging_app == "SMS":
                    content_variables_list = format_content_variables_sms(topic, summary)
                else:
                    content_variables_list = format_content_variables(topic, summary)
                
                for i, content_variables in enumerate(content_variables_list):
                    success, result = send_message(user, content_variables, os.environ.get('TWILIO_CONTENT_SID'))
                    if success:
                        part_info = f" (Part {i+1}/{len(content_variables_list)})" if len(content_variables_list) > 1 else ""
                        print(f"Message sent to {user.email} for topic {topic.name}{part_info} via {user.messaging_app}. SID: {result}")
                    else:
                        print(f"Failed to send message to {user.email} for topic {topic.name}. Error: {result}")
