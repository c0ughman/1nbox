import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from supabase import create_client
import base64
from datetime import datetime
from datetime import timedelta
import re
from openai import OpenAI
from bs4 import BeautifulSoup
import os
import json
from supabase import create_client, Client

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Function to get messages from Gmail API
def get_gmail_messages(user):

    access_token = user.provider_token
    refresh_token = user.provider_refresh_token

    frequency = user.frequency

    CLIENT_ID = os.environ.get('CLIENT_ID')
    CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

    user_info = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "token": access_token,
    "refresh_token": refresh_token,
    "token_uri": "https://accounts.google.com/o/oauth2/token",
    "scopes": ['https://www.googleapis.com/auth/gmail.readonly']
    }

    creds = Credentials.from_authorized_user_info(user_info)

    if is_token_expired(creds):
        print("expired")
        refresh_access_token(creds)

    # Choosing the frequency to see how many days to get emails from
    days = '1d'
    if frequency == 'daily':
        days = '1d'
    elif frequency == 'weekly':
        days = '7d'
    else:
        print("frequency not daily or weekly")
    
    service = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    # Get messages using the Gmail API                          UNTESTED↓↓↓
    response = service.users().messages().list(userId='me', q=f'newer_than:{days} in:inbox is:unread -category:(promotions OR social)').execute()
    #print(response)
    messages = response.get('messages', [])

    # make negative keywords into a list to iterate
    negative = user.negative_keywords
    if negative != None:
        negative_list = negative.split(", ")
    else:
        negative_list = [""]

    # Loop through messages and get contents
    big_list = []

    for message in messages:
        # Replace 'me' with the actual user's email address
        message_data = service.users().messages().get(userId='me', id=message['id']).execute()
        
        decoded_text = decode_message(message_data)

        # Check if decoded_text contains any negative keyword
        skip_message = False

        if negative_list[0] != "":
            for neg in negative_list:
                if neg in decoded_text:
                    print("Negative keyword found in message. Skipping...")
                    skip_message = True
                    break

        if skip_message:
            continue  # Skip to the next message if a negative keyword is found

        # Clean the text and add it to big_list
        clean = clean_text(decoded_text)
        big_list.append(clean)

    # Convert big_list to a string
    number_of_emails = len(big_list)
    print(f"Number of emails summarized: {number_of_emails}")
    big_list = list(set(big_list))
    big_string = '\n'.join(big_list)

    return big_string, number_of_emails

# Function to check if the access token is expired or about to expire
def is_token_expired(creds):
    if not creds or not creds.valid:
        return True
    expiry = creds.expiry
    now = datetime.datetime.now(creds.expiry.tzinfo)
    return now >= expiry

# Function to refresh the access token
def refresh_access_token(creds):
    if creds.refresh_token:
        creds.refresh(Request())
    else:
        raise ValueError('No refresh token available.')

# Function to decode text
def decode_message(message):
    """Decode the base64 encoded message."""
    payload = message['payload']

    if 'body' in payload and 'data' in payload['body']:
        # The message has a simple body
        message_data = payload['body']['data']
    elif 'parts' in payload:
        # The message has multiple parts (possibly including attachments)
        message_data = ""
        for part in payload['parts']:
            if 'body' in part and 'data' in part['body']:
                message_data += part['body']['data']
    else:
        # No recognizable body or parts
        return ""

    return base64.urlsafe_b64decode(message_data).decode('utf-8', errors='ignore')

# Function to clean text
def clean_text(text):
    encoded_text = text.encode('utf-8')
    clean_text = encoded_text.decode('utf-8')

      # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(text, 'html.parser')

    # Remove script tags and their content
    for script in soup(['script', 'style']):
        script.extract()

    # Remove CSS properties from HTML attributes
    for element in soup.find_all(attrs=lambda x: x and re.search(r'style\s*=\s*[\'"][^\'"]*?[^\\\\][\'}"]', str(x))):
        element.attrs['style'] = re.sub(r'([;\s]|^)(?:[^:;{}\\]|\\.)+?:[^;{}]*?;?', '', element.attrs.get('style', ''))

    # Remove inline CSS styles
    for element in soup.find_all(style=True):
        del element['style']

    # Remove remaining HTML tags and get text
    clean_text = soup.get_text(separator=' ')

    # Remove newline characters
    clean_text = clean_text.replace('\n', '')

    # Remove carriage return characters
    clean_text = clean_text.replace('\r', '')

    # Remove URLs
    clean_text = re.sub(r'https?://[^\s]+', '', clean_text)

    # Remove &nbsp;
    clean_text = clean_text.replace('&nbsp;', '')

    # Remove multiple spaces
    clean_text = re.sub(r'\s+', ' ', clean_text)

    # Remove content inside parentheses and the parentheses as well
    clean_text = re.sub(r'\([^)]*\)', '', clean_text)

    # Remove asterisks
    clean_text = clean_text.replace('*', '')

    # Remove consecutive dashes over three
    clean_text = re.sub(r'-{3,}', '', clean_text)

    # Remove repeated words over three times in a row
    clean_text = re.sub(r'\b(\w+)\s+\1\s+\1\b', '', clean_text)

    clean_text = clean_text[:1500]

    return clean_text.strip()

