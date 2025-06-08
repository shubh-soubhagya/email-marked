import gradio as gr
import time
import json
import pandas as pd
import threading
from datetime import datetime
from send_mail import (
    gmail_authenticate,
    build,
    convert_to_double_braces,
    create_message,
    send_message
)
# Updated import - we'll use the fixed version
from check_reply import get_recent_repliers, remove_responders_from_csv
from sugestion import generate_suggestions, choose_option

# Global variables for tracking
tracking_active = False
tracking_thread = None
service = None
creds = None

def authenticate_gmail():
    """Authenticate Gmail and return status"""
    global creds, service
    try:
        creds = gmail_authenticate()
        service = build('gmail', 'v1', credentials=creds)
        return "✅ Gmail authenticated successfully!", True
    except Exception as e:
        return f"❌ Authentication failed: {str(e)}", False

def generate_email_suggestions(subject, message):
    """Generate suggestions using Groq"""
    if not subject.strip() or not message.strip():
        return "Please enter both subject and message", [], [], "", ""
    
    # Auto-convert single braces to double braces for placeholders
    if "{influencer_name}" in subject:
        subject = subject.replace("{influencer_name}", "{{influencer_name}}")
    if "{influencer_name}" in message:
        message = message.replace("{influencer_name}", "{{influencer_name}}")
    
    try:
        print(f"Generating suggestions for:\nSubject: {subject}\nMessage: {message}")
        suggestions = generate_suggestions(subject, message)
        
        # Return the suggestions as lists for checkboxes
        return (
            "✅ Suggestions generated successfully!",
            suggestions["subject_suggestions"],  # List for subject checkboxes
            suggestions["message_suggestions"],  # List for message checkboxes
            suggestions["subject_suggestions"][0],  # Default to first suggestion
            suggestions["message_suggestions"][0]   # Default to first suggestion
        )
    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return "❌ Connection error: Please check your internet connection and Groq API key", [], [], "", ""
        return f"❌ Error generating suggestions: {error_msg}", [], [], "", ""

def update_selected_subject(subject_choice):
    """Return the selected subject"""
    return subject_choice if subject_choice else ""

def update_selected_message(message_choice):
    """Return the selected message"""
    return message_choice if message_choice else ""

