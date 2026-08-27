from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError
from datetime import datetime
from pathlib import Path
import pandas as pd
import time
import random


OUTPUT_FILE = Path("trends_market.csv")
MOMENTUM_FILE = Path("trends_momentum.csv")


# ============================================================
# SETTINGS
# ============================================================

ANCHOR = "ASOS"

# Google Trends allows a maximum of five terms per comparison.
# ASOS appears in every batch so all retailers can be put
# onto the same ASOS = 100 scale.

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


# Number of attempts for each Google Trends batch
MAX_RETRIES = 4

# Wait between successful batches.
# The random element makes the requests look less mechanical.
MIN_BATCH_WAIT = 20
MAX_BATCH_WAIT = 35


# ============================================================
# CREATE GOOGLE TRENDS CONNECTION
# ============================================================

def create_pytrends():

    return TrendReq(
        hl="en-GB",
        tz=0,
        timeout=(10, 30),
    )


# ============================================================
# GET ONE BATCH WITH RETRIES
# ============================================================

def get_batch(terms):

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            print(
                f"Attempt {attempt}/{MAX_RETRIES} "
                f"for {terms}"
            )

            # Create a fresh connection for each attempt.
            pytrends = create_pytrends()

            pytrends.build_payload(
                kw_list=terms,
                timeframe="today 3-m",
                geo="GB",
            )

            df = (
                pytrends
                .interest_over_time()
            )

            if df.empty:
                raise RuntimeError(
                    f"Google Trends returned no data "
                    f"for {terms}"
                )

            if "isPartial" in df.columns:
                df = df.drop(
                    columns=["isPartial"]
                )

            # -----------------------------------------------
            # USE TRAILING 30 COMPLETE OBSERVATIONS
            # -----------------------------------------------

            today = (
                datetime.utcnow()
                .date()
            )

            df["date"] = (
                df.index.date
            )

            complete = df[
                df["date"] < today
            ].copy()

            if complete.empty:
                raise RuntimeError(
                    f"No complete Google Trends "
                    f"data for {terms}"
                )

            recent = (
                complete
                .tail(30)
            )

            averages = (
                recent
                .drop(columns=["date"])
                .mean()
                .to_dict()
            )

            print(
                "Google Trends batch succeeded."
            )

            return averages

        except TooManyRequestsError:

            print(
                "Google returned 429 "
                "(Too Many Requests)."
            )

            if attempt >= MAX_RETRIES:
                raise

            # Increasing waits:
            # roughly 45 sec, 90 sec, 180 sec

            base_waits = {
                1: 45,
                2: 90,
                3: 180,
            }

            wait = (
                base_waits.get(
                    attempt,
                    180
                )
                + random.randint(
                    5,
                    20
                )
            )

            print(
                f"Waiting {wait} seconds "
                "before trying again..."
            )

            time.sleep(
                wait
            )

        except Exception as error:

            print(
                f"Google Trends error: {error}"
            )

            if attempt >= MAX_RETRIES:
                raise

            wait = (
                30 * attempt
                + random.randint(
                    5,
                    15
                )
            )

            print(
                f"Waiting {wait} seconds "
                "before retrying..."
            )

            time.sleep(
                wait
            )

    raise RuntimeError(
        f"Could not retrieve Google Trends "
        f"for {terms}"
    )


# ============================================================
# BUILD MARKET INDEX
# ============================================================

def get_market_index():

    results = {}

    for batch_number, terms in enumerate(
        BATCHES,
        start=1
    ):

        print("\n")
        print("=" * 60)

        print(
            f"Fetching Google Trends batch "
            f"{batch_number}/{len(BATCHES)}"
        )

        print(
            terms
        )

        print("=" * 60)

        averages = get_batch(
            terms
        )

        anchor_value = (
            averages.get(
                ANCHOR,
                0
            )
        )

        if anchor_value == 0:

            raise RuntimeError(
                f"ASOS returned zero in "
                f"batch {batch_number}"
            )

        # -----------------------------------------------
        # NORMALISE EVERYTHING TO ASOS = 100
        # -----------------------------------------------

        for term, value in averages.items():

            index_value = (
                value
                / anchor_value
                * 100
            )

            column = (
                DISPLAY_NAMES[
                    term
                ]
            )

            results[
                column
            ] = round(
                index_value,
                1
            )

        # -----------------------------------------------
        # PAUSE BEFORE NEXT GOOGLE REQUEST
        # -----------------------------------------------

        if batch_number < len(
            BATCHES
        ):

            wait = random.randint(
                MIN_BATCH_WAIT,
                MAX_BATCH_WAIT
            )

            print(
                f"\nWaiting {wait} seconds "
                "before next batch..."
            )

            time.sleep(
                wait
            )

    # Force anchor to exactly 100

    results["asos"] = 100.0

    return results


# ============================================================
# SAVE DAILY HISTORY
# ============================================================

def save_history(results):

    today = str(
        datetime.utcnow()
        .date()
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

        # Replace today's observation if the
        # workflow is run more than once.

        old = old[
            old["date"].astype(str)
            != today
        ]

        combined = pd.concat(
            [
                old,
                new_row
            ],
            ignore_index=True
        )

    else:

        combined = (
            new_row.copy()
        )

    combined = (
        combined
        .sort_values(
            "date"
        )
    )

    combined.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\n")
    print("=" * 60)
    print("UK FASHION SEARCH POPULARITY")
    print("ASOS = 100")
    print("=" * 60)

    print(
        new_row.to_string(
            index=False
        )
    )

    return combined


# ============================================================
# CALCULATE MOMENTUM
# ============================================================

def calculate_momentum(history):

    brands = [
        column
        for column
        in history.columns
        if column != "date"
    ]

    latest = (
        history.iloc[-1]
    )

    print("\n")
    print("=" * 60)
    print("SEARCH MOMENTUM")
    print("=" * 60)

    momentum_rows = []

    for brand in brands:

        current = (
            latest[brand]
        )

        change_7d = None
        change_30d = None

        # -----------------------------------------------
        # 7-DAY CHANGE
        # -----------------------------------------------

        if len(history) >= 8:

            old_7d = (
                history
                .iloc[-8][brand]
            )

            if (
                pd.notna(old_7d)
                and old_7d != 0
                and pd.notna(current)
            ):

                change_7d = round(
                    (
                        current
                        / old_7d
                        - 1
                    )
                    * 100,
                    1
                )

        # -----------------------------------------------
        # 30-DAY CHANGE
        # -----------------------------------------------

        if len(history) >= 31:

            old_30d = (
                history
                .iloc[-31][brand]
            )

            if (
                pd.notna(old_30d)
                and old_30d != 0
                and pd.notna(current)
            ):

                change_30d = round(
                    (
                        current
                        / old_30d
                        - 1
                    )
                    * 100,
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

    momentum = (
        momentum
        .sort_values(
            "popularity_index",
            ascending=False
        )
    )

    momentum.to_csv(
        MOMENTUM_FILE,
        index=False
    )

    print(
        momentum.to_string(
            index=False
        )
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    market = (
        get_market_index()
    )

    history = (
        save_history(
            market
        )
    )

    calculate_momentum(
        history
    )
