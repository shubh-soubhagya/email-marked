import time
import json
import pandas as pd
from send_mail import (
    gmail_authenticate,
    build,
    convert_to_double_braces,
    create_message,
    send_message
)
from check_reply import get_recent_repliers, remove_responders_from_csv
from sugestion import generate_suggestions, choose_option


subject_input = input("📩 Enter your email subject line: ").strip()
message_input = input("📝 Enter your email body message: ").strip()

print("\n⏳ Generating suggestions from Groq...")
suggestions = generate_suggestions(subject_input, message_input)

subject_choice, chosen_subject = choose_option(suggestions["subject_suggestions"], "Subject")
message_choice, chosen_message = choose_option(suggestions["message_suggestions"], "Message")

output = {
    "selected_subject_number": subject_choice,
    "selected_subject": chosen_subject,
    "selected_message_number": message_choice,
    "selected_message": chosen_message
}

with open("final_selection.json", "w") as f:
    json.dump(output, f, indent=4)

print("\n✅ Saved selected subject and message to `final_selection.json`")


csv_path = 'influencer.csv'

# Authenticate once
creds = gmail_authenticate()
service = build('gmail', 'v1', credentials=creds)

# Load chosen subject/message from JSON
with open('final_selection.json') as f:
    selected = json.load(f)

# Ensure templates use double braces
subject_template = convert_to_double_braces(selected["selected_subject"])
message_template = convert_to_double_braces(selected["selected_message"])

# Send emails initially to all
df = pd.read_csv(csv_path)
for _, row in df.iterrows():
    influencer_name = row['influencer_name']
    email = row['email']
    
    personalized_subject = subject_template.replace("{{influencer_name}}", influencer_name)
    personalized_message = message_template.replace("{{influencer_name}}", influencer_name)
    
    email_msg = create_message(email, personalized_subject, personalized_message)
    send_message(service, 'me', email_msg)

print("✅ All initial emails sent.")

# 🔁 Start live reply tracking loop
print("\n🚀 Starting live tracking of replies... (Press Ctrl+C to stop)\n")

try:
    while True:
        repliers = get_recent_repliers(service)
        if repliers:
            print(f"📩 Found replies from: {repliers}")
            remove_responders_from_csv(csv_path, repliers)
        else:
            print("ℹ️ No replies yet.")

        # Sleep before checking again (e.g., 600 seconds = 10 minutes)
        time.sleep(60)

except KeyboardInterrupt:
    print("\n🛑 Live tracking stopped by user.")
