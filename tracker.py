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

def clean_name(text):
    text = " ".join(text.split())

    for prefix in [
        "Relevance ",
        "Best Sellers ",
        "Newness "
    ]:
        if text.startswith(prefix):
            text = text[len(prefix):]

    positions = []
    for label in ATTRIBUTE_LABELS:
        pos = text.find(label)
        if pos != -1:
            positions.append(pos)

    if positions:
        text = text[:min(positions)]

    for marker in ["Quick View", "Add to bag", "Add to Bag"]:
        if marker in text:
            text = text.split(marker)[-1]

    return " ".join(text.split()).strip()


def get_brand(name):
    n = name.lower()

    if "boohoo" in n[:25]:
        return "boohoo"
    if n.startswith("nastygal"):
        return "NastyGal"
    if n.startswith("misspap"):
        return "MissPap"
    if n.startswith("debenhams"):
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

        # Accept/reject cookie banner if it blocks clicks
        for label in ["REJECT ALL", "ACCEPT ALL"]:
            try:
                button = page.get_by_text(label, exact=True)
                if button.count() > 0:
                    button.first.click(timeout=3000)
                    break
            except:
                pass

        # Repeatedly click Boohoo's Load More control
        clicks = 0

        while clicks < 120:
            try:
                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                page.wait_for_timeout(1000)

                load_more = page.get_by_text(
                    re.compile(r"Load More", re.I)
                )

                if load_more.count() == 0:
                    print("No Load More button found.")
                    break

                button = load_more.last

                if not button.is_visible():
                    print("Load More no longer visible.")
                    break

                button.scroll_into_view_if_needed()
                button.click(timeout=10000)

                clicks += 1
                page.wait_for_timeout(1500)

                print(f"Clicked Load More {clicks} times")

            except Exception as e:
                print(f"Stopped loading after {clicks} clicks: {e}")
                break

        print(f"Finished loading after {clicks} Load More clicks")

        text = " ".join(page.locator("body").inner_text().split())

        browser.close()

    # Product prices:
    # discounted: £15.00 £32.00 -53%
    # full price: £49.00

    price_pattern = re.compile(
        r"£(\d+(?:\.\d{1,2})?)"
        r"(?:\s*£(\d+(?:\.\d{1,2})?)\s*-(\d+)%)?"
    )

    matches = list(price_pattern.finditer(text))
    previous_end = 0

    for match in matches:
        block = text[previous_end:match.start()].strip()

        if len(block) > 500:
            block = block[-500:]

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
            and 5 <= len(name) <= 180
            and "£" not in name
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

    df.to_csv("latest.csv", index=False)

    # Preserve historical snapshots
    if os.path.exists("history.csv"):
        old = pd.read_csv("history.csv")
        old = old[old["date"].astype(str) != today]
        history = pd.concat([old, df], ignore_index=True)
    else:
        history = df.copy()

    history.to_csv("history.csv", index=False)

    # Summary
    if not df.empty:
        discounted_df = df[df["discounted"] == True]

        summary = pd.DataFrame([{
            "date": today,
            "products_captured": len(df),
            "products_discounted": len(discounted_df),
            "pct_assortment_discounted":
                round(len(discounted_df) / len(df) * 100, 1),
            "average_discount_pct":
                round(discounted_df["discount_pct"].mean(), 1)
                if len(discounted_df) else 0,
            "median_discount_pct":
                round(discounted_df["discount_pct"].median(), 1)
                if len(discounted_df) else 0,
            "discounted_30pct_plus":
                int((df["discount_pct"] >= 30).sum()),
            "discounted_50pct_plus":
                int((df["discount_pct"] >= 50).sum())
        }])

        summary.to_csv("summary.csv", index=False)

        print("\nDAILY SUMMARY")
        print(summary.to_string(index=False))

    print(f"\nTOTAL PRODUCTS CAPTURED: {len(df)}")


if __name__ == "__main__":
    extract()
