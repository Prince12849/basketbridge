import json
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from utils.llm import generate_json

# ----------------------------
# Configuration
# ----------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = PROJECT_ROOT / "data" / "cleaned" / "relevant_reviews.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "review_insights.csv"
FAILED_FILE = PROJECT_ROOT / "data" / "processed" / "failed_reviews.csv"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CHECKPOINT_FILE = CHECKPOINT_DIR / "insights_checkpoint.json"

CHECKPOINT_DIR.mkdir(exist_ok=True)

BATCH_SIZE = 20
MAX_RETRIES = 3
CHECKPOINT_INTERVAL = 100
SLEEP_AFTER_BATCH = 1

def build_prompt(batch):
    reviews = []

    for _, row in batch.iterrows():
        reviews.append(
            {
                "review_id": row["review_id"],
                "review": row["review_text"]
            }
        )

    return json.dumps(reviews, indent=2)

SYSTEM_PROMPT = """
You are a Senior Product Manager at Blinkit.

Your task is to analyze customer reviews and extract structured product insights.

Your goal is to understand:
- Why users do or do not explore new product categories.
- What prevents category exploration.
- How users discover products.
- What improvements Blinkit should make.

Return ONLY valid JSON.

Each review must return EXACTLY one JSON object.

Required fields:

review_id
feature
shopping_stage
pain_point
exploration_barrier
user_need
discovery_method
category_mentioned
sentiment
severity

------------------------
Allowed Values
------------------------

feature (choose ONLY ONE)

- Search
- Homepage
- Recommendations
- Categories
- Offers
- Cart
- Checkout
- Delivery
- Inventory
- Pricing
- General Experience

shopping_stage (choose ONLY ONE)

- Discovery
- Browsing
- Searching
- Selection
- Checkout
- Delivery
- Post-Purchase

exploration_barrier (choose ONLY ONE)

- Habit
- Lack of Awareness
- Poor Recommendations
- Price Concern
- Trust
- Limited Information
- No Need
- App Experience
- Unknown

discovery_method (choose ONLY ONE)

- Search
- Homepage
- Categories
- Recommendations
- Offers
- Previous Orders
- Unknown

category_mentioned (choose ONLY ONE)

- Groceries
- Snacks & Beverages
- Personal Care
- Household Essentials
- Baby Care
- Pet Care
- Medicines
- Electronics
- Unknown

sentiment (choose ONLY ONE)

- Positive
- Neutral
- Negative
- Mixed

severity (choose ONLY ONE)

- High
- Medium
- Low

------------------------
Field Definitions
------------------------

pain_point

Write ONE short sentence (maximum 15 words).

Examples:
"High delivery charges."
"Search results are irrelevant."

If there is no pain point, return:
"Unknown"

user_need

Write ONE short sentence (maximum 12 words).

Examples:
"Lower delivery charges."
"Better recommendations."

If unknown, return:
"Unknown"

------------------------
Rules
------------------------

1. Return ONLY valid JSON.
2. Return exactly one object per review.
3. Never invent new labels.
4. Always use the allowed values exactly as written.
5. Use double quotes for every JSON key and value.
6. If information cannot be determined, return "Unknown".
7. Do NOT explain your reasoning.
8. Do NOT return markdown.
9. Do NOT include extra fields.
10. Do NOT return anything except JSON.

Example:

[
{
"review_id":123,
"feature":"Search",
"shopping_stage":"Discovery",
"pain_point":"Search results show familiar products.",
"exploration_barrier":"Habit",
"user_need":"Better personalized recommendations.",
"discovery_method":"Search",
"category_mentioned":"Personal Care",
"sentiment":"Negative",
"severity":"High"
}
]
"""

REQUIRED_FIELDS = [
    "review_id",
    "feature",
    "shopping_stage",
    "pain_point",
    "exploration_barrier",
    "user_need",
    "discovery_method",
    "category_mentioned",
    "sentiment",
    "severity",
]
REQUIRED_FIELDS = [
    "review_id",
    "feature",
    "shopping_stage",
    "pain_point",
    "exploration_barrier",
    "user_need",
    "discovery_method",
    "category_mentioned",
    "sentiment",
    "severity",
]

ALLOWED_FEATURES = {
    "Search",
    "Homepage",
    "Recommendations",
    "Categories",
    "Offers",
    "Cart",
    "Checkout",
    "Delivery",
    "Inventory",
    "Pricing",
    "General Experience",
}

