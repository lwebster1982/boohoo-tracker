from pathlib import Path
from datetime import datetime

import pandas as pd


README_FILE = Path("README.md")


# ============================================================
# DISPLAY NAMES
# ============================================================

TREND_NAMES = {
    "asos": "ASOS",
    "boohoo": "Boohoo",
    "plt": "PrettyLittleThing",
    "boohooman": "BoohooMAN",
    "karen_millen": "Karen Millen",
    "next": "Next",
    "zara": "Zara",
    "hm": "H&M",
    "river_island": "River Island",
    "new_look": "New Look",
    "mango": "Mango",
    "marks_spencer": "M&S",
}

FOCUS_TRENDS = [
    "boohoo",
    "plt",
    "boohooman",
    "karen_millen",
]


# ============================================================
# HELPERS
# ============================================================

def read_csv_safe(filename):
    path = Path(filename)

    if not path.exists():
        return None

    try:
        df = pd.read_csv(path)

        if df.empty:
            return None

        return df

    except Exception as error:
        print(
            f"Could not read {filename}: {error}"
        )
        return None


def latest_row(filename):
    df = read_csv_safe(filename)

    if df is None:
        return None

    return df.iloc[-1]


def previous_row(filename):
    df = read_csv_safe(filename)

    if df is None or len(df) < 2:
        return None

    return df.iloc[-2]


def fmt_number(value, decimals=1):
    if value is None or pd.isna(value):
        return "—"

    return f"{float(value):,.{decimals}f}"


def fmt_int(value):
    if value is None or pd.isna(value):
        return "—"

    return f"{int(round(float(value))):,}"


def change_text(current, previous, suffix="pp"):
    if previous is None:
        return ""

    if (
        current is None
        or pd.isna(current)
        or pd.isna(previous)
    ):
        return ""

    change = (
        float(current)
        - float(previous)
    )

    if abs(change) < 0.05:
        return "→ unchanged"

    arrow = "↑" if change > 0 else "↓"

    return (
        f"{arrow} "
        f"{abs(change):.1f}{suffix}"
    )


# ============================================================
# DISCOUNTING
# ============================================================

def brand_discount_block(
    display_name,
    summary_file
):
    latest = latest_row(
        summary_file
    )

    previous = previous_row(
        summary_file
    )

    if latest is None:
        return []

    lines = []

    lines.append(
        f"### {display_name}"
    )

    lines.append("")

    products = latest.get(
        "products_captured"
    )

    lines.append(
        f"**Assortment:** "
        f"{fmt_int(products)} products"
    )

    lines.append("")

    markdown_rate = latest.get(
        "pct_assortment_discounted"
    )

    previous_markdown = (
        previous.get(
            "pct_assortment_discounted"
        )
        if previous is not None
        else None
    )

    movement = change_text(
        markdown_rate,
        previous_markdown
    )

    markdown_line = (
        f"**On markdown:** "
        f"{fmt_number(markdown_rate)}%"
    )

    if movement:
        markdown_line += (
            f" · {movement} vs prior day"
        )

    lines.append(
        markdown_line
    )

    lines.append("")

    average = latest.get(
        "average_discount_pct"
    )

    previous_average = (
        previous.get(
            "average_discount_pct"
        )
        if previous is not None
        else None
    )

    movement = change_text(
        average,
        previous_average
    )

    average_line = (
        f"**Average markdown:** "
        f"{fmt_number(average)}%"
    )

    if movement:
        average_line += (
            f" · {movement} vs prior day"
        )

    lines.append(
        average_line
    )

    lines.append("")

    median = latest.get(
        "median_discount_pct"
    )

    previous_median = (
        previous.get(
            "median_discount_pct"
        )
        if previous is not None
        else None
    )

    movement = change_text(
        median,
        previous_median
    )

    median_line = (
        f"**Median markdown:** "
        f"{fmt_number(median)}%"
    )

    if movement:
        median_line += (
            f" · {movement} vs prior day"
        )

    lines.append(
        median_line
    )

    lines.append("")

    lines.append(
        f"**≥30% off:** "
        f"{fmt_int(latest.get('discounted_30pct_plus'))}"
        f" · "
        f"**≥50% off:** "
        f"{fmt_int(latest.get('discounted_50pct_plus'))}"
    )

    lines.append("")

    return lines


