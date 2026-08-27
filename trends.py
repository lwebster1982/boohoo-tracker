from pytrends.request import TrendReq
from datetime import datetime
from pathlib import Path
import pandas as pd
import time

OUTPUT_FILE = Path("trends_history.csv")

# Keep all brands in ONE request.
# This is important because it puts them on the same 0-100 scale.
TERMS = [
    "boohoo",
    "PrettyLittleThing",
    "boohooMAN",
    "Karen Millen",
]

COLUMN_NAMES = {
    "boohoo": "boohoo",
    "PrettyLittleThing": "plt",
    "boohooMAN": "boohooman",
    "Karen Millen": "karen_millen",
}


def get_google_trends():
    pytrends = TrendReq(
        hl="en-GB",
        tz=0,
        timeout=(10, 30),
        retries=2,
        backoff_factor=0.5,
    )

    # Last 7 days gives hourly/recent data and provides
    # a much better daily momentum signal than a long history.
    pytrends.build_payload(
        kw_list=TERMS,
        timeframe="now 7-d",
        geo="GB",
    )

    df = pytrends.interest_over_time()

    if df.empty:
        raise RuntimeError("Google Trends returned no data")

    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])

    df = df.rename(columns=COLUMN_NAMES)

    # Average the latest complete day's observations.
    df["date"] = df.index.date

    today = datetime.utcnow().date()

    complete = df[df["date"] < today]

    if complete.empty:
        raise RuntimeError("No complete Google Trends day available")

    latest_date = complete["date"].max()

    latest = (
        complete[complete["date"] == latest_date]
        .drop(columns=["date"])
        .mean()
        .round(1)
        .to_dict()
    )

    return {
        "date": str(latest_date),
        **latest,
    }


def save_history(row):
    new_row = pd.DataFrame([row])

    if OUTPUT_FILE.exists():
        old = pd.read_csv(OUTPUT_FILE)

        # Remove existing observation for the same day
        # so rerunning GitHub Actions doesn't duplicate it.
        old = old[old["date"].astype(str) != str(row["date"])]

        combined = pd.concat([old, new_row], ignore_index=True)
    else:
        combined = new_row

    combined = combined.sort_values("date")
    combined.to_csv(OUTPUT_FILE, index=False)

    print("\nGoogle Trends:")
    print(new_row.to_string(index=False))


if __name__ == "__main__":
    result = get_google_trends()
    save_history(result)
