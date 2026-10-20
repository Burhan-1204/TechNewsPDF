
import os
import smtplib
import traceback

from pathlib import Path
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


# ---------------------------------------------------------
# Load Environment Variables
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

GMAIL_USER = os.getenv("GMAIL_USER")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RECIPIENTS = [
    email.strip()
    for email in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if email.strip()
]


# ---------------------------------------------------------
# Send PDF Email
# ---------------------------------------------------------

def send_pdf_email(pdf_path):

    server = None

    try:
        # Validate configuration
        missing = []

        if not GMAIL_USER:
            missing.append("GMAIL_USER")

        if not APP_PASSWORD:
            missing.append("GMAIL_APP_PASSWORD")

        if not RECIPIENTS:
            missing.append("EMAIL_RECIPIENTS")

        if missing:
            raise ValueError(
                "Missing environment variables: "
                + ", ".join(missing)
            )

        pdf_path = Path(pdf_path)

        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"PDF file not found: {pdf_path}"
            )

        print("\n--- Preparing Email ---")

        # Create email
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = ", ".join(RECIPIENTS)
        msg["Subject"] = "Daily Tech News - Latest Updates"

        body = """
            Hello!

            Your Daily Tech News PDF is ready.

            The attached report contains articles from
            Hacker News and TechCrunch.

            Happy reading!

            Automated Tech News Generator
        """

        msg.attach(MIMEText(body, "plain"))

        # Attach PDF
        with open(pdf_path, "rb") as pdf_file:
            attachment = MIMEApplication(
                pdf_file.read(),
                _subtype="pdf",
            )

        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=pdf_path.name,
        )

        msg.attach(attachment)

        print("PDF attached:", pdf_path.name)
        print("Connecting to Gmail SMTP server...")

        # Connect securely
        server = smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=30,
        )

        server.ehlo()
        server.starttls()
        server.ehlo()

        # Authenticate
        print("Logging into Gmail...")
        server.login(GMAIL_USER, APP_PASSWORD)

        # Send message
        print("\n--- Sending Email to Recipients ---")

        failed_recipients = server.send_message(
            msg,
            from_addr=GMAIL_USER,
            to_addrs=RECIPIENTS,
        )

        successful_recipients = [
            email
            for email in RECIPIENTS
            if email not in failed_recipients
        ]

        if successful_recipients:
            print("Email accepted for:", ", ".join(successful_recipients))

        if failed_recipients:
            print("Failed recipients:")
            for email, error in failed_recipients.items():
                print(f"  {email}: {error}")

        print("Success! Email sent.")
        print("Recipients:", ", ".join(RECIPIENTS))
        return True

    except Exception:
        print("\nEmail sending failed:")
        print(traceback.format_exc())
        return False

    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                print(traceback.format_exc())