# Reduce repetition
def reduce_repetitive_patterns(text):
    # Define regex patterns to identify repetitive sequences
    patterns = [
        (r'(\b\w+\b)(\s+\1)+', r'\1'),  # Remove repeated words
        (r'([.,?!])\1+', r'\1'),  # Remove repeated punctuation
        (r'(["\'])(?:(?=(\\?))\2.)*?\1', r'\1'),  # Remove repeated quotes
        (r'(\b\w+\b\s*){3,}', r'\1'),  # Remove repeated sequences of three or more words
        # Add more patterns as needed to identify other repetitive structures
    ]

    # Apply regex substitutions
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)

    return text

def remove_whitespace(string):
    return string.replace("     ", "")

def remove_repeated_text(input_str):
    n = len(input_str)
    if n <= 200:
        return input_str

    # Dictionary to store the first occurrence of each 201-character substring hash
    seen_hashes = {}
    substring_length = 201

    i = 0
    while i <= n - substring_length:
        current_substring = input_str[i:i + substring_length]
        current_hash = hash(current_substring)

        if current_hash in seen_hashes:
            start_index = seen_hashes[current_hash]
            if input_str[start_index:start_index + substring_length] == current_substring:
                # Find the end of the repeated segment
                j = i + substring_length
                while j < n and input_str[j] == input_str[start_index + (j - i)]:
                    j += 1

                # Remove the repeated segment
                input_str = input_str[:i] + input_str[j:]
                n = len(input_str)  # Update the length of the input_str
                continue  # Check the new substring at the same position

        else:
            seen_hashes[current_hash] = i

        i += 1

    return input_str

# Function to create prompt string
def create_prompt(user):

    style = user.style
    positive = user.positive_keywords
    negative = user.negative_keywords

    style_text = (
        "You are an Inbox Summarizer. I will give you some messages from my email inbox, and I want you to tell me "
        "what messages I have received in a small paragraph. "
        "want the email summaries to loosely follow the following format: "
        "*start of sentence mentioning the sender name* [the main idea or important piece of information of the email]. "
        "Feel free to group together summaries in case they are similar in content or topic, or if they are not that important comparatively."
    )
    
    if style == "list":
        style_text = (
            "You are an Inbox Summarizer. I will give you some messages from my email inbox, and I want you to tell me "
            "what messages I have received in a one-sentence summary for each email. Don't miss any of the emails."
            "I want each email summary to follow the following format: "
            "*sender name:* [the main idea or important piece of information of the email] "
            "I also want there to be a line break after each summary"
        )
        # THIS NEEDS TO BE FIXED SOMETIME
    elif style == "importance":
        style_text = (
            "You are an Inbox Summarizer and Chief Prioritizer Assistant." 
            "I will give you messages from my email inbox, and I want the three most important or urgent emails i have received summarized "
            "in a short sentence each containing the name of the sender and the main idea or important information from the message." 
            "Then, i want a general summary or main idea of the rest of the emails in the  inbox, "
            "giving me a snapshot of the other emails i received  in a small and direct paragraph."
        )
    
    return f'{style_text} It is obligatory to delete anything containing or pertaining to these words: {negative}. It is obligatory to include anything containing or pertaining to these words: {positive}'

