from pathlib import Path

import pandas as pd


# =========================================================
# PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "review_insights.csv"
)

REPORT_DIR = PROJECT_ROOT / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_FILE = REPORT_DIR / "discovery_report.md"


# =========================================================
# LOAD DATA
# =========================================================

def load_data():

    df = pd.read_csv(INPUT_FILE)

    # Clean text columns
    for column in df.select_dtypes(include="object").columns:
        df[column] = (
            df[column]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )

    return df


# =========================================================
# BASIC SUMMARY
# =========================================================

def total_reviews(df):
    return len(df)


def count_and_percentage(df, column, exclude_unknown=False):

    data = df.copy()

    if exclude_unknown:
        data = data[
            data[column].str.lower() != "unknown"
        ]

    counts = data[column].value_counts()

    total = counts.sum()

    if total == 0:
        return pd.DataFrame(
            columns=["Count", "Percentage"]
        )

    percentages = (
        counts / total * 100
    ).round(1)

    return pd.DataFrame({
        "Count": counts,
        "Percentage": percentages,
    })


# =========================================================
# SENTIMENT
# =========================================================

def sentiment_summary(df):

    return count_and_percentage(
        df,
        "sentiment"
    )


# =========================================================
# EXPLORATION BARRIERS
# =========================================================

def exploration_barriers(df):

    return count_and_percentage(
        df,
        "exploration_barrier",
        exclude_unknown=True,
    )


# =========================================================
# DISCOVERY METHODS
# =========================================================

def discovery_methods(df):

    return count_and_percentage(
        df,
        "discovery_method",
        exclude_unknown=True,
    )


# =========================================================
# FEATURES
# =========================================================

def feature_summary(df):

    return count_and_percentage(
        df,
        "feature",
        exclude_unknown=True,
    )


# =========================================================
# CATEGORIES
# =========================================================

def category_summary(df):

    return count_and_percentage(
        df,
        "category_mentioned",
        exclude_unknown=True,
    )


# =========================================================
# PAIN POINT THEMES
# =========================================================

def classify_pain_point(text):

    text = str(text).lower()

    if text == "unknown":
        return "Unknown"

    if any(word in text for word in [
        "price",
        "expensive",
        "cost",
        "charge",
        "fee",
        "pricing",
    ]):
        return "Pricing & Fees"

    if any(word in text for word in [
        "stock",
        "unavailable",
        "availability",
        "out of stock",
    ]):
        return "Inventory & Availability"

    if any(word in text for word in [
        "delivery",
        "late",
        "delay",
        "slow",
    ]):
        return "Delivery Experience"

    if any(word in text for word in [
        "quality",
        "expired",
        "damaged",
        "fresh",
        "fake",
        "spoiled",
    ]):
        return "Product Quality & Trust"

    if any(word in text for word in [
        "refund",
        "return",
        "replacement",
        "exchange",
    ]):
        return "Returns & Refunds"

    if any(word in text for word in [
        "search",
        "find",
        "discover",
        "recommend",
        "category",
    ]):
        return "Search & Discovery"

    if any(word in text for word in [
        "city",
        "area",
        "location",
        "service not available",
    ]):
        return "Service Availability"

    if any(word in text for word in [
        "app",
        "interface",
        "checkout",
        "cart",
        "payment",
    ]):
        return "App Experience"

    return "Other"


def pain_point_summary(df):

    themes = df["pain_point"].apply(
        classify_pain_point
    )

    known = themes[
        themes != "Unknown"
    ]

    counts = known.value_counts()

    percentages = (
        counts / counts.sum() * 100
    ).round(1)

    return pd.DataFrame({
        "Count": counts,
        "Percentage": percentages,
    })


# =========================================================
# USER NEED THEMES
# =========================================================

def classify_user_need(text):

    text = str(text).lower()

    if text == "unknown":
        return "Unknown"

    if any(word in text for word in [
        "price",
        "pricing",
        "affordable",
        "cheaper",
        "lower cost",
        "competitive",
        "fee",
        "charge",
    ]):
        return "Better Pricing"

    if any(word in text for word in [
        "stock",
        "inventory",
        "availability",
        "available",
    ]):
        return "Better Availability"

    if any(word in text for word in [
        "recommend",
        "discover",
        "personalized",
        "suggestion",
        "category",
    ]):
        return "Better Discovery"

    if any(word in text for word in [
        "delivery",
        "faster",
        "fast delivery",
        "timely",
    ]):
        return "Better Delivery"

    if any(word in text for word in [
        "quality",
        "fresh",
        "authentic",
        "genuine",
    ]):
        return "Better Product Quality"

    if any(word in text for word in [
        "refund",
        "return",
        "replacement",
        "exchange",
    ]):
        return "Better Returns & Support"

    if any(word in text for word in [
        "search",
        "navigation",
        "browse",
    ]):
        return "Better Search & Navigation"

    return "Other"


def user_need_summary(df):

    themes = df["user_need"].apply(
        classify_user_need
    )

    known = themes[
        themes != "Unknown"
    ]

    counts = known.value_counts()

    percentages = (
        counts / counts.sum() * 100
    ).round(1)

    return pd.DataFrame({
        "Count": counts,
        "Percentage": percentages,
    })


