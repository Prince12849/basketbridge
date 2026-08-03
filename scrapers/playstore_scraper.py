from google_play_scraper import reviews, Sort
import pandas as pd

APP_ID = "com.grofers.customerapp"  # Blinkit

result, _ = reviews(
    APP_ID,
    lang="en",
    country="in",
    sort=Sort.NEWEST,
    count=1000
)

df = pd.DataFrame(result)

df = df[
    [
        "userName",
        "score",
        "content",
        "at",
        "thumbsUpCount",
    ]
]

df.to_csv(
    "blinkit_playstore_reviews.csv",
    index=False,
    encoding="utf-8-sig",
)

print(df.head())
print(f"\nCollected {len(df)} reviews.")