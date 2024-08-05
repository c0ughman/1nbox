from _1nbox_ai.models import User, Topic  # Adjust the import to your actual module path
from openai import OpenAI
import os
from twilio.rest import Client


def generate_answer(from_number, body):
    # Check if from_number contains ":" and extract the part after it if present
    if ":" in from_number:
        from_number = from_number.split(":", 1)[1]
    print("GENERATING ANSWER")
    print(from_number)
    print(body)
    
    # Find the user with the matching phone number
    user = User.objects.filter(phone_number=from_number).first()
    if not user:
        return "Error: User not found."

    summaries = []
    general_list = []
    # Iterate through the user's topics
    for topic in user.topics:
        try:
            chosen_topic = Topic.objects.get(name=topic)
            # Add the Topic summary to the general list
            summaries.append(repr(chosen_topic.summary))
            
            # Add each cluster summary to the general list
            general_list.append(repr(chosen_topic.cluster_summaries))
                    
        except Topic.DoesNotExist:
            # Skip to the next topic if the Topic instance does not exist
            continue
    
    client = OpenAI(api_key=os.environ.get('OPENAI_KEY'))

    # Make the OpenAI API request
    response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1000,
            temperature=0.125,
            messages=[
            {"role": "system", "content": "You are a news assistant. Use the provided information to answer the question concisely."},
            {"role": "user", "content": f"Information: {general_list}\nThis is what the user received: {summaries}\nQuestion: {body}\n\nProvide a short and concise answer."}
            ]
        )
    
    # Extract the generated answer
    answer = response.choices[0].message.content.strip()
    send_answer(user,answer)
   
    return answer

def send_answer(user,answer):
    # Twilio client setup
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    client = Client(account_sid, auth_token)

    try:
        if user.messaging_app == 'SMS':
            message = client.messages.create(
                to=user.phone_number,
                messaging_service_sid=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                body=answer,
            )
        elif user.messaging_app == 'Facebook Messenger':
            message = client.messages.create(
                to=f'messenger:{"FACEBOOK ID DOES NOT EXIST"}',
                messaging_service_sid=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                body=answer,
            )
        elif user.messaging_app == 'WhatsApp':
            message = client.messages.create(
                to=f"whatsapp:{user.phone_number}",
                from_=os.environ.get('TWILIO_MESSAGING_SERVICE_SID'),
                body=answer,
            )
        else:
            return False, "Invalid messaging app"
        
        return True, message.sid
    except Exception as e:
        return False, str(e)