ALLOWED_SHOPPING_STAGE = {
    "Discovery",
    "Browsing",
    "Searching",
    "Selection",
    "Checkout",
    "Delivery",
    "Post-Purchase",
}

ALLOWED_BARRIERS = {
    "Habit",
    "Lack of Awareness",
    "Poor Recommendations",
    "Price Concern",
    "Trust",
    "Limited Information",
    "No Need",
    "App Experience",
    "Unknown",
}

ALLOWED_DISCOVERY = {
    "Search",
    "Homepage",
    "Categories",
    "Recommendations",
    "Offers",
    "Previous Orders",
    "Unknown",
}

ALLOWED_CATEGORY = {
    "Groceries",
    "Snacks & Beverages",
    "Personal Care",
    "Household Essentials",
    "Baby Care",
    "Pet Care",
    "Medicines",
    "Electronics",
    "Unknown",
}

ALLOWED_SENTIMENT = {
    "Positive",
    "Neutral",
    "Negative",
    "Mixed",
}

ALLOWED_SEVERITY = {
    "High",
    "Medium",
    "Low",
}
def validate_response(response):

    if not isinstance(response, list):
        return False

    for item in response:

        if not isinstance(item, dict):
            return False

        for field in REQUIRED_FIELDS:
            if field not in item:
                return False

        if item["feature"] not in ALLOWED_FEATURES:
            return False

        if item["shopping_stage"] not in ALLOWED_SHOPPING_STAGE:
            return False

        if item["exploration_barrier"] not in ALLOWED_BARRIERS:
            return False

        if item["discovery_method"] not in ALLOWED_DISCOVERY:
            return False

        if item["category_mentioned"] not in ALLOWED_CATEGORY:
            return False

        if item["sentiment"] not in ALLOWED_SENTIMENT:
            return False

        if item["severity"] not in ALLOWED_SEVERITY:
            return False

    return True
def extract_batch(batch):

    prompt = build_prompt(batch)

    for attempt in range(MAX_RETRIES):

        try:

            response = generate_json(
                SYSTEM_PROMPT,
                prompt,
            )

            if validate_response(response):
                NORMALIZATION = {
                    "Lack Of Awareness": "Lack of Awareness",
                    "Recommendation": "Recommendations",
                    "Category": "Categories",
                    "General": "Unknown",
                    "None.": "Unknown",
                }
                for item in response:
                    for key, value in item.items():
                        if isinstance(value, str):
                            item[key] = NORMALIZATION.get(value, value)
                return response

        except Exception as e:

            print(f"Retry {attempt + 1}: {e}")

            time.sleep(2)

    print("Batch failed. Saving for manual review...")

    failed = batch.copy()

    if FAILED_FILE.exists():
        failed.to_csv(
            FAILED_FILE,
            mode="a",
            index=False,
            header=False,
        )
    else:
        failed.to_csv(
            FAILED_FILE,
            index=False,
        )

    return []

def load_checkpoint():

    if CHECKPOINT_FILE.exists():

        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)

    return {"last_processed": 0}
def save_checkpoint(last_processed):

    with open(CHECKPOINT_FILE, "w") as f:

        json.dump(
            {
                "last_processed": last_processed
            },
            f,
            indent=2,
        )
def load_reviews():

    df = pd.read_csv(INPUT_FILE)

    return df
def main():

    df = load_reviews()

    checkpoint = load_checkpoint()

    start = checkpoint["last_processed"]

    results = []

    if start > 0 and OUTPUT_FILE.exists():

        results = pd.read_csv(OUTPUT_FILE).to_dict("records")

    for i in tqdm(range(start, len(df), BATCH_SIZE)):

        batch = df.iloc[i:i+BATCH_SIZE]

        insights = extract_batch(batch)

        results.extend(insights)

        if (i + BATCH_SIZE) % CHECKPOINT_INTERVAL == 0:

            pd.DataFrame(results).to_csv(
                OUTPUT_FILE,
                index=False,
            )

            save_checkpoint(i + BATCH_SIZE)

        time.sleep(SLEEP_AFTER_BATCH)

    pd.DataFrame(results).to_csv(
        OUTPUT_FILE,
        index=False,
    )

    save_checkpoint(len(df))

    print()

    failed_reviews = 0
    if FAILED_FILE.exists():
        failed_reviews = len(pd.read_csv(FAILED_FILE))

    print("\n===================================")
    print("Insight extraction complete!")
    print(f"Insights generated : {len(results)}")
    print(f"Failed reviews     : {failed_reviews}")
    print("===================================")

if __name__ == "__main__":
    main()