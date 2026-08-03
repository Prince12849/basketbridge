from pathlib import Path
import pandas as pd

# --------------------------------------------------
# Paths
# --------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CLEANED_DIR = PROJECT_ROOT / "data" / "cleaned"
OUTPUT_FILE = CLEANED_DIR / "merged_reviews.csv"

# --------------------------------------------------
# Files to merge
# filename : source_name
# --------------------------------------------------
FILES = {
    "blinkit_playstore_reviews_clean.csv": "playstore",
    "blinkit_playstore_clean.csv": "playstore",
    "blinkit_appstore_reviews_clean.csv": "appstore",
    "blinkit_reddit_clean.csv": "reddit",
    "blinkit_youtube_comments_clean.csv": "youtube",
    "trustpilot_reviews_clean.csv": "trustpilot",
}

# --------------------------------------------------
# Possible column mappings
# --------------------------------------------------
COLUMN_MAPPING = {
    # Review text
    "content": "review_text",
    "review": "review_text",
    "text": "review_text",
    "body": "review_text",
    "comment": "review_text",
    "raw_text": "review_text",

    # Rating
    "score": "rating",
    "rating": "rating",

    # Date
    "at": "date",
    "created_at": "date",
    "date": "date",
    "published_at": "date",

    # User
    "userName": "user_name",
    "username": "user_name",
    "author": "user_name",

    # Helpful count
    "thumbsUpCount": "helpful_votes",
    "likes": "helpful_votes",
    "upvotes": "helpful_votes",
}


def standardize_columns(df):
    rename_dict = {}

    for col in df.columns:
        if col in COLUMN_MAPPING:
            rename_dict[col] = COLUMN_MAPPING[col]

    df = df.rename(columns=rename_dict)

    return df


def create_missing_columns(df):
    required = [
        "review_text",
        "rating",
        "date",
        "user_name",
        "helpful_votes",
    ]

    for col in required:
        if col not in df.columns:
            df[col] = None

    return df


def load_file(file_name, source):
    path = CLEANED_DIR / file_name

    if not path.exists():
        print(f"⚠ Skipping {file_name} (not found)")
        return None

    print(f"Loading {file_name}")

    df = pd.read_csv(path)

    df = standardize_columns(df)
    df = create_missing_columns(df)

    df["source"] = source

    return df[
        [
            "review_text",
            "rating",
            "date",
            "user_name",
            "helpful_votes",
            "source",
        ]
    ]


def main():
    merged = []

    for file_name, source in FILES.items():
        df = load_file(file_name, source)

        if df is not None:
            merged.append(df)

    if len(merged) == 0:
        print("No files found.")
        return

    final_df = pd.concat(merged, ignore_index=True)

    # Remove blank reviews
    final_df = final_df.dropna(subset=["review_text"])
    final_df = final_df[
        final_df["review_text"].astype(str).str.strip() != ""
    ]

    # Create unique review ids
    final_df.insert(
        0,
        "review_id",
        range(1, len(final_df) + 1)
    )

    final_df.to_csv(OUTPUT_FILE, index=False)

    print("\n===================================")
    print("Merge Complete")
    print("===================================")
    print(f"Total Reviews : {len(final_df):,}")
    print(f"Sources       : {final_df['source'].nunique()}")
    print(f"Saved To      : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()