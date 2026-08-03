"""
filter_relevant_reviews.py

Filters customer reviews to identify reviews that are relevant for
product discovery, shopping behaviour, category exploration,
and product opportunity analysis.

Input:
    data/cleaned/cleaned_reviews.csv

Outputs:
    data/cleaned/relevant_reviews.csv
    data/cleaned/irrelevant_reviews.csv

Author: Prince Lakra
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import json
import logging
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from utils.llm import generate_json
from tqdm import tqdm

# ============================================================
# Environment
# ============================================================

from dotenv import load_dotenv
import os

# ============================================================
# Configuration
# ============================================================

BATCH_SIZE = 50

MAX_RETRIES = 3

CHECKPOINT_INTERVAL = 100

SLEEP_AFTER_BATCH = 1

# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

CLEANED_DIR = DATA_DIR / "cleaned"

CHECKPOINT_DIR = BASE_DIR / "checkpoints"

LOG_DIR = BASE_DIR / "logs"

PROMPT_DIR = BASE_DIR / "prompts"

INPUT_FILE = CLEANED_DIR / "merged_reviews.csv"

RELEVANT_OUTPUT = CLEANED_DIR / "relevant_reviews.csv"

IRRELEVANT_OUTPUT = CLEANED_DIR / "irrelevant_reviews.csv"

MANUAL_OUTPUT = CLEANED_DIR / "manual_review.csv"

CHECKPOINT_FILE = CHECKPOINT_DIR / "filter_checkpoint.json"

LOG_FILE = LOG_DIR / "filter.log"

# ============================================================
# Create folders
# ============================================================

CLEANED_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================
# Prompt
# ============================================================

PROMPT_FILE = PROMPT_DIR / "filter_prompt.txt"

if not PROMPT_FILE.exists():
    raise FileNotFoundError(
        f"Prompt file not found: {PROMPT_FILE}"
    )

with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

# ============================================================
# Helper Functions
# ============================================================


def load_reviews():
    """
    Load cleaned reviews.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
    "review_id",
    "review_text",
    "source",
    "rating",
    "date",
    ]

    missing = [
        c for c in required_columns
        if c not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    df = df.dropna(subset=["review_text"])

    df["review_text"] = (
    df["review_text"]
    .astype(str)
    .str.strip()
    )

    df = df[df["review_text"] != ""]

    df = df.drop_duplicates(
        subset=["review_text"]
    ).reset_index(drop=True)

    logger.info(
        f"Loaded {len(df)} cleaned reviews."
    )

    return df


def create_batches(df, batch_size=BATCH_SIZE):
    """
    Split dataframe into batches.
    """

    total = len(df)

    for start in range(0, total, batch_size):

        end = min(start + batch_size, total)

        yield df.iloc[start:end]


def build_prompt(batch):
    """
    Convert dataframe batch into GPT prompt.
    """

    reviews = []

    for _, row in batch.iterrows():

        reviews.append(

            f"""
Review ID: {row['review_id']}

Source: {row['source']}

Rating: {row['rating']}

Review:
{row['review_text']}
"""

        )

    review_text = "\n\n---------------------------\n\n".join(reviews)

    prompt = f"""
Classify every review.

Return ONLY valid JSON.

Example:

[
    {{
        "review_id":"101",
        "relevant":true,
        "reason":"User explains why they don't explore categories.",
        "confidence":0.95
    }}
]

Reviews:

{review_text}
"""

    return prompt

# ============================================================
# OpenAI API
# ============================================================

def call_llm(prompt):

    for attempt in range(MAX_RETRIES):

        try:

            response = generate_json(
                SYSTEM_PROMPT,
                prompt,
            )

            print("\nGemini Response:")
            print(response)

            return response

        except Exception as e:

            print("ERROR:", e)

            logger.error(
                f"Attempt {attempt+1}: {e}"
            )

        time.sleep(2)

    return None


# ============================================================
# Validation
# ============================================================

REQUIRED_KEYS = {
    "review_id",
    "relevant",
    "reason",
    "confidence",
}


def validate_response(results):
    """
    Validate GPT response.
    """

    if results is None:
        return False

    if not isinstance(results, list):
        return False

    for item in results:

        if not isinstance(item, dict):
            return False

        if not REQUIRED_KEYS.issubset(item.keys()):
            return False

    return True


# ============================================================
# Checkpoint
# ============================================================

def load_checkpoint():

    print("Checkpoint path:", CHECKPOINT_FILE)

    if not CHECKPOINT_FILE.exists():
        print("No checkpoint found.")
        return {
            "processed": 0,
            "relevant": [],
            "irrelevant": [],
            "manual": [],
        }

    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        checkpoint = json.load(f)

    print("Checkpoint loaded:")
    print("Processed:", checkpoint["processed"])
    print("Relevant:", len(checkpoint["relevant"]))
    print("Irrelevant:", len(checkpoint["irrelevant"]))
    print("Manual:", len(checkpoint["manual"]))

    return checkpoint


def save_checkpoint(
    processed,
    relevant,
    irrelevant,
    manual,
):

    checkpoint = {
        "processed": processed,
        "relevant": relevant,
        "irrelevant": irrelevant,
        "manual": manual,
    }

    with open(
        CHECKPOINT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            checkpoint,
            f,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# Batch Processing
# ============================================================

def process_batches(df):

    checkpoint = load_checkpoint()

    processed = checkpoint["processed"]

    relevant = checkpoint["relevant"]

    irrelevant = checkpoint["irrelevant"]

    manual = checkpoint["manual"]

    remaining = df.iloc[processed:].reset_index(drop=True)

    if len(remaining) == 0:

        logger.info("Nothing left to process.")

        return relevant, irrelevant, manual

    total_batches = (
        len(remaining) + BATCH_SIZE - 1
    ) // BATCH_SIZE

    progress = tqdm(
        create_batches(remaining),
        total=total_batches,
        desc="Filtering Reviews",
    )

    for batch in progress:

        prompt = build_prompt(batch)

        results = call_llm(prompt)

        if results is None or not validate_response(results):

            logger.warning(
                "Invalid response. Sending entire batch to manual review."
            )

            for _, row in batch.iterrows():

                manual.append(row.to_dict())

            processed += len(batch)

            continue

        batch_lookup = {
            str(r.review_id): r
            for r in batch.itertuples()
        }

        for item in results:

            rid = str(item["review_id"])

            if rid not in batch_lookup:

                continue

            row = batch_lookup[rid]

            record = {
                "review_id": row.review_id,
                "source": row.source,
                "rating": row.rating,
                "date": row.date,
                "review_text": row.review_text,
                "relevant": item["relevant"],
                "reason": item["reason"],
                "confidence": item["confidence"],
            }

            if item["relevant"]:

                relevant.append(record)

            else:

                irrelevant.append(record)

        processed += len(batch)

        if processed % CHECKPOINT_INTERVAL == 0:

            save_checkpoint(
                processed,
                relevant,
                irrelevant,
                manual,
            )

            logger.info(
                f"Checkpoint saved ({processed} reviews)"
            )

        time.sleep(SLEEP_AFTER_BATCH)

    save_checkpoint(
        processed,
        relevant,
        irrelevant,
        manual,
    )

    return relevant, irrelevant, manual
# ============================================================
# Main
# ============================================================

def main():

    logger.info("Starting review filtering...")

    df = load_reviews()

    print(f"Loaded {len(df)} reviews.")

    relevant, irrelevant, manual = process_batches(df)

    pd.DataFrame(relevant).to_csv(
        RELEVANT_OUTPUT,
        index=False,
    )

    pd.DataFrame(irrelevant).to_csv(
        IRRELEVANT_OUTPUT,
        index=False,
    )

    pd.DataFrame(manual).to_csv(
        MANUAL_OUTPUT,
        index=False,
    )

    logger.info("Filtering complete.")

    print("\nFiltering complete!")
    print(f"Relevant reviews   : {len(relevant)}")
    print(f"Irrelevant reviews : {len(irrelevant)}")
    print(f"Manual review      : {len(manual)}")


if __name__ == "__main__":
    main()