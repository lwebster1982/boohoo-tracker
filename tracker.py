from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import re

URL = "https://www.boohoo.com/buy/vestidos"

def extract():
    products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
        )

        page.goto(URL, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(5000)

        # Scroll several times so more products load
        for _ in range(12):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1000)

        text = page.locator("body").inner_text()

        lines = [line.strip() for line in text.splitlines() if line.strip()]

        price_pattern = re.compile(r"£(\d+(?:\.\d{2})?)")
        discount_pattern = re.compile(r"-(\d+)%")

        for i, line in enumerate(lines):
            prices = price_pattern.findall(line)

            if not prices:
                continue

            # Look backwards for a likely product name
            name = ""
            for j in range(i - 1, max(i - 8, -1), -1):
                candidate = lines[j]

                if (
                    "£" not in candidate
                    and "%" not in candidate
                    and len(candidate) > 8
                    and candidate.lower() not in [
                        "add to bag",
                        "quick view",
                        "new in",
                    ]
                ):
                    name = candidate
                    break

            if not name:
                continue

            values = [float(x) for x in prices]

            current_price = values[0]
            original_price = values[1] if len(values) > 1 else values[0]

            discount_match = discount_pattern.search(line)

            if discount_match:
                discount_pct = int(discount_match.group(1))
            elif original_price > current_price:
                discount_pct = round(
                    (1 - current_price / original_price) * 100
                )
            else:
                discount_pct = 0

            products.append(
                {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "product": name,
                    "current_price": current_price,
                    "original_price": original_price,
                    "discount_pct": discount_pct,
                }
            )

        browser.close()

    df = pd.DataFrame(products)

    # Remove duplicates
    if not df.empty:
        df = df.drop_duplicates(
            subset=["product", "current_price", "original_price"]
        )

    df.to_csv("latest.csv", index=False)

    print(f"Captured {len(df)} products")


if __name__ == "__main__":
    extract()
