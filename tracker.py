
from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime

URL = "https://www.boohoo.com/womens"

def extract():
    products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")

        page.mouse.wheel(0, 12000)
        page.wait_for_timeout(3000)

        cards = page.locator("article").all()

        for card in cards:
            try:
                text = card.inner_text()

                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if len(lines) < 2:
                    continue

                name = lines[0]

                prices = []
                for l in lines:
                    if "£" in l:
                        prices.append(l)

                products.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "name": name,
                    "prices": " | ".join(prices)
                })
            except:
                pass

        browser.close()

    df = pd.DataFrame(products)
    df.to_csv("latest.csv", index=False)

if __name__ == "__main__":
    extract()
