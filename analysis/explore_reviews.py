import os
import pandas as pd

CLEAN_DIR = "data/cleaned"

REVIEW_COLUMNS = ["content", "review", "raw_text", "text", "comment", "body"]
RATING_COLUMNS = ["score", "rating", "stars"]
HELPFUL_COLUMNS = ["thumbsUpCount", "likes", "helpful"]


for file in os.listdir(CLEAN_DIR):

    if not file.endswith(".csv"):
        continue

    print("\n" + "=" * 70)
    print(file)
    print("=" * 70)

    df = pd.read_csv(os.path.join(CLEAN_DIR, file))

    review_col = next((c for c in REVIEW_COLUMNS if c in df.columns), None)
    rating_col = next((c for c in RATING_COLUMNS if c in df.columns), None)
    helpful_col = next((c for c in HELPFUL_COLUMNS if c in df.columns), None)

    print(f"\nTotal Reviews: {len(df)}")

    if rating_col:
        print("\nRating Distribution:")
        print(df[rating_col].value_counts().sort_index())

    if review_col:

        df["review_length"] = df[review_col].astype(str).str.len()

        print("\nLongest Reviews:")
        cols = [review_col, "review_length"]

        if rating_col:
            cols.insert(0, rating_col)

        print(
            df.sort_values("review_length", ascending=False)[cols].head(10)
        )

    if helpful_col and review_col:

        cols = [review_col, helpful_col]

        if rating_col:
            cols.insert(0, rating_col)

        print("\nTop Helpful Reviews:")
        print(
            df.sort_values(helpful_col, ascending=False)[cols].head(10)
        )