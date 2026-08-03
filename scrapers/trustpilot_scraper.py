from playwright.sync_api import sync_playwright
import pandas as pd
import time

URL = "https://www.trustpilot.com/review/blinkit.nl"


def scrape_trustpilot(max_pages=5):
    reviews = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        BASE_URL = "https://www.trustpilot.com/review/blinkit.nl"
        for page_no in range(1, max_pages + 1):
            url = f"{BASE_URL}?page={page_no}"
            print(f"\nScraping {url}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(3000)
            cards = page.locator("article")
            print("Found:", cards.count())

            for i in range(min(cards.count(), 5)):
                 print("\n" + "=" * 80)
                 card = cards.nth(i)
                 text = card.inner_text()
                 reviews.append({
                     "source": "trustpilot",
                     "raw_text": text
                     })

        browser.close()

    return pd.DataFrame(reviews)


if __name__ == "__main__":
    df = scrape_trustpilot(max_pages=10)
    df.to_csv("trustpilot_reviews.csv", index=False)
    print(df.head())
    print(f"Saved {len(df)} reviews")