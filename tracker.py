from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import re

URL = "https://www.boohoo.com/buy/vestidos"

# These are attribute labels that appear between a product name and its prices
ATTRIBUTE_LABELS = [
    "Body fit:", "Design:", "Detail:", "Fabric:", "Length:",
    "Neckline:", "Occasion:", "Sleeve length:", "Style:"
]

def clean_name(text):
    """Remove Boohoo's attribute text from the end of a product description."""
    positions = []

    for label in ATTRIBUTE_LABELS:
        pos = text.find(label)
        if pos != -1:
            positions.append(pos)

    if positions:
        text = text[:min(positions)]

    return " ".join(text.split()).strip()


def extract():
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

        # Scroll down to load products
        for _ in range(20):
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(750)

        text = page.locator("body").inner_text()
        text = " ".join(text.split())

        # Boohoo's listing format is broadly:
        # PRODUCT NAME + attributes + £current £original -XX%
        #
        # We anchor on the two prices + discount, then work backwards
        # to the previous price/discount boundary.

        price_discount = re.compile(
            r"£(\d+(?:\.\d{1,2})?)\s*"
            r"£(\d+(?:\.\d{1,2})?)\s*"
            r"-(\d+)%"
        )

        matches = list(price_discount.finditer(text))

        previous_end = 0

        for match in matches:
            block = text[previous_end:match.start()].strip()

            # Keep the tail of the block, which contains the current product
            # rather than navigation text from much earlier on the page.
            if len(block) > 500:
                block = block[-500:]

            name = clean_name(block)

            # Strip common junk before the actual product name
            junk_markers = [
                "Quick View",
                "Add to bag",
                "Add to Bag"
            ]

            for marker in junk_markers:
                if marker in name:
                    name = name.split(marker)[-1].strip()

            current_price = float(match.group(1))
            original_price = float(match.group(2))
            discount_pct = int(match.group(3))

            # Basic sanity checks
            if (
                name
                and len(name) >= 5
                and original_price >= current_price
                and 0 <= discount_pct <= 100
            ):
                products.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "product": name,
                    "current_price": current_price,
                    "original_price": original_price,
                    "discount_pct": discount_pct,
                })

            previous_end = match.end()

        browser.close()

    df = pd.DataFrame(products)

    if not df.empty:
        df = df.drop_duplicates(
            subset=[
                "product",
                "current_price",
                "original_price",
                "discount_pct"
            ]
        )

        df = df.sort_values(
            ["discount_pct", "product"],
            ascending=[False, True]
        )

    df.to_csv("latest.csv", index=False)

    print(f"Captured {len(df)} discounted products")

    if not df.empty:
        print(
            f"Average discount: {df['discount_pct'].mean():.1f}%"
        )


if __name__ == "__main__":
    extract()
