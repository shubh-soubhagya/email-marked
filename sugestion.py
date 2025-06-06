import json
import re
from groq import Groq  # pip install groq
import os
from dotenv import load_dotenv

# Initialize Groq Client
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def extract_json_from_response(response_text):
    """Extracts the first JSON object from a mixed Groq response."""
    match = re.search(r"{.*}", response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            print("❌ JSON decode error:", e)
            print("⚠️ Raw matched content:\n", match.group(0))
            exit(1)
    else:
        print("❌ Could not extract JSON from Groq response.")
        print("⚠️ Raw response:\n", response_text)
        exit(1)

def generate_suggestions(subject, message):
    prompt = f"""
You are an expert marketing agent. Based on the following inputs, suggest:
- 5 improved subject lines
- 5 improved email messages that feel personalized but professional

Original Subject Line:
{subject}

Original Email Message:
{message}

The email message should include a placeholder {{influencer_name}} where the name will be injected later.
Respond in JSON format as:
{{
  "subject_suggestions": ["...", "...", "...", "...", "..."],
  "message_suggestions": ["...", "...", "...", "...", "..."]
}}
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8
    )

    content = response.choices[0].message.content.strip()
    return extract_json_from_response(content)

def choose_option(options, label):
    """Utility function to display options and get a valid selection from user."""
    print(f"\n🔹 {label} Suggestions:")
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}\n")

    while True:
        try:
            choice = int(input(f"Choose a {label.lower()} number (1-{len(options)}): "))
            if 1 <= choice <= len(options):
                return choice, options[choice - 1]
            else:
                print(f"❗ Please enter a number between 1 and {len(options)}.")
        except ValueError:
            print("❗ Invalid input. Please enter a number.")

def main():
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

if __name__ == "__main__":
    main()