def save_selection(subject, message):
    """Save the selected subject and message"""
    try:
        if not subject or not message:
            return "❌ Please select both subject and message options"
            
        output = {
            "selected_subject": subject,
            "selected_message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        with open("final_selection.json", "w") as f:
            json.dump(output, f, indent=4)
        
        return "✅ Selection saved to final_selection.json"
    except Exception as e:
        return f"❌ Error saving selection: {str(e)}"

def send_initial_emails(csv_path):
    """Send emails to all contacts in CSV"""
    global service
    
    if service is None:
        return "❌ Please authenticate Gmail first"
    
    try:
        # Load CSV
        if not csv_path:
            csv_path = 'influencer.csv'
        
        df = pd.read_csv(csv_path)
        
        # Load selected templates
        with open('final_selection.json') as f:
            selected = json.load(f)
        
        subject_template = convert_to_double_braces(selected["selected_subject"])
        message_template = convert_to_double_braces(selected["selected_message"])
        
        sent_count = 0
        errors = []
        
        for _, row in df.iterrows():
            try:
                influencer_name = row['influencer_name']
                email = row['email']
                
                personalized_subject = subject_template.replace("{{influencer_name}}", influencer_name)
                personalized_message = message_template.replace("{{influencer_name}}", influencer_name)
                
                email_msg = create_message(email, personalized_subject, personalized_message)
                send_message(service, 'me', email_msg)
                sent_count += 1
                
                # Small delay to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                errors.append(f"Failed to send to {email}: {str(e)}")
        
        result = f"✅ Sent {sent_count} emails successfully"
        if errors:
            result += f"\n❌ {len(errors)} errors occurred:\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                result += f"\n... and {len(errors) - 5} more errors"
        
        return result
        
    except Exception as e:
        return f"❌ Error sending emails: {str(e)}"

def save_responder_to_csv(responder_email, responder_name=None):
    """Save responder to responded.csv file"""
    try:
        import os
        
        # Check if responded.csv exists
        if not os.path.exists('responded.csv'):
            # Create new file with headers
            with open('responded.csv', 'w', newline='') as f:
                f.write('influencer_name,email\n')
        
        # Read existing data to avoid duplicates
        try:
            existing_df = pd.read_csv('responded.csv')
            if responder_email in existing_df['email'].values:
                return False  # Already exists
        except:
            pass
        
        # Append new responder
        with open('responded.csv', 'a', newline='') as f:
            name = responder_name if responder_name else "Unknown"
            f.write(f'{name},{responder_email}\n')
        
        return True
    except Exception as e:
        print(f"Error saving responder: {e}")
        return False

def start_reply_tracking(csv_path):
    """Start the reply tracking in a separate thread - FIXED VERSION"""
    global tracking_active, tracking_thread, service

    if tracking_active:
        return "⚠️ Tracking already active"

    if service is None:
        return "❌ Please authenticate Gmail first"

    tracking_active = True

    def tracking_loop():
        global tracking_active
        csv_file_path = csv_path if csv_path else 'influencer.csv'

        print(f"🚀 Starting reply tracking for {csv_file_path}")

        # Load original contact list for validation
        try:
            original_df = pd.read_csv(csv_file_path)
            # original_contacts = set(original_df['email'].str.lower())
            original_contacts = set(email.lower().strip() for email in original_df["email"])
            print(f"📋 Loaded {len(original_contacts)} original contacts for validation")
        except Exception as e:
            print(f"❌ Error loading original contacts: {e}")
            return

        while tracking_active:
            try:
                print(f"🔍 Checking for replies at {datetime.now().strftime('%H:%M:%S')}...")

                repliers = get_recent_repliers(service)
                

                if repliers:
                    # ✅ Only keep those that are in the original contacts
                    # valid_repliers = set(email for email in repliers if email in original_contacts)
                    valid_repliers = set(email.lower().strip() for email in repliers if email.lower().strip() in original_contacts)


                    # if valid_repliers:
                    #     print(f"📩 Valid replies from original contacts: {valid_repliers}")
                    #     remove_responders_from_csv(csv_file_path, valid_repliers)
                    #     original_contacts -= valid_repliers
                    if valid_repliers:
                        print(f"📩 Valid replies from original contacts: {valid_repliers}")
    
                        for email in valid_repliers:
                            try:
                                influencer_name = original_df.loc[original_df['email'].str.lower() == email, 'influencer_name'].values[0]
                            except:
                                influencer_name = "Unknown"
        
                        save_responder_to_csv(email, influencer_name)

                        remove_responders_from_csv(csv_file_path, valid_repliers)
                        original_contacts -= valid_repliers

            
                        print(f"📋 {len(original_contacts)} contacts remaining")
                    else:
                        print("ℹ️ No valid replies from contacts in original CSV.")
                else:
                    print("ℹ️ No new replies found")

                # Update live status
                try:
                    current_df = pd.read_csv(csv_file_path)
                    remaining_count = len(current_df)

                    import os
                    if os.path.exists('responded.csv'):
                        responded_df = pd.read_csv('responded.csv')
                        responded_count = len(responded_df)
                    else:
                        responded_count = 0

                    print(f"📊 Status: {remaining_count} contacts remaining, {responded_count} total responses")
                except Exception as e:
                    print(f"⚠️ Error getting statistics: {e}")

                time.sleep(60)  # Wait 1 min before next check

            except Exception as e:
                print(f"❌ Tracking error: {e}")
                time.sleep(30)
                continue

    tracking_thread = threading.Thread(target=tracking_loop, daemon=True)
    tracking_thread.start()

    return "🚀 Reply tracking started! Now checking for REAL replies from your original contacts every minute..."


def stop_reply_tracking():
    """Stop the reply tracking"""
    global tracking_active
    tracking_active = False
    return "🛑 Reply tracking stopped"

def get_tracking_status():
    """Get current tracking status"""
    return "🟢 Active" if tracking_active else "🔴 Inactive"

def get_responded_contacts():
    """Get list of contacts who have responded"""
    try:
        import os
        if os.path.exists('responded.csv'):
            df = pd.read_csv('responded.csv')
            if len(df) > 0:
                response_list = []
                for _, row in df.iterrows():
                    response_list.append(f"• {row['influencer_name']} - {row['email']}")
                return f"📧 Total Responses: {len(df)}\n\n" + "\n".join(response_list)
            else:
                return "📧 No responses yet"
        else:
            return "📧 No responses yet - responded.csv not found"
    except Exception as e:
        return f"❌ Error reading responses: {str(e)}"

def refresh_response_data():
    """Refresh the response data display"""
    return get_responded_contacts()

def clear_response_log():
    """Clear the response log file"""
    try:
        import os
        if os.path.exists('responded.csv'):
            # Keep header, remove data
            with open('responded.csv', 'w') as f:
                f.write('influencer_name,email\n')
            return "🗑️ Response log cleared successfully"
        else:
            return "📧 No response log to clear"
    except Exception as e:
        return f"❌ Error clearing log: {str(e)}"

def load_csv_info(csv_path):
    """Load and display CSV information"""
    try:
        if not csv_path:
            csv_path = 'influencer.csv'
        
        df = pd.read_csv(csv_path)
        
        # Show sample data
        sample_data = ""
        if len(df) > 0:
            sample_data = f"\n\nSample data:\n"
            for i, row in df.head(3).iterrows():
                if 'influencer_name' in df.columns and 'email' in df.columns:
                    sample_data += f"• {row['influencer_name']} - {row['email']}\n"
                else:
                    sample_data += f"• Row {i+1}: {dict(row)}\n"
        
        return f"📊 CSV loaded: {len(df)} contacts found\nColumns: {', '.join(df.columns.tolist())}{sample_data}"
    except Exception as e:
        return f"❌ Error loading CSV: {str(e)}"

# Create the Gradio interface
with gr.Blocks(title="Email Campaign Manager", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📧 Email Campaign Manager")
    gr.Markdown("Manage your influencer email campaigns with AI-powered suggestions and **REAL** reply tracking")

    gr.Markdown("---")
    gr.Markdown("""
    💡 **Quick Start Guide:**
    🔐 **Authenticate Gmail** first --> 📁 **Load your CSV** to verify contacts --> ✍️ **Write your email** using `{influencer_name}` for personalization --> 🤖 **Generate suggestions** with AI --> ☑️ **Select your preferred options** using checkboxes --> 📤 **Send your campaign** --> 🔄 **Track REAL replies** automatically (only from your original contacts)
    """)
    gr.Markdown("⚠️ **Note:** Use `{influencer_name}` (single braces) in your email body input - the system will convert it automatically!")
    gr.Markdown("🎯 **Fixed:** Now only tracks actual replies from people in your contact list!")

    
    with gr.Tabs() as tabs:
        # Tab 1: Authentication
        with gr.Tab("🔐 Authentication", id=0):
            gr.Markdown("### Gmail Authentication")
            auth_btn = gr.Button("🔑 Authenticate Gmail", variant="primary")
            auth_status = gr.Textbox(label="Authentication Status", interactive=False)
            
            # Next button for Authentication tab
            gr.Markdown("---")
            with gr.Row(elem_classes="centered-row"):
                next_to_composition = gr.Button("Next: Email Composition ➡️", variant="secondary", size="lg")
            
            auth_btn.click(
                authenticate_gmail,
                outputs=[auth_status, gr.State()]
            )
        
        # Tab 2: Email Composition
        with gr.Tab("✍️ Email Composition", id=1):
            gr.Markdown("### Create Your Email Campaign")
            
            with gr.Row():
                with gr.Column():
                    subject_input = gr.Textbox(
                        label="📩 Email Subject",
                        placeholder="Enter your email subject... (use {influencer_name} for personalization)",
                        lines=2,
                        info="Example: Collaboration Opportunity with {influencer_name}"
                    )
                    message_input = gr.Textbox(
                        label="📝 Email Message",
                        placeholder="Enter your email message... (use {influencer_name} for personalization)",
                        lines=5,
                        info="Example: Hi {influencer_name}, I hope you're doing well. I'd love to collaborate..."
                    )
                    generate_btn = gr.Button("🤖 Generate AI Suggestions", variant="primary")
            
            suggestion_status = gr.Textbox(label="Status", interactive=False)
            
            # Store suggestions in state for reference
            subject_suggestions_state = gr.State([])
            message_suggestions_state = gr.State([])
            
            # Hidden textboxes to store selected values
            selected_subject = gr.Textbox(visible=False)
            selected_message = gr.Textbox(visible=False)
            
            with gr.Column():
                with gr.Row():
                    subject_radio = gr.Radio(
                        label="Choose Subject Option",
                        choices=[],
                        value=None,
                        interactive=True
                    )
                
                with gr.Row():
                    message_radio = gr.Radio(
                        label="Choose Message Option",
                        choices=[],
                        value=None,
                        interactive=True
                    )
            
            save_btn = gr.Button("💾 Save Selection", variant="secondary", size="lg")
            save_status = gr.Textbox(label="Save Status", interactive=False)
            
            # Next button for Email Composition tab
            gr.Markdown("---")
            with gr.Row():
                prev_to_auth = gr.Button("⬅️ Previous: Authentication", variant="secondary")
                next_to_campaign = gr.Button("Next: Campaign Management ➡️", variant="secondary", size="lg")
            
            # Event handlers
            def update_suggestions_and_radio(subject, message):
                status, subject_list, message_list, default_subject, default_message = generate_email_suggestions(subject, message)
                return (
                    status,
                    gr.Radio(choices=subject_list, value=None),  # Update subject radio
                    gr.Radio(choices=message_list, value=None),  # Update message radio
                    subject_list,  # Store in state
                    message_list,  # Store in state
                    "",  # Clear selected subject
                    ""   # Clear selected message
                )
            
            generate_btn.click(
                update_suggestions_and_radio,
                inputs=[subject_input, message_input],
                outputs=[
                    suggestion_status, 
                    subject_radio, 
                    message_radio,
                    subject_suggestions_state,
                    message_suggestions_state,
                    selected_subject, 
                    selected_message
                ]
            )
            
            # Update selected values when radio buttons change
            subject_radio.change(
                update_selected_subject,
                inputs=[subject_radio],
                outputs=[selected_subject]
            )
            
            message_radio.change(
                update_selected_message,
                inputs=[message_radio],
                outputs=[selected_message]
            )
            
            save_btn.click(
                save_selection,
                inputs=[selected_subject, selected_message],
                outputs=[save_status]
            )
        
        # Tab 3: Campaign Management
        with gr.Tab("📤 Campaign Management", id=2):
            gr.Markdown("### Manage Your Email Campaign")
            
            csv_path_input = gr.Textbox(
                label="📁 CSV File Path",
                value="influencer.csv",
                placeholder="Path to your contacts CSV file"
            )
            
            load_csv_btn = gr.Button("📊 Load CSV Info")
            csv_info = gr.Textbox(label="CSV Information", interactive=False)
            
            gr.Markdown("---")
            
            with gr.Row():
                send_emails_btn = gr.Button("📧 Send Initial Emails", variant="primary", size="lg")
                send_status = gr.Textbox(label="Send Status", interactive=False)
            
            # Next button for Campaign Management tab
            gr.Markdown("---")
            with gr.Row():
                prev_to_composition = gr.Button("⬅️ Previous: Email Composition", variant="secondary")
                next_to_tracking = gr.Button("Next: Reply Tracking ➡️", variant="secondary", size="lg")
            
            load_csv_btn.click(
                load_csv_info,
                inputs=[csv_path_input],
                outputs=[csv_info]
            )
            
            send_emails_btn.click(
                send_initial_emails,
                inputs=[csv_path_input],
                outputs=[send_status]
            )
        
        # Tab 4: Reply Tracking
        with gr.Tab("🔄 Reply Tracking", id=3):
            gr.Markdown("### Live Reply Tracking - FIXED! 🎯")
            gr.Markdown("Monitor **REAL** replies from your original contacts and automatically remove responders from your contact list")
            gr.Markdown("⚠️ **Important:** Only emails from people in your original CSV will be considered as replies!")
            
            with gr.Row():
                with gr.Column():
                    tracking_status_display = gr.Textbox(
                        label="Tracking Status",
                        value="🔴 Inactive",
                        interactive=False
                    )
                    
                with gr.Column():
                    with gr.Row():
                        start_tracking_btn = gr.Button("🚀 Start Tracking", variant="primary")
                        stop_tracking_btn = gr.Button("🛑 Stop Tracking", variant="stop")
                        refresh_status_btn = gr.Button("🔄 Refresh Status")
            
            tracking_output = gr.Textbox(label="Tracking Output", interactive=False)
            
            # Response display section
            gr.Markdown("---")
            gr.Markdown("### 📧 Email Responses")
            
            with gr.Row():
                responses_display = gr.Textbox(
                    label="Contacts Who Responded",
                    value="📧 No responses yet", 
                    interactive=False,
                    lines=10
                )
                
            with gr.Row():
                refresh_responses_btn = gr.Button("🔄 Refresh Responses", variant="secondary")
                clear_responses_btn = gr.Button("🗑️ Clear Response Log", variant="stop")
            
            # Previous button for Reply Tracking tab (no next since it's the last tab)
            gr.Markdown("---")
            with gr.Row(elem_classes="centered-row"):
                prev_to_campaign = gr.Button("⬅️ Previous: Campaign Management", variant="secondary")
            
            # FIXED: Update responses display after tracking actions
            def start_tracking_and_refresh(csv_path):
                result = start_reply_tracking(csv_path)
                responses = get_responded_contacts()
                return result, responses
            
            def stop_tracking_and_refresh():
                result = stop_reply_tracking()
                responses = get_responded_contacts() 
                return result, responses
            
            def clear_log_and_refresh():
                result = clear_response_log()
                responses = get_responded_contacts()
                return result, responses
            
            # Event handlers for tracking - FIXED to update both outputs
            start_tracking_btn.click(
                start_tracking_and_refresh,
                inputs=[csv_path_input],
                outputs=[tracking_output, responses_display]
            )
            
            stop_tracking_btn.click(
                stop_tracking_and_refresh,
                outputs=[tracking_output, responses_display]
            )
            
            refresh_status_btn.click(
                get_tracking_status,
                outputs=[tracking_status_display]
            )
            
            # Response management handlers
            refresh_responses_btn.click(
                refresh_response_data,
                outputs=[responses_display]
            )
            
            clear_responses_btn.click(
                clear_log_and_refresh,
                outputs=[tracking_output, responses_display]
            )
            
            # ADDED: Auto-refresh button with instructions
            gr.Markdown("💡 **Tip:** Click 'Refresh Responses' periodically to see new replies while tracking is active")
            gr.Markdown("🎯 **Fixed Feature:** Now only genuine replies from your contact list are tracked!")
    
    # Tab navigation event handlers
    next_to_composition.click(lambda: gr.Tabs(selected=1), outputs=[tabs])
    next_to_campaign.click(lambda: gr.Tabs(selected=2), outputs=[tabs])
    next_to_tracking.click(lambda: gr.Tabs(selected=3), outputs=[tabs])
    
    prev_to_auth.click(lambda: gr.Tabs(selected=0), outputs=[tabs])
    prev_to_composition.click(lambda: gr.Tabs(selected=1), outputs=[tabs])
    prev_to_campaign.click(lambda: gr.Tabs(selected=2), outputs=[tabs])
    
# if __name__ == "__main__":
#     app.launch(
#         server_name="0.0.0.0",
#         server_port=7860,
#         share=False,
#         debug=False
#     )

if __name__ == "__main__":
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        debug=False
    )