# ============================================================
# MATERIAL DAILY CHANGES
# ============================================================

def build_discount_signals():
    signals = []

    brands = [
        (
            "Boohoo",
            "summary.csv"
        ),
        (
            "PrettyLittleThing",
            "plt_summary.csv"
        ),
        (
            "BoohooMAN",
            "boohooman_summary.csv"
        ),
    ]

    for brand, filename in brands:

        latest = latest_row(
            filename
        )

        previous = previous_row(
            filename
        )

        if (
            latest is None
            or previous is None
        ):
            continue

        markdown_change = (
            float(
                latest.get(
                    "pct_assortment_discounted",
                    0
                )
            )
            -
            float(
                previous.get(
                    "pct_assortment_discounted",
                    0
                )
            )
        )

        median_change = (
            float(
                latest.get(
                    "median_discount_pct",
                    0
                )
            )
            -
            float(
                previous.get(
                    "median_discount_pct",
                    0
                )
            )
        )

        if abs(markdown_change) >= 2:

            direction = (
                "increased"
                if markdown_change > 0
                else "decreased"
            )

            signals.append(
                f"**{brand}:** "
                f"markdown breadth {direction} "
                f"by {abs(markdown_change):.1f}pp."
            )

        if abs(median_change) >= 5:

            direction = (
                "deepened"
                if median_change > 0
                else "eased"
            )

            signals.append(
                f"**{brand}:** "
                f"median markdown {direction} "
                f"by {abs(median_change):.1f}pp."
            )

    return signals


# ============================================================
# GOOGLE TRENDS MARKET POPULARITY
# ============================================================

def trends_market_block():
    df = read_csv_safe(
        "trends_market.csv"
    )

    if df is None:
        return []

    latest = df.iloc[-1]

    rows = []

    for column in df.columns:

        if column == "date":
            continue

        value = latest.get(
            column
        )

        if pd.isna(value):
            continue

        rows.append(
            (
                TREND_NAMES.get(
                    column,
                    column
                ),
                float(value)
            )
        )

    rows.sort(
        key=lambda item: item[1],
        reverse=True
    )

    lines = []

    lines.append(
        "## 🔎 UK Search Popularity"
    )

    lines.append("")

    lines.append(
        "_Trailing 30-day Google search "
        "interest, normalised to ASOS = 100._"
    )

    lines.append("")

    lines.append(
        "| Brand | Search index |"
    )

    lines.append(
        "|---|---:|"
    )

    for name, value in rows:

        lines.append(
            f"| **{name}** | {value:.1f} |"
        )

    lines.append("")

    return lines


# ============================================================
# GOOGLE TRENDS MOMENTUM
# ============================================================

def trends_momentum_block():
    df = read_csv_safe(
        "trends_momentum.csv"
    )

    if df is None:
        return []

    lines = []

    lines.append(
        "## 📈 Brand Search Momentum"
    )

    lines.append("")

    lines.append(
        "_Momentum is shown only for "
        "Boohoo, PLT, BoohooMAN and Karen Millen._"
    )

    lines.append("")

    found_any = False

    for brand in FOCUS_TRENDS:

        match = df[
            df["brand"] == brand
        ]

        if match.empty:
            continue

        row = match.iloc[0]

        name = TREND_NAMES[
            brand
        ]

        popularity = row.get(
            "popularity_index"
        )

        change_7d = row.get(
            "change_7d_pct"
        )

        change_30d = row.get(
            "change_30d_pct"
        )

        lines.append(
            f"### {name}"
        )

        lines.append("")

        lines.append(
            f"**Current search index:** "
            f"{fmt_number(popularity)}"
        )

        lines.append("")

        if pd.isna(change_7d):

            lines.append(
                "**7-day momentum:** "
                "Not enough history yet"
            )

        else:

            arrow = (
                "↑"
                if change_7d > 0
                else "↓"
                if change_7d < 0
                else "→"
            )

            lines.append(
                f"**7-day momentum:** "
                f"{arrow} "
                f"{abs(float(change_7d)):.1f}%"
            )

        lines.append("")

        if pd.isna(change_30d):

            lines.append(
                "**30-day momentum:** "
                "Not enough history yet"
            )

        else:

            arrow = (
                "↑"
                if change_30d > 0
                else "↓"
                if change_30d < 0
                else "→"
            )

            lines.append(
                f"**30-day momentum:** "
                f"{arrow} "
                f"{abs(float(change_30d)):.1f}%"
            )

        lines.append("")

        found_any = True

    if not found_any:

        lines.append(
            "Not enough trend history yet."
        )

        lines.append("")

    return lines


