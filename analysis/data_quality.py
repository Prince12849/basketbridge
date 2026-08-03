import os
import pandas as pd

RAW_DIR = "data/raw"

REVIEW_COLUMNS = ["content", "review", "raw_text", "text", "comment", "body"]
RATING_COLUMNS = ["score", "rating", "stars"]
DATE_COLUMNS = ["at", "date", "created_at", "review_date"]


for file in os.listdir(RAW_DIR):

    if not file.endswith(".csv"):
        continue

    print("\n" + "=" * 70)
    print(file)
    print("=" * 70)

    df = pd.read_csv(os.path.join(RAW_DIR, file))

    review_col = next((c for c in REVIEW_COLUMNS if c in df.columns), None)
    rating_col = next((c for c in RATING_COLUMNS if c in df.columns), None)
    date_col = next((c for c in DATE_COLUMNS if c in df.columns), None)

    print(f"\nTotal Reviews: {len(df)}")

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nMissing Values:")
    print(df.isnull().sum())

    if rating_col:
        print("\nRating Distribution:")
        print(df[rating_col].value_counts().sort_index())

    if date_col:
        print("\nDate Range:")
        print("Oldest :", df[date_col].min())
        print("Newest :", df[date_col].max())

    if review_col:

        print("\nDuplicate Reviews:")
        print(df.duplicated(subset=[review_col]).sum())

        df["review_length"] = df[review_col].astype(str).str.len()

        print("\nReview Length Statistics:")
        print(df["review_length"].describe())

        print("\nTop 10 Longest Reviews:")
        cols = ["review_length", review_col]

        if rating_col:
            cols.insert(0, rating_col)

        print(df.nlargest(10, "review_length")[cols])