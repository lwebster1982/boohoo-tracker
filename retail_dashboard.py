from pathlib import Path
from datetime import datetime

import pandas as pd


README_FILE = Path("README.md")


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

    except Exception:
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
    if pd.isna(value):
        return "—"

    return f"{float(value):,.{decimals}f}"


def fmt_int(value):
    if pd.isna(value):
        return "—"

    return f"{int(round(float(value))):,}"


def change_text(current, previous, suffix=""):
    if previous is None:
        return ""

    if pd.isna(current) or pd.isna(previous):
        return ""

    change = float(current) - float(previous)

    if abs(change) < 0.05:
        return "→ unchanged"

    arrow = "↑" if change > 0 else "↓"

    return (
        f"{arrow} "
        f"{abs(change):.1f}{suffix} vs previous day"
    )


def pct_change_text(current, previous):
    if previous is None:
        return ""

    if (
        pd.isna(current)
        or pd.isna(previous)
        or float(previous) == 0
    ):
        return ""

    change = (
        float(current) / float(previous) - 1
    ) * 100

    if abs(change) < 0.1:
        return "→ unchanged"

    arrow = "↑" if change > 0 else "↓"

    return (
        f"{arrow} "
        f"{abs(change):.1f}% vs previous day"
    )


# ============================================================
# RETAIL DISCOUNT SECTION
# ============================================================

def brand_discount_block(
    display_name,
    summary_file
):
    latest = latest_row(summary_file)
    previous = previous_row(summary_file)

    if latest is None:
        return []

    prev_discounted = None
    prev_avg = None
    prev_median = None

    if previous is not None:
        prev_discounted = previous.get(
            "pct_assortment_discounted"
        )

        prev_avg = previous.get(
            "average_discount_pct"
        )

        prev_median = previous.get(
            "median_discount_pct"
        )

    lines = []

    lines.append(
        f"### {display_name}"
    )

    lines.append("")

    lines.append(
        f"**Assortment:** "
        f"{fmt_int(latest.get('products_captured'))} products"
    )

    lines.append("")

    markdown_rate = latest.get(
        "pct_assortment_discounted"
    )

    movement = change_text(
        markdown_rate,
        prev_discounted,
        "pp"
    )

    line = (
        f"**On markdown:** "
        f"{fmt_number(markdown_rate)}%"
    )

    if movement:
        line += f" · {movement}"

    lines.append(line)
    lines.append("")

    avg_discount = latest.get(
        "average_discount_pct"
    )

    avg_move = change_text(
        avg_discount,
        prev_avg,
        "pp"
    )

    line = (
        f"**Average markdown:** "
        f"{fmt_number(avg_discount)}%"
    )

    if avg_move:
        line += f" · {avg_move}"

    lines.append(line)
    lines.append("")

    median_discount = latest.get(
        "median_discount_pct"
    )

    median_move = change_text(
        median_discount,
        prev_median,
        "pp"
    )

    line = (
        f"**Median markdown:** "
        f"{fmt_number(median_discount)}%"
    )

    if median_move:
        line += f" · {median_move}"

    lines.append(line)
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
# GOOGLE TRENDS SECTION
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

        value = latest.get(column)

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
        key=lambda x: x[1],
        reverse=True
    )

    lines = []

    lines.append(
        "## 🔎 UK Search Popularity"
    )

    lines.append("")

    lines.append(
        "_Relative Google search interest, "
        "normalised to ASOS = 100._"
    )

    lines.append("")

    for name, value in rows:

        lines.append(
            f"**{name}: {value:.1f}**"
        )

        lines.append("")

    return lines


def trends_momentum_block():
    df = read_csv_safe(
        "trends_momentum.csv"
    )

    if df is None:
        return []

    useful = []

    for _, row in df.iterrows():

        brand = row.get("brand")

        if brand not in TREND_NAMES:
            continue

        change_7d = row.get(
            "change_7d_pct"
        )

        change_30d = row.get(
            "change_30d_pct"
        )

        if (
            pd.isna(change_7d)
            and pd.isna(change_30d)
        ):
            continue

        useful.append(
            (
                TREND_NAMES[brand],
                change_7d,
                change_30d
            )
        )

    if not useful:
        return []

    lines = []

    lines.append(
        "## 📈 Search Momentum"
    )

    lines.append("")

    for name, change_7d, change_30d in useful:

        parts = []

        if not pd.isna(change_7d):

            arrow = (
                "↑"
                if change_7d > 0
                else "↓"
                if change_7d < 0
                else "→"
            )

            parts.append(
                f"7d {arrow} "
                f"{abs(change_7d):.1f}%"
            )

        if not pd.isna(change_30d):

            arrow = (
                "↑"
                if change_30d > 0
                else "↓"
                if change_30d < 0
                else "→"
            )

            parts.append(
                f"30d {arrow} "
                f"{abs(change_30d):.1f}%"
            )

        lines.append(
            f"**{name}** · "
            + " · ".join(parts)
        )

        lines.append("")

    return lines


# ============================================================
# KEY DAILY SIGNALS
# ============================================================

def build_signals():
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

        latest = latest_row(filename)
        previous = previous_row(filename)

        if latest is None or previous is None:
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
                f"**{brand}:** markdown breadth "
                f"{direction} by "
                f"{abs(markdown_change):.1f}pp."
            )

        if abs(median_change) >= 5:

            direction = (
                "deepened"
                if median_change > 0
                else "eased"
            )

            signals.append(
                f"**{brand}:** median markdown "
                f"{direction} by "
                f"{abs(median_change):.1f}pp."
            )

    # Trends signals

    trends = read_csv_safe(
        "trends_momentum.csv"
    )

    if trends is not None:

        for _, row in trends.iterrows():

            brand = row.get("brand")

            if brand not in [
                "boohoo",
                "plt",
                "boohooman",
                "karen_millen",
            ]:
                continue

            change = row.get(
                "change_7d_pct"
            )

            if pd.isna(change):
                continue

            if abs(float(change)) >= 10:

                arrow = (
                    "increased"
                    if change > 0
                    else "decreased"
                )

                signals.append(
                    f"**{TREND_NAMES[brand]}:** "
                    f"7-day search interest "
                    f"{arrow} "
                    f"{abs(float(change)):.1f}%."
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
        "_Daily read-through on promotional intensity "
        "and consumer search interest._"
    )

    # --------------------------------------------------------
    # IMPORTANT CHANGES
    # --------------------------------------------------------

    signals = build_signals()

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

    # --------------------------------------------------------
    # DISCOUNTING
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # TRENDS
    # --------------------------------------------------------

    lines.append("---")
    lines.append("")

    lines.extend(
        trends_market_block()
    )

    momentum = trends_momentum_block()

    if momentum:

        lines.append("---")
        lines.append("")
        lines.extend(
            momentum
        )

    # --------------------------------------------------------
    # LINKS TO RAW DATA
    # --------------------------------------------------------

    lines.append("---")
    lines.append("")

    lines.append(
        "## 📂 Data"
    )

    lines.append("")

    lines.append(
        "- [Boohoo daily summary](summary.csv)"
    )

    lines.append(
        "- [PLT daily summary](plt_summary.csv)"
    )

    lines.append(
        "- [BoohooMAN daily summary](boohooman_summary.csv)"
    )

    lines.append(
        "- [Search popularity](trends_market.csv)"
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
