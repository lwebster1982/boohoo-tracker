from pytrends.request import TrendReq
from datetime import datetime
from pathlib import Path
import pandas as pd
import time

OUTPUT_FILE = Path("trends_market.csv")

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

ANCHOR = "ASOS"

# Google Trends allows a maximum of five terms
# in a single comparison.
#
# ASOS appears in every batch, which allows us
# to put every retailer onto a common ASOS = 100 scale.

BATCHES = [
    [
        "ASOS",
        "boohoo",
        "PrettyLittleThing",
        "boohooMAN",
        "Karen Millen",
    ],
    [
        "ASOS",
        "Next",
        "Zara",
        "H&M",
        "River Island",
    ],
    [
        "ASOS",
        "New Look",
        "Mango",
        "Marks & Spencer",
    ],
]

DISPLAY_NAMES = {
    "ASOS": "asos",
    "boohoo": "boohoo",
    "PrettyLittleThing": "plt",
    "boohooMAN": "boohooman",
    "Karen Millen": "karen_millen",
    "Next": "next",
    "Zara": "zara",
    "H&M": "hm",
    "River Island": "river_island",
    "New Look": "new_look",
    "Mango": "mango",
    "Marks & Spencer": "marks_spencer",
}


# --------------------------------------------------
# GET ONE BATCH FROM GOOGLE TRENDS
# --------------------------------------------------

def get_batch(pytrends, terms):

    pytrends.build_payload(
        kw_list=terms,
        timeframe="today 3-m",
        geo="GB",
    )

    df = pytrends.interest_over_time()

    if df.empty:
        raise RuntimeError(
            f"Google Trends returned no data for {terms}"
        )

    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])

    # Use the trailing 30 complete days.
    # This makes the relative popularity measure
    # much more stable than using a single day.

    today = datetime.utcnow().date()

    df["date"] = df.index.date

    complete = df[
        df["date"] < today
    ].copy()

    if complete.empty:
        raise RuntimeError(
            f"No complete data for {terms}"
        )

    recent = complete.tail(30)

    averages = (
        recent
        .drop(columns=["date"])
        .mean()
        .to_dict()
    )

    return averages


# --------------------------------------------------
# BUILD MARKET INDEX
# --------------------------------------------------

def get_market_index():

    pytrends = TrendReq(
        hl="en-GB",
        tz=0,
        timeout=(10, 30),
    )

    results = {}

    for batch_number, terms in enumerate(BATCHES, start=1):

        print(
            f"\nFetching Google Trends batch "
            f"{batch_number}: {terms}"
        )

        averages = get_batch(
            pytrends,
            terms
        )

        anchor_value = averages.get(
            ANCHOR,
            0
        )

        if anchor_value == 0:
            raise RuntimeError(
                f"ASOS returned zero in batch "
                f"{batch_number}"
            )

        # Normalise every retailer so ASOS = 100

        for term, value in averages.items():

            index_value = (
                value / anchor_value
            ) * 100

            column = DISPLAY_NAMES[term]

            results[column] = round(
                index_value,
                1
            )

        # Avoid hitting Google Trends too quickly

        time.sleep(5)

    # Force anchor to exactly 100

    results["asos"] = 100.0

    return results


# --------------------------------------------------
# SAVE DAILY HISTORY
# --------------------------------------------------

def save_history(results):

    today = str(
        datetime.utcnow().date()
    )

    row = {
        "date": today,
        **results,
    }

    new_row = pd.DataFrame(
        [row]
    )

    if OUTPUT_FILE.exists():

        old = pd.read_csv(
            OUTPUT_FILE
        )

        # If we run GitHub Actions twice today,
        # replace today's observation rather
        # than creating a duplicate.

        old = old[
            old["date"].astype(str) != today
        ]

        combined = pd.concat(
            [old, new_row],
            ignore_index=True
        )

    else:

        combined = new_row.copy()

    combined = combined.sort_values(
        "date"
    )

    combined.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n==============================")
    print("UK FASHION SEARCH POPULARITY")
    print("ASOS = 100")
    print("==============================")

    print(
        new_row.to_string(
            index=False
        )
    )

    return combined


# --------------------------------------------------
# CALCULATE MOMENTUM
# --------------------------------------------------

def calculate_momentum(history):

    brands = [
        column
        for column in history.columns
        if column != "date"
    ]

    latest = history.iloc[-1]

    print("\n==============================")
    print("SEARCH MOMENTUM")
    print("==============================")

    momentum_rows = []

    for brand in brands:

        current = latest[brand]

        change_7d = None
        change_30d = None

        # We need at least 8 observations
        # for a genuine 7-day comparison.

        if len(history) >= 8:

            old_7d = history.iloc[-8][brand]

            if old_7d != 0:

                change_7d = round(
                    (
                        current / old_7d
                        - 1
                    ) * 100,
                    1
                )

        # We need at least 31 observations
        # for a genuine 30-day comparison.

        if len(history) >= 31:

            old_30d = history.iloc[-31][brand]

            if old_30d != 0:

                change_30d = round(
                    (
                        current / old_30d
                        - 1
                    ) * 100,
                    1
                )

        momentum_rows.append({
            "brand": brand,
            "popularity_index": current,
            "change_7d_pct": change_7d,
            "change_30d_pct": change_30d,
        })

    momentum = pd.DataFrame(
        momentum_rows
    )

    momentum = momentum.sort_values(
        "popularity_index",
        ascending=False
    )

    momentum.to_csv(
        "trends_momentum.csv",
        index=False
    )

    print(
        momentum.to_string(
            index=False
        )
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    market = get_market_index()

    history = save_history(
        market
    )

    calculate_momentum(
        history
    )
