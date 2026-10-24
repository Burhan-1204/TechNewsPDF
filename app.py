import subprocess
import sys

subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium"],
    check=True
)

import os
import re
import hmac
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from tech_news_pdf import (
    collect_news,
    collect_techcrunch,
    generate_pdf,
    PDF_PATH,
)
from send_email import send_pdf_email


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

st.set_page_config(
    page_title="Daily Tech News Generator",
    page_icon="📰",
    layout="wide",
)


# ---------------------------------------------------------
# BASIC SIGN-IN
# Configure APP_USERNAME and APP_PASSWORD in Streamlit
# Community Cloud Secrets or as environment variables.
# Never hardcode credentials or commit them to GitHub.
# ---------------------------------------------------------

def get_setting(name):
    """Read a setting from Streamlit secrets, then environment variables."""
    try:
        value = st.secrets.get(name)
        if value is not None and str(value).strip():
            return str(value)
    except Exception:
        # Local development may not have a Streamlit secrets file.
        pass

    value = os.getenv(name)
    return value.strip() if value else None


APP_USERNAME = get_setting("APP_USERNAME")
APP_PASSWORD = get_setting("APP_PASSWORD")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not APP_USERNAME or not APP_PASSWORD:
    st.title("📰 Daily Tech News Generator")
    st.error(
        "Sign-in is not configured yet. Set APP_USERNAME and APP_PASSWORD "
        "in your local environment or Streamlit Community Cloud secrets, "
        "then restart the app."
    )
    st.stop()

