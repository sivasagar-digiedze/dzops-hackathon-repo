
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sender_email = ""
app_password = ""


def send_smtp_email(receiver_email, subject, body, thread_id = None):
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    if thread_id:
        message["In-Reply-To"] = thread_id
        message["References"] = thread_id

    message.attach(MIMEText(body, "plain"))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls() 
        server.login(sender_email, app_password)
        server.sendmail(sender_email, receiver_email, message.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        server.quit()

def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else None

def build_conversation_context(messages):
    context = []
    for msg in messages:
        role = "User" if msg["sender"] == "user" else "Agent"
        context.append(f"{role}: {msg['message']}")

    return "\n".join(context[-10:])

RESOURCE_CONTRACTS = {
    "storage": {
        "list": ["account_name"],
        "read": ["account_name", "container_name"],
        "delete": ["account_name", "container_name", "blob_name"],
        "upload": ["account_name", "container_name", "blob_name", "data"]
    }
}
