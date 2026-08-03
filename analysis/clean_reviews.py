import os
import pandas as pd

RAW_DIR = "data/raw"
CLEAN_DIR = "data/cleaned"

os.makedirs(CLEAN_DIR, exist_ok=True)

REVIEW_COLUMNS = [
    "content",
    "review",
    "raw_text",
    "text",
    "comment",
    "body"
]

for file in os.listdir(RAW_DIR):

    if not file.endswith(".csv"):
        continue

    input_path = os.path.join(RAW_DIR, file)

    print(f"\nProcessing: {file}")

    try:
        df = pd.read_csv(input_path)

    except Exception as e:
        print(f"Failed to read {file}: {e}")
        continue

    review_col = None

    for col in REVIEW_COLUMNS:
        if col in df.columns:
            review_col = col
            break

    if review_col is None:
        print(f"No review column found in {file}")
        continue

    original = len(df)

    # Remove duplicates
    df = df.drop_duplicates(subset=[review_col])

    # Remove nulls
    df = df[df[review_col].notna()]

    # Remove blanks
    df = df[df[review_col].astype(str).str.strip() != ""]

    # Remove short reviews
    df = df[df[review_col].astype(str).str.len() >= 15]

    cleaned = len(df)

    output_name = file.replace(".csv", "_clean.csv")
    output_path = os.path.join(CLEAN_DIR, output_name)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Original : {original}")
    print(f"Cleaned  : {cleaned}")
    print(f"Saved -> {output_path}")

print("\nDone.")