import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List

GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
SENDER_EMAIL = "matt@manhattancomputation.com"
APP_PASSWORD = "yuzi immk yjme tpie"
RECIPIENTS = ["matt@manhattancomputation.com", "jack@manhattancomputation.com"]

def send_email(subject: str, body: str) -> bool:
    """
    Send an email using Gmail SMTP server.
    
    Args:
        subject (str): Subject line of the email
        body (str): Content/body of the email
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(RECIPIENTS)
        msg['Subject'] = subject

        # Add body to email
        msg.attach(MIMEText(body, 'plain'))

        # Create SMTP session
        with smtplib.SMTP(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT) as server:
            server.starttls()  # Enable TLS
            server.login(SENDER_EMAIL, APP_PASSWORD)
            
            # Send email
            server.send_message(msg)
            
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False 