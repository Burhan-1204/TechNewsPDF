from datetime import datetime
from pathlib import Path
from html import escape
from playwright.sync_api import sync_playwright
from send_email import send_pdf_email

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

NEWS_URL = "https://news.ycombinator.com/"

# Collect more stories so filtering has a larger pool to search.
ARTICLE_LIMIT = 10

# Windows Desktop path
desktop = Path.home() / "Desktop"

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "news_template.html"

# Support Windows systems where Desktop is redirected to OneDrive
if not desktop.exists():
    onedrive_desktop = Path.home() / "OneDrive" / "Desktop"
    if onedrive_desktop.exists():
        desktop = onedrive_desktop

PDF_PATH = desktop / "Daily_News.pdf"


# ---------------------------------------------------------
# Collect news from Hacker News page
# ---------------------------------------------------------
def collect_news(page):
    """Collect the first 10 ranked articles from Hacker News."""

    print("\nOpening Hacker News...")
    page.goto(NEWS_URL, wait_until="domcontentloaded", timeout=60000)

    page.locator("tr.athing").first.wait_for(
        state="visible", timeout=20000
    )

    articles = []
    story_rows = page.locator("tr.athing")
    total = story_rows.count()

    for index in range(min(total, ARTICLE_LIMIT)):
        row = story_rows.nth(index)
        link = row.locator(".titleline > a").first

        title = link.inner_text().strip()
        url = link.get_attribute("href")

        if not url:
            continue

        # Resolve relative URLs, if any
        url = page.url if url == "" else url
        if url.startswith("/"):
            url = "https://news.ycombinator.com" + url

        # Get score from the row immediately below the story
        score = "Not available"
        subtext = row.locator(
            "xpath=following-sibling::tr[1]"
        ).locator(".score")

        if subtext.count() > 0:
            score = subtext.first.inner_text().strip()

        articles.append({
            "rank": index + 1,
            "title": title,
            "url": url,
            "score": score,
            "source": "Hacker News",
        })

    return articles


# ---------------------------------------------------------
# Collect news from TechCrunch
# -----------------------------------------------------
def collect_techcrunch(page):
    """Collect the first 10 article links from TechCrunch Latest."""

    print("\nOpening TechCrunch Latest News...")

    page.goto(
        "https://techcrunch.com/latest/",
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.locator("body").wait_for(state="visible")

    # Try common article-title selectors.
    selectors = [
        "a.loop-card__title-link",
        "a.post-block__title__link",
        "article h2 a",
        "article h3 a",
    ]

    articles = []
    seen_urls = set()

    for selector in selectors:
        links = page.locator(selector)

        if links.count() == 0:
            continue

        for i in range(links.count()):
            link = links.nth(i)

            if not link.is_visible():
                continue

            title = link.inner_text().strip()
            url = link.get_attribute("href")

            if not title or not url:
                continue

            if url.startswith("/"):
                url = "https://techcrunch.com" + url

            if not url.startswith("https://techcrunch.com/"):
                continue

            # Exclude the site's homepage and duplicate URLs.
            if url.rstrip("/") == "https://techcrunch.com":
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            articles.append({
                "rank": len(articles) + 1,
                "title": title,
                "url": url,
                "score": "N/A",
                "source": "TechCrunch",
            })

            if len(articles) >= 10:
                break

        if articles:
            break

    if not articles:
        raise RuntimeError(
            "No TechCrunch articles found. "
            "The website's HTML selectors may have changed."
        )

    return articles


# ---------------------------------------------------------
# Generate PDF using external HTML template
# ---------------------------------------------------------
def build_cards(articles):
    cards = ""

    for article in articles:
        title = escape(article["title"])
        url = escape(article["url"], quote=True)

        cards += f"""
        <article class="story">
            <div class="rank">
                {article['rank']:02d}
            </div>

            <div class="story-content">
                <h2>{title}</h2>

                <a href="{url}">{escape(article['url'])}</a>
            </div>
        </article>
        """

    return cards

def generate_pdf(hacker_articles, techcrunch_articles):
    """Generate one PDF containing news from both websites."""

    print("\n--- Generating Daily News PDF ---")

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"HTML template not found: {TEMPLATE_PATH}"
        )

    # Read HTML template
    html_content = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Prepare dynamic values
    replacements = {
        "{{DATE}}": datetime.now().strftime("%d %B %Y"),
        "{{GENERATED_AT}}": datetime.now().strftime("%I:%M %p"),
        "{{TECHCRUNCH_ARTICLES}}": build_cards(techcrunch_articles),
        "{{HACKER_NEWS_ARTICLES}}": build_cards(hacker_articles),
    }

    # Replace placeholders
    for placeholder, value in replacements.items():
        html_content = html_content.replace(placeholder, value)

    # Render HTML and save PDF
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.set_content(html_content, wait_until="load")

            page.pdf(
                path=str(PDF_PATH),
                format="A4",
                print_background=True,
                display_header_footer=False,
                prefer_css_page_size=True,
            )
        finally:
            browser.close()

    print("\nPDF generated successfully!")
    print("Hacker News articles:", len(hacker_articles))
    print("TechCrunch articles:", len(techcrunch_articles))
    print("Total articles:", len(hacker_articles) + len(techcrunch_articles))
    print("Saved location:", PDF_PATH)

def main():
    print("=" * 55)
    print("       AUTOMATED TECH NEWS PDF GENERATOR")
    print("=" * 55)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            techcrunch_articles = collect_techcrunch(page)
            print(f"TechCrunch: {len(techcrunch_articles)} articles")

            hacker_articles = collect_news(page)
            print(f"\nHacker News: {len(hacker_articles)} articles")

        finally:
            browser.close()

    print("\n--- TechCrunch ---")
    for article in techcrunch_articles:
        print(f"{article['rank']}. {article['title']}")
        print(f"   {article['url']}")

    print("\n--- Hacker News ---")
    for article in hacker_articles:
        print(f"{article['rank']}. {article['title']}")
        print(f"   {article['url']}")

    if not hacker_articles and not techcrunch_articles:
        print("No articles collected. PDF not generated.")
        return

    # Step 1: Generate the PDF
    generate_pdf(hacker_articles, techcrunch_articles)

    # Step 2: Send the generated PDF through Gmail
    print("\n--- Sending Daily News PDF by Email ---")

    email_sent = send_pdf_email(PDF_PATH)

    if email_sent:
        print("Daily News PDF emailed successfully.")
    else:
        print("PDF was generated, but email delivery failed.")


if __name__ == "__main__":
    main()