# ============================================================
# TREND ALERTS
# ============================================================

def build_trend_signals():
    signals = []

    df = read_csv_safe(
        "trends_momentum.csv"
    )

    if df is None:
        return signals

    for brand in FOCUS_TRENDS:

        match = df[
            df["brand"] == brand
        ]

        if match.empty:
            continue

        row = match.iloc[0]

        change = row.get(
            "change_7d_pct"
        )

        if pd.isna(change):
            continue

        change = float(
            change
        )

        # Only flag genuinely noticeable
        # short-term movements.

        if abs(change) >= 10:

            direction = (
                "increased"
                if change > 0
                else "decreased"
            )

            signals.append(
                f"**{TREND_NAMES[brand]}:** "
                f"7-day search interest "
                f"{direction} by "
                f"{abs(change):.1f}%."
            )

    return signals


# ============================================================
# BUILD README
# ============================================================

def main():

    today = datetime.now().strftime(
        "%d %B %Y"
    )

    lines = []

    lines.append(
        "# Retail Trading Monitor"
    )

    lines.append("")

    lines.append(
        f"**{today}**"
    )

    lines.append("")

    lines.append(
        "_Daily read-through on promotional "
        "intensity and UK consumer search interest._"
    )

    # ========================================================
    # CHANGES WORTH NOTICING
    # ========================================================

    signals = (
        build_discount_signals()
        +
        build_trend_signals()
    )

    if signals:

        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append(
            "## 🚨 Changes Worth Noticing"
        )

        lines.append("")

        for signal in signals:

            lines.append(
                f"- {signal}"
            )

    # ========================================================
    # PROMOTIONAL INTENSITY
    # ========================================================

    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append(
        "## 🏷️ Promotional Intensity"
    )

    lines.append("")

    for display_name, filename in [
        (
            "Boohoo",
            "summary.csv"
        ),
        (
            "PrettyLittleThing",
            "plt_summary.csv"
        ),
        (
            "BoohooMAN",
            "boohooman_summary.csv"
        ),
    ]:

        lines.extend(
            brand_discount_block(
                display_name,
                filename
            )
        )

    # ========================================================
    # SEARCH POPULARITY
    # ========================================================

    lines.append("---")
    lines.append("")

    lines.extend(
        trends_market_block()
    )

    # ========================================================
    # SEARCH MOMENTUM
    # ========================================================

    lines.append("---")
    lines.append("")

    lines.extend(
        trends_momentum_block()
    )

    # ========================================================
    # RAW DATA
    # ========================================================

    lines.append("---")
    lines.append("")

    lines.append(
        "## 📂 Raw Data"
    )

    lines.append("")

    lines.append(
        "- [Boohoo summary](summary.csv)"
    )

    lines.append(
        "- [PLT summary](plt_summary.csv)"
    )

    lines.append(
        "- [BoohooMAN summary](boohooman_summary.csv)"
    )

    lines.append(
        "- [UK search popularity](trends_market.csv)"
    )

    lines.append(
        "- [Search momentum](trends_momentum.csv)"
    )

    lines.append("")

    lines.append(
        "_Updated automatically by GitHub Actions._"
    )

    README_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print(
        "Retail mobile dashboard created."
    )


if __name__ == "__main__":
    main()