# =========================================================
# CROSS ANALYSIS
# =========================================================

def barrier_by_category(df):

    filtered = df[
        (df["exploration_barrier"] != "Unknown")
        &
        (df["category_mentioned"] != "Unknown")
    ]

    return pd.crosstab(
        filtered["category_mentioned"],
        filtered["exploration_barrier"],
    )


def barrier_by_feature(df):

    filtered = df[
        df["exploration_barrier"] != "Unknown"
    ]

    return pd.crosstab(
        filtered["feature"],
        filtered["exploration_barrier"],
    )


def barrier_by_sentiment(df):

    filtered = df[
        df["exploration_barrier"] != "Unknown"
    ]

    return pd.crosstab(
        filtered["exploration_barrier"],
        filtered["sentiment"],
    )


# =========================================================
# MARKDOWN HELPERS
# =========================================================

def dataframe_to_markdown(df):

    if df.empty:
        return "No data available.\n"

    return df.to_markdown()


# =========================================================
# GENERATE REPORT
# =========================================================

def generate_report(df):

    total = total_reviews(df)

    unknown_barriers = (
        df["exploration_barrier"]
        .eq("Unknown")
        .sum()
    )

    unknown_discovery = (
        df["discovery_method"]
        .eq("Unknown")
        .sum()
    )

    unknown_categories = (
        df["category_mentioned"]
        .eq("Unknown")
        .sum()
    )

    report = []

    report.append(
        "# Blinkit AI-Powered Discovery Engine Report\n"
    )

    report.append(
        "## 1. Dataset Overview\n"
    )

    report.append(
        f"- Reviews with extracted insights: **{total:,}**"
    )

    report.append(
        f"- Reviews without an identifiable exploration barrier: "
        f"**{unknown_barriers:,} ({unknown_barriers / total * 100:.1f}%)**"
    )

    report.append(
        f"- Reviews without an identifiable discovery method: "
        f"**{unknown_discovery:,} ({unknown_discovery / total * 100:.1f}%)**"
    )

    report.append(
        f"- Reviews without an identifiable product category: "
        f"**{unknown_categories:,} ({unknown_categories / total * 100:.1f}%)**\n"
    )

    report.append(
        "Percentages in sections that exclude `Unknown` are calculated "
        "only among reviews where that signal could be identified.\n"
    )

    report.append(
        "## 2. Sentiment Distribution\n"
    )

    report.append(
        dataframe_to_markdown(
            sentiment_summary(df)
        )
    )

    report.append(
        "\n## 3. Category Exploration Barriers\n"
    )

    report.append(
        dataframe_to_markdown(
            exploration_barriers(df)
        )
    )

    report.append(
        "\n## 4. Product Discovery Methods\n"
    )

    report.append(
        dataframe_to_markdown(
            discovery_methods(df)
        )
    )

    report.append(
        "\n## 5. Recurring Pain-Point Themes\n"
    )

    report.append(
        dataframe_to_markdown(
            pain_point_summary(df)
        )
    )

    report.append(
        "\n## 6. Recurring User-Need Themes\n"
    )

    report.append(
        dataframe_to_markdown(
            user_need_summary(df)
        )
    )

    report.append(
        "\n## 7. Product Features Mentioned\n"
    )

    report.append(
        dataframe_to_markdown(
            feature_summary(df)
        )
    )

    report.append(
        "\n## 8. Categories Mentioned\n"
    )

    report.append(
        dataframe_to_markdown(
            category_summary(df)
        )
    )

    report.append(
        "\n## 9. Exploration Barrier × Category\n"
    )

    report.append(
        dataframe_to_markdown(
            barrier_by_category(df)
        )
    )

    report.append(
        "\n## 10. Exploration Barrier × Product Feature\n"
    )

    report.append(
        dataframe_to_markdown(
            barrier_by_feature(df)
        )
    )

    report.append(
        "\n## 11. Exploration Barrier × Sentiment\n"
    )

    report.append(
        dataframe_to_markdown(
            barrier_by_sentiment(df)
        )
    )

    REPORT_FILE.write_text(
        "\n".join(report),
        encoding="utf-8",
    )


# =========================================================
# MAIN
# =========================================================

def main():

    df = load_data()

    print("=" * 60)
    print("Blinkit AI Discovery Analysis")
    print("=" * 60)

    print(
        f"\nReviews analyzed: {total_reviews(df):,}"
    )

    print(
        "\nExploration Barriers "
        "(excluding Unknown)"
    )
    print(
        exploration_barriers(df)
    )

    print(
        "\nDiscovery Methods "
        "(excluding Unknown)"
    )
    print(
        discovery_methods(df)
    )

    print(
        "\nPain Point Themes "
        "(excluding Unknown)"
    )
    print(
        pain_point_summary(df)
    )

    print(
        "\nUser Need Themes "
        "(excluding Unknown)"
    )
    print(
        user_need_summary(df)
    )

    generate_report(df)

    print(
        f"\nReport saved to:\n{REPORT_FILE}"
    )


if __name__ == "__main__":
    main()