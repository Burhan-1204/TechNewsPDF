
import os
import smtplib
import traceback

from pathlib import Path
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# ---------------------------------------------------------
# LOAD ENVIRONMENT VARIABLES
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

GMAIL_USER = os.getenv("GMAIL_USER")
APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Default recipients from .env
RECIPIENTS = [
    email.strip()
    for email in os.getenv("EMAIL_RECIPIENTS", "").split(",")
    if email.strip()
]


# ---------------------------------------------------------
# SEND PDF EMAIL
# ---------------------------------------------------------

def send_pdf_email(pdf_path, recipients=None):
    """
    Send the PDF to the supplied recipients.

    If recipients are supplied by the frontend, use those.
    Otherwise, use EMAIL_RECIPIENTS from .env.

    Returns True if SMTP accepts all recipients.
    Returns False if sending fails or any recipient is rejected.
    """

    server = None

    # Use frontend recipients if provided; otherwise use .env
    actual_recipients = (
        [
            email.strip()
            for email in recipients
            if email and email.strip()
        ]
        if recipients is not None
        else RECIPIENTS.copy()
    )

    try:
        # -------------------------------------------------
        # VALIDATE CONFIGURATION
        # -------------------------------------------------

        missing = []

        if not GMAIL_USER:
            missing.append("GMAIL_USER")

        if not APP_PASSWORD:
            missing.append("GMAIL_APP_PASSWORD")

        if missing:
            raise ValueError(
                "Missing environment variables: "
                + ", ".join(missing)
            )

        if not actual_recipients:
            raise ValueError(
                "Please provide at least one recipient email address."
            )

        # Remove duplicate addresses
        actual_recipients = list(
            dict.fromkeys(
                email.lower()
                for email in actual_recipients
            )
        )

        # Basic email format validation
        invalid_recipients = [
            email
            for email in actual_recipients
            if (
                "@" not in email
                or email.startswith("@")
                or email.endswith("@")
                or "." not in email.rsplit("@", 1)[-1]
                or any(char.isspace() for char in email)
            )
        ]

        if invalid_recipients:
            raise ValueError(
                "Invalid email address format: "
                + ", ".join(invalid_recipients)
            )

        # -------------------------------------------------
        # VALIDATE PDF
        # -------------------------------------------------

        pdf_path = Path(pdf_path)

        if not pdf_path.is_file():
            raise FileNotFoundError(
                f"PDF file not found: {pdf_path}"
            )

        print("\n--- Preparing Email ---")
        print("PDF attached:", pdf_path.name)
        print("Recipients:", ", ".join(actual_recipients))

        # -------------------------------------------------
        # CREATE EMAIL
        # -------------------------------------------------

        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = ", ".join(actual_recipients)
        msg["Subject"] = "Daily Tech News - Latest Updates"

        body = """
            Hello!

            Your Daily Tech News PDF is ready.

            The attached report contains articles from
            TechCrunch and Hacker News.

            Happy reading!

            Automated Tech News Generator
        """

        msg.attach(MIMEText(body, "plain"))

        # -------------------------------------------------
        # ATTACH PDF
        # -------------------------------------------------

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

        # -------------------------------------------------
        # CONNECT TO GMAIL
        # -------------------------------------------------

        print("Connecting to Gmail SMTP server...")

        server = smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=30,
        )

        server.ehlo()
        server.starttls()
        server.ehlo()

        print("Logging into Gmail...")
        server.login(GMAIL_USER, APP_PASSWORD)

        # -------------------------------------------------
        # SEND EMAIL
        # -------------------------------------------------

        print("\n--- Sending Email to Recipients ---")

        failed_recipients = server.send_message(
            msg,
            from_addr=GMAIL_USER,
            to_addrs=actual_recipients,
        )

        successful_recipients = [
            email
            for email in actual_recipients
            if email not in failed_recipients
        ]

        if successful_recipients:
            print(
                "SMTP accepted:",
                ", ".join(successful_recipients),
            )

        if failed_recipients:
            print("\nSMTP rejected these recipients:")

            for email, error in failed_recipients.items():
                print(f"  {email}: {error}")

        # Only report complete SMTP acceptance as success
        if failed_recipients:
            print(
                "\nEmail was not accepted for all recipients."
            )
            return False

        print("\nSuccess! SMTP accepted all recipients.")
        print("Recipients:", ", ".join(actual_recipients))
        print(
            "Note: SMTP acceptance does not guarantee "
            "final inbox delivery."
        )

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
                pass