# Function to send request to OpenAI API
def get_openai_response(user, messages):
    # Assuming create_prompt is defined elsewhere in your code
    prompt = create_prompt(user)

    # Replace 'your_openai_api_key' with your actual OpenAI API key
    openai_key = os.environ.get('OPENAI_KEY')
    
    client = OpenAI(api_key=openai_key)

    completion = client.chat.completions.create(
    model="gpt-3.5-turbo-0125",
    max_tokens=300,
    temperature=0.125,
    messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": messages}
    ]
    )

    summary = completion.choices[0].message

    return summary

# Adds the summary to the database
def add_summary_to_supabase(user, summary):

    user_id = user.supabase_user_id
    access_token = user.access_token
    refresh_token = user.refresh_token

    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    supabase: Client = create_client(supabase_url, supabase_key)

    try:
        # Attempt to set the session with the current tokens
        supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
    except Exception as e:
        print(f"Error setting session: {e}")
        # Attempt to refresh the tokens if the session setting fails
        try:
            response = requests.post(
                f"{supabase_url}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": supabase_key, "Content-Type": "application/json"},
                json={"refresh_token": refresh_token}
            )
            response_data = response.json()
            if response.status_code == 200:
                # Update the user's tokens
                access_token = response_data['access_token']
                refresh_token = response_data['refresh_token']
                user.access_token = access_token
                user.refresh_token = refresh_token
                user.save()  # Save the updated tokens to the database
                # Set the session with the new tokens
                supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            else:
                print(f"Error refreshing token: {response_data}")
                return
        except Exception as refresh_error:
            print(f"Error refreshing token: {refresh_error}")
            return

    # Insert the summary into the Supabase table
    try:
        data, count = supabase.table('Summaries').insert({"user_id": user_id, "summary": summary}).execute()
        print(data)
        print(count)
    except Exception as insert_error:
        print(f"Error inserting summary: {insert_error}")

# Send message to WhatsApp
def send_request(access_key, phone_number, project_id, version, locale, timeframe, summary, number_of_emails):
    url = os.environ.get('WHATSAPP_URL')

    headers = {
        'Authorization': f'AccessKey {access_key}',
        'Content-Type': 'application/json'
    }

    data = {
        "receiver": {
            "contacts": [
                {
                    "identifierValue": phone_number,
                    "identifierKey": "phonenumber"
                }
            ]
        },
        "template": {
            "projectId": project_id,
            "version": version,
            "locale": locale,
            "variables": {
                "timeframe": timeframe,
                "summary": summary,
                "numberofemails": number_of_emails
            }
        }
    }

    response = requests.post(url, headers=headers, data=json.dumps(data))

    return response.status_code, response.json()

def send_message_whatsapp(user, message, number_of_emails):
    
    # general API variables
    access_key = os.environ.get('WHATSAPP_KEY')

    # phone number related variables
    # CHANGE to user.number or something similar when ready
    phone_number = user.phone_number

    # project variables
    project_id = "c6222858-eca9-4c68-9977-1ce3a2c630b4"
    version = "3dff5675-c9a0-490b-bcc0-5955ffbc1aba"
    locale = "en"

    # message related variables
    
    timeframe = "today"
    if user.frequency == "weekly":
        timeframe = "the week"
    elif user.frequency == "daily":
        timeframe = "today"
    else: 
        print("OJO!!! - frequency not daily or weekly")
    
    summary = message

    number = str(number_of_emails)
    
    response = send_request(
    access_key, 
    phone_number, 
    project_id, 
    version, 
    locale, 
    timeframe, 
    summary, 
    number
    )

    print("OJO!!!!! ") 
    print(response)

# Main function to execute the workflow
def main(user):
    
    # Get messages from Gmail API
    messages, number_of_emails = get_gmail_messages(user)

    messages = remove_whitespace(messages)
    messages = remove_repeated_text(messages)

    print(messages)

    # Send request to OpenAI API
    summary = get_openai_response(user, messages)

    summary = str(summary.content)
    summary = repr(summary)
    summary = summary[1:-1]
    
    # Add the summary to Supabase
    add_summary_to_supabase(user, summary)

    # Send via Whatsapp
    send_message_whatsapp(user, summary, number_of_emails)


    print(f"({user.t} - {user.frequency})")
    print(user.email + f" -- ({user.supabase_user_id})")
    print("Summary: ")  
    print(summary)
    print("Style: " + user.style)
    print("/n Positive Keywords " + user.positive_keywords)
    print("/n Negative Keywords " + user.negative_keywords)
    
    return (summary)
    

