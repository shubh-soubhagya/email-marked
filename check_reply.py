import pandas as pd
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]


def gmail_authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(r'credentials/credentials_email.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token_file:
            token_file.write(creds.to_json())
    return creds

def get_recent_repliers(service):
    response = service.users().messages().list(userId='me', q="in:inbox newer_than:2d").execute()
    messages = response.get('messages', [])
    repliers = set()

    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['From']).execute()
        headers = msg_data['payload']['headers']
        for h in headers:
            if h['name'] == 'From':
                email = h['value']
                if '<' in email:
                    email = email.split('<')[1].strip('>')
                repliers.add(email.lower())
    return repliers

# def remove_responders_from_csv(csv_path, repliers):
#     df = pd.read_csv(csv_path)
#     initial_count = len(df)
#     df['email'] = df['email'].str.lower()
#     df = df[~df['email'].isin(repliers)]
#     df.to_csv(csv_path, index=False)
#     print(f"✅ Removed {initial_count - len(df)} replied influencers. CSV updated.")

import pandas as pd

def remove_responders_from_csv(csv_path, repliers, responded_path='responded.csv'):
    df = pd.read_csv(csv_path)

    # Filter the rows that match the repliers
    mask = df['email'].isin(repliers)
    responded_df = df[mask]
    remaining_df = df[~mask]

    # Save the replied ones to responded.csv (append if file exists)
    try:
        existing_responded = pd.read_csv(responded_path)
        responded_df = pd.concat([existing_responded, responded_df], ignore_index=True).drop_duplicates(subset=['email'])
    except FileNotFoundError:
        pass  # File doesn't exist yet, will be created fresh

    responded_df.to_csv(responded_path, index=False)
    remaining_df.to_csv(csv_path, index=False)

    print(f"✅ Moved {len(responded_df)} replied influencers to '{responded_path}' and updated '{csv_path}'.")


def main():
    creds = gmail_authenticate()
    service = build('gmail', 'v1', credentials=creds)

    csv_path = 'influencer.csv'
    repliers = get_recent_repliers(service)
    if repliers:
        print(f"📩 Found replies from: {repliers}")
        remove_responders_from_csv(csv_path, repliers)
    else:
        print("ℹ️ No replies detected in the last 2 days.")

if __name__ == '__main__':
    main()
