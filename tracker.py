from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import re
import os

URL = "https://www.boohoo.com/buy/vestidos"

ATTRIBUTE_LABELS = [
    "Body fit:", "Design:", "Detail:", "Fabric:", "Length:",
    "Neckline:", "Occasion:", "Sleeve length:", "Style:"
]

JUNK_PHRASES = [
    "privacy policy",
    "let me choose",
    "reject all",
    "accept all",
    "skip to main content",
    "show more filters",
    "sort:",
    "products style size colour",
]

def clean_name(text):
    text = " ".join(text.split())

    # Cut off product attributes
    positions = []
    for label in ATTRIBUTE_LABELS:
        pos = text.find(label)
        if pos != -1:
            positions.append(pos)

    if positions:
        text = text[:min(positions)]

    # Remove common page junk
    for junk in JUNK_PHRASES:
        pos = text.lower().rfind(junk)
        if pos != -1:
            text = text[pos + len(junk):]

    for marker in ["Quick View", "Add to bag", "Add to Bag"]:
        if marker in text:
            text = text.split(marker)[-1]

    return " ".join(text.split()).strip()


def get_brand(name):
    lower = name.lower()

    if lower.startswith("plus boohoo"):
        return "boohoo"
    elif lower.startswith("boohoo"):
        return "boohoo"
    elif lower.startswith("nastygal"):
        return "NastyGal"
    elif lower.startswith("misspap"):
        return "MissPap"
    elif lower.startswith("debenhams"):
        return "Debenhams"

    return "Other"


def extract():
    today = datetime.now().strftime("%Y-%m-%d")
    products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1440, "height": 1200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
        )

        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        # Scroll repeatedly to load more catalogue items
        last_height = 0

        for _ in range(80):
            page.mouse.wheel(0, 3500)
            page.wait_for_timeout(600)

            height = page.evaluate("document.body.scrollHeight")

            if height == last_height:
                break

            last_height = height

        text = " ".join(page.locator("body").inner_text().split())

        browser.close()

    # Matches either:
    # £15.00 £32.00 -53%
    # or a single full price such as £49.00

    price_pattern = re.compile(
        r"£(\d+(?:\.\d{1,2})?)"
        r"(?:\s*£(\d+(?:\.\d{1,2})?)\s*-(\d+)%)?"
    )

    matches = list(price_pattern.finditer(text))
    previous_end = 0

    for match in matches:
        block = text[previous_end:match.start()].strip()

        # Avoid dragging huge amounts of navigation text into a name
        if len(block) > 600:
            block = block[-600:]

        name = clean_name(block)

        current_price = float(match.group(1))

        if match.group(2):
            original_price = float(match.group(2))
            discount_pct = int(match.group(3))
            discounted = True
        else:
            original_price = current_price
            discount_pct = 0
            discounted = False

        if (
            name
            and len(name) >= 5
            and len(name) <= 180
            and "£" not in name
            and not any(j in name.lower() for j in JUNK_PHRASES)
            and original_price >= current_price
            and 0 <= discount_pct <= 100
        ):
            products.append({
                "date": today,
                "brand": get_brand(name),
                "product": name,
                "current_price": current_price,
                "original_price": original_price,
                "discount_pct": discount_pct,
                "discounted": discounted
            })

        previous_end = match.end()

    df = pd.DataFrame(products)

    if not df.empty:
        df = df.drop_duplicates(
            subset=["product", "current_price", "original_price"]
        )

    # Save today's clean snapshot
    df.to_csv("latest.csv", index=False)

    # Add today's observations to permanent history
    history_file = "history.csv"

    if os.path.exists(history_file):
        old = pd.read_csv(history_file)

        # Prevent duplicate rows if we manually rerun on the same day
        old = old[old["date"].astype(str) != today]

        history = pd.concat([old, df], ignore_index=True)
    else:
        history = df.copy()

    history.to_csv(history_file, index=False)

    # Produce a simple daily summary
    if not df.empty:
        total = len(df)
        discounted_count = int(df["discounted"].sum())
        markdown_rate = discounted_count / total * 100

        discounted_df = df[df["discounted"]]

        avg_discount = (
            discounted_df["discount_pct"].mean()
            if not discounted_df.empty
            else 0
        )

        median_discount = (
            discounted_df["discount_pct"].median()
            if not discounted_df.empty
            else 0
        )

        summary = pd.DataFrame([{
            "date": today,
            "products_captured": total,
            "products_discounted": discounted_count,
            "pct_assortment_discounted": round(markdown_rate, 1),
            "average_discount_pct": round(avg_discount, 1),
            "median_discount_pct": round(median_discount, 1),
            "discounted_30pct_plus": int(
                (df["discount_pct"] >= 30).sum()
            ),
            "discounted_50pct_plus": int(
                (df["discount_pct"] >= 50).sum()
            )
        }])

        summary.to_csv("summary.csv", index=False)

        print(summary.to_string(index=False))

    print(f"Captured {len(df)} products")


if __name__ == "__main__":
    extract()
