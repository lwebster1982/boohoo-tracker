from playwright.sync_api import sync_playwright
import pandas as pd
from datetime import datetime
import re
import os

BASE_URL = "https://www.boohoo.com/categories/womens-dresses"
MAX_PAGES = 120

ATTRIBUTE_LABELS = [
    "Body fit:", "Design:", "Detail:", "Fabric:", "Length:",
    "Neckline:", "Occasion:", "Sleeve length:", "Style:"
]


def clean_name(text):
    text = " ".join(text.split())

    # Remove sorting/navigation text
    for marker in [
        "Relevance ",
        "Best Sellers ",
        "Newness ",
        "Load More "
    ]:
        if text.startswith(marker):
            text = text[len(marker):]

    # Remove product attributes
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

    if "boohoo" in n[:30]:
        return "boohoo"
    if n.startswith("nastygal"):
        return "NastyGal"
    if n.startswith("misspap"):
        return "MissPap"
    if n.startswith("debenhams"):
        return "Debenhams"

    return "Other"


def extract_page(page, page_number, today):

    url = f"{BASE_URL}?page={page_number}"

    print(f"\nLoading page {page_number}: {url}")

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=120000
    )

    page.wait_for_timeout(3000)

    # Scroll once to make sure product cards render
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1500)

    text = " ".join(
        page.locator("body").inner_text().split()
    )

    price_pattern = re.compile(
        r"£(\d+(?:\.\d{1,2})?)"
        r"(?:\s*£(\d+(?:\.\d{1,2})?)\s*-(\d+)%)?"
    )

    matches = list(price_pattern.finditer(text))

    print(f"Found {len(matches)} price blocks")

    products = []
    previous_end = 0

    for match in matches:

        block = text[
            previous_end:match.start()
        ].strip()

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
                "discounted": discounted,
                "page": page_number
            })

        previous_end = match.end()

    return products


def main():

    today = datetime.now().strftime("%Y-%m-%d")

    all_products = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36"
            )
        )

        previous_names = None

        for page_number in range(1, MAX_PAGES + 1):

            try:

                products = extract_page(
                    page,
                    page_number,
                    today
                )

            except Exception as e:

                print(
                    f"ERROR on page {page_number}: {e}"
                )

                break

            if not products:

                print(
                    f"No products on page {page_number}. Stopping."
                )

                break

            current_names = set(
                product["product"]
                for product in products
            )

            # If Boohoo ignores ?page= and keeps returning
            # the same products, stop rather than creating
            # thousands of duplicates.
            if current_names == previous_names:

                print(
                    f"Page {page_number} duplicates previous page."
                )

                print(
                    "Boohoo is ignoring the page parameter."
                )

                break

            previous_names = current_names

            all_products.extend(products)

            print(
                f"Running total: {len(all_products)}"
            )

        browser.close()

    df = pd.DataFrame(all_products)

    if df.empty:

        print("NO PRODUCTS CAPTURED")
        return

    # Remove duplicate products
    df = df.drop_duplicates(
        subset=[
            "product",
            "current_price",
            "original_price"
        ]
    )

    df.to_csv(
        "latest.csv",
        index=False
    )

    # -------------------------
    # HISTORICAL DATABASE
    # -------------------------

    if os.path.exists("history.csv"):

        old = pd.read_csv("history.csv")

        # Replace today's run if we test more than once
        old = old[
            old["date"].astype(str) != today
        ]

        history = pd.concat(
            [old, df],
            ignore_index=True
        )

    else:

        history = df.copy()

    history.to_csv(
        "history.csv",
        index=False
    )

    # -------------------------
    # DAILY SUMMARY
    # -------------------------

    discounted = df[
        df["discounted"] == True
    ]

    summary = pd.DataFrame([{

        "date": today,

        "products_captured":
            len(df),

        "products_discounted":
            len(discounted),

        "pct_assortment_discounted":
            round(
                len(discounted)
                / len(df)
                * 100,
                1
            ),

        "average_discount_pct":
            round(
                discounted[
                    "discount_pct"
                ].mean(),
                1
            )
            if len(discounted)
            else 0,

        "median_discount_pct":
            round(
                discounted[
                    "discount_pct"
                ].median(),
                1
            )
            if len(discounted)
            else 0,

        "discounted_30pct_plus":
            int(
                (
                    df["discount_pct"] >= 30
                ).sum()
            ),

        "discounted_50pct_plus":
            int(
                (
                    df["discount_pct"] >= 50
                ).sum()
            )

    }])

    summary.to_csv(
        "summary.csv",
        index=False
    )

    print("\n======================")
    print("DAILY SUMMARY")
    print("======================")

    print(
        summary.to_string(index=False)
    )

    print(
        f"\nTOTAL UNIQUE PRODUCTS: {len(df)}"
    )


if __name__ == "__main__":
    main()
