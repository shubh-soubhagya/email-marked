import pandas as pd
import json
import os
import base64
import re
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying scopes, delete token.json
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]


def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(r'credentials\credentials_email.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    return creds

def create_message(to, subject, message_text):
    message = MIMEText(message_text, 'plain', 'utf-8')
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_message(service, user_id, message):
    try:
        sent_message = service.users().messages().send(userId=user_id, body=message).execute()
        print(f"✅ Email sent to {message['raw'][:30]}... Message Id: {sent_message['id']}")
        return sent_message
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def convert_to_double_braces(text):
    # Replace {placeholder} with {{placeholder}}, but skip if already doubled
    return re.sub(r'(?<!{){(\w+)}(?!})', r'{{\1}}', text)

def main():
    # Authenticate Gmail API
    creds = gmail_authenticate()
    service = build('gmail', 'v1', credentials=creds)

    # Load influencers CSV
    df = pd.read_csv('influencer.csv')

    # Load chosen subject/message from JSON
    with open('final_selection.json') as f:
        selected = json.load(f)

    # Ensure templates use double braces
    subject_template = convert_to_double_braces(selected["selected_subject"])
    message_template = convert_to_double_braces(selected["selected_message"])

    for _, row in df.iterrows():
        influencer_name = row['influencer_name']
        email = row['email']

        # Replace placeholders
        personalized_subject = subject_template.replace("{{influencer_name}}", influencer_name)
        personalized_message = message_template.replace("{{influencer_name}}", influencer_name)

        # Create and send the message
        email_msg = create_message(email, personalized_subject, personalized_message)
        send_message(service, 'me', email_msg)

if __name__ == '__main__':
    main()