if not st.session_state.authenticated:
    st.title("📰 Daily Tech News Generator")
    st.subheader("Sign in")
    st.caption("Please sign in to access the Daily Tech News Generator.")

    with st.form("login_form", clear_on_submit=False):
        entered_username = st.text_input("Username")
        entered_password = st.text_input("Password", type="password")
        submitted = st.form_submit_button(
            "Sign in",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        username_ok = hmac.compare_digest(
            entered_username.strip(),
            APP_USERNAME,
        )
        password_ok = hmac.compare_digest(
            entered_password,
            APP_PASSWORD,
        )

        if username_ok and password_ok:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    st.stop()

with st.sidebar:
    st.caption("Signed in")
    if st.button("Sign out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.pdf_ready = False
        st.rerun()

# Initialize session state
if "techcrunch_articles" not in st.session_state:
    st.session_state.techcrunch_articles = []

if "hacker_articles" not in st.session_state:
    st.session_state.hacker_articles = []

if "pdf_ready" not in st.session_state:
    st.session_state.pdf_ready = False

if "pdf_path" not in st.session_state:
    st.session_state.pdf_path = str(PDF_PATH)


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def collect_latest_news():
    """Collect fresh articles from both news sources."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Collect TechCrunch first
            techcrunch_articles = collect_techcrunch(page)

            # Collect Hacker News second
            hacker_articles = collect_news(page)
        finally:
            browser.close()

    return techcrunch_articles, hacker_articles


def is_valid_email(email):
    """Basic email format validation."""
    return bool(
        re.fullmatch(
            r"[^@\s,]+@[^@\s,]+\.[^@\s,]+",
            email.strip(),
        )
    )


def display_articles(articles, source_name):
    """Display article titles and links."""
    if not articles:
        st.info(f"No {source_name} articles were collected.")
        return

    for index, article in enumerate(articles, start=1):
        title = article.get("title", "Untitled article")
        url = article.get("url", "")

        # Escape square brackets and parentheses in Markdown link text/URL.
        safe_title = title.replace("[", r"\[").replace("]", r"\]")
        if url:
            st.markdown(f"{index}. [{safe_title}]({url})")
        else:
            st.markdown(f"{index}. **{safe_title}**")


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("📰 Daily Tech News Generator")

st.markdown(
    """
    Collect the latest technology news, generate a PDF report,
    download it, or send it to your chosen email recipients.
    """
)

st.divider()


# ---------------------------------------------------------
# GENERATE PDF BUTTON
# Collect fresh news + generate PDF in one action
# ---------------------------------------------------------

if st.button(
    "📄 Generate PDF",
    type="primary",
    use_container_width=True,
):
    # Clear the previous result so an old PDF isn't mistaken
    # for the newly generated report.
    st.session_state.pdf_ready = False

    try:
        with st.spinner(
            "Collecting fresh TechCrunch and Hacker News articles..."
        ):
            techcrunch_articles, hacker_articles = collect_latest_news()

        st.session_state.techcrunch_articles = techcrunch_articles
        st.session_state.hacker_articles = hacker_articles

        if not techcrunch_articles and not hacker_articles:
            st.error("No articles were collected. Please try again.")
        else:
            with st.spinner("Generating your PDF report..."):
                # Keep the existing generate_pdf argument order.
                # PDF section order is controlled by tech_news_pdf.py/template.
                generate_pdf(
                    hacker_articles,
                    techcrunch_articles,
                )

            pdf_path = Path(PDF_PATH)

            if pdf_path.exists():
                st.session_state.pdf_path = str(pdf_path)
                st.session_state.pdf_ready = True

                st.success(
                    "PDF generated successfully! "
                    f"TechCrunch: {len(techcrunch_articles)} articles; "
                    f"Hacker News: {len(hacker_articles)} articles."
                )
            else:
                st.error(
                    "PDF generation finished, but the expected "
                    "PDF file was not found."
                )

    except Exception as exc:
        st.session_state.pdf_ready = False
        st.error(f"An error occurred: {exc}")


# ---------------------------------------------------------
# ARTICLE PREVIEW
# TechCrunch MUST appear before Hacker News
# ---------------------------------------------------------

techcrunch_articles = st.session_state.techcrunch_articles
hacker_articles = st.session_state.hacker_articles

if techcrunch_articles or hacker_articles:
    st.divider()
    st.header("🗞️ Collected News")

    st.metric(
        "Total articles",
        len(techcrunch_articles) + len(hacker_articles),
    )

    # TechCrunch tab is deliberately first.
    techcrunch_tab, hacker_tab = st.tabs(
        [
            f"TechCrunch ({len(techcrunch_articles)})",
            f"Hacker News ({len(hacker_articles)})",
        ]
    )

    with techcrunch_tab:
        display_articles(techcrunch_articles, "TechCrunch")

    with hacker_tab:
        display_articles(hacker_articles, "Hacker News")


# ---------------------------------------------------------
# DOWNLOAD PDF + SEND EMAIL
# ---------------------------------------------------------

if st.session_state.pdf_ready:
    pdf_path = Path(st.session_state.pdf_path)

    if pdf_path.exists():
        st.divider()
        st.header("📥 Download Your Report")

        with open(pdf_path, "rb") as pdf_file:
            pdf_data = pdf_file.read()

        st.download_button(
            label="⬇️ Download Daily_News.pdf",
            data=pdf_data,
            file_name="Daily_News.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        # Email section: recipient input appears immediately before
        # the Send PDF button, as requested.
        st.divider()
        st.header("✉️ Send PDF by Email")

        default_recipients = os.getenv("EMAIL_RECIPIENTS", "")

        recipients_text = st.text_input(
            "Receiver email addresses",
            value=default_recipients,
            placeholder="person1@gmail.com, person2@gmail.com",
            help="Enter one or more email addresses separated by commas.",
            key="recipient_input",
        )

        if st.button(
            "Send PDF to Recipients",
            use_container_width=True,
        ):
            recipients = [
                email.strip()
                for email in recipients_text.split(",")
                if email.strip()
            ]

            if not recipients:
                st.error("Please enter at least one recipient email address.")
            else:
                invalid_emails = [
                    email for email in recipients
                    if not is_valid_email(email)
                ]

                if invalid_emails:
                    st.error(
                        "Please correct these email addresses: "
                        + ", ".join(invalid_emails)
                    )
                elif len({email.lower() for email in recipients}) != len(recipients):
                    st.error(
                        "Duplicate email addresses found. Please remove duplicates."
                    )
                else:
                    try:
                        with st.spinner("Sending the PDF email..."):
                            # Positional argument avoids keyword mismatch
                            # with an older imported function signature.
                            success = send_pdf_email(pdf_path, recipients)

                        if success:
                            st.success(
                                "The email was accepted by the SMTP server "
                                "for all recipients. This does not guarantee "
                                "final inbox delivery."
                            )
                        else:
                            st.error(
                                "Email sending failed. Check the terminal "
                                "output for details."
                            )
                    except Exception as exc:
                        st.error(f"Email error: {exc}")
    else:
        st.warning(
            "The generated PDF could not be found. "
            "Please generate the report again."
        )


# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.divider()

st.caption(
    "Daily Tech News Generator | "
    "TechCrunch first · Hacker News second"
)
