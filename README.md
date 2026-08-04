# AI Product Discovery Engine

This repository contains two separate parts of a Blinkit product-management
case study:

- **Part 1 — AI-powered research/discovery engine:** review scraping, cleaning,
  relevance filtering, insight extraction, segmentation/opportunity analysis,
  and report generation.
- **Part 4 — AI-powered customer-facing category discovery MVP:** a focused
  Streamlit prototype called **Worth Trying With Your Order**.

The Part 4 application is independent of the expensive Part 1 operations. It
does not rerun scraping, review filtering, or the 2,233-review analysis.

## AI-NATIVE MVP — WORTH TRYING WITH YOUR ORDER

### Problem

Routine quick-commerce shoppers often open the app with a predefined mission,
then use Search or Previous Orders to buy familiar products. That behavior is
fast, but it gives unfamiliar categories little exposure.

### Research insight

The completed research found that exploration is constrained by price, trust,
awareness, information, and habit. Search and previous-order behavior are
common discovery paths, while recommendations are used less frequently.

The MVP therefore brings one relevant discovery opportunity into the existing
shopping mission instead of trying to turn routine shoppers into browsers.

### Target segment

The primary segment is the **Routine Restocker**: a frequent shopper with a
narrow category mix who is open to relevant, low-friction discovery while
completing a familiar order.

The demo also includes Deal-Sensitive Restocker, Urgency Shopper, and
Trust-First Shopper profiles.

### Product hypothesis

If a Routine Restocker sees one contextually relevant product from a previously
unpurchased category during an existing shopping mission, supported by an
appropriate confidence signal, they will be more likely to purchase from a new
category without materially increasing shopping friction.

### How AI works

When the shopper asks for a suggestion, Gemini receives:

- purchase history
- previously purchased categories
- current cart
- behavioral profile
- simulated catalogue
- price and discount
- ratings and rating counts
- brand and trust information

Gemini decides whether to show a recommendation, selects one product and one
new category, writes a contextual reason, and selects the confidence signal.
The response is required to be one JSON object. A deterministic validation
layer then rejects unknown products, category mismatches, already-purchased
categories, malformed fields, and multiple recommendations.

Urgent sessions are protected by a deterministic friction guardrail. If Gemini
is unavailable, the app uses a clearly labelled demo-only fallback for
non-urgent profiles; urgent profiles are suppressed.

### MVP flow

```text
Browse simulated catalogue
        |
        v
Build a live shopping cart
        |
        + simulated purchase history
        + historically purchased categories
                |
                v
Click "Find something worth trying"
                |
                v
        Gemini decision engine
                |
                v
        Deterministic validation
                |
        +-------+-------+
        |               |
  One new-category   Suppress discovery
   recommendation    when unsafe/urgent
        |
  Add to cart / Not interested
        |
  Session event log + demo analytics
```

The primary screen is intentionally a small shopping experience rather than an
AI engineering dashboard. Visitors browse the simulated catalogue, add normal
products to a live cart, and explicitly ask the AI to evaluate that basket.
Profile presets, Control/AI Variant, and demo analytics remain secondary
controls in the sidebar.

### Simulated data disclaimer

The profiles in `mvp/profiles.py` and products in
`data/mvp/product_catalog.csv` are fictional demo data. They are not real
Blinkit customer profiles, catalogue records, ratings, or production metrics.

### Project structure

```text
mvp/
    app.py            Streamlit shopping interface
    catalog.py        Simulated catalogue loader and validation
    events.py         Session-only event tracking
    profiles.py       Simulated shopper profiles
    prompts.py        Gemini system and user prompt construction
    recommender.py    Gemini decision, retry, guardrails, and fallback
    session.py        Cart and category-breadth helpers
    validators.py     Deterministic response validation
data/mvp/
    product_catalog.csv
tests/
    test_mvp.py
utils/llm.py          Shared Gemini helper; array API preserved
```

## Run locally

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run mvp/app.py
```

The exact application command is:

```bash
streamlit run mvp/app.py
```

Run the automated tests with:

```bash
python -m unittest discover -s tests -v
```

### Required environment variables

```text
GEMINI_API_KEY=your_gemini_api_key
```

The key can also be configured as a Streamlit secret in
`.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_gemini_api_key"
```

Never commit `.env` or `.streamlit/secrets.toml`. The app can start without a
key, but it will use the clearly labelled demo fallback rather than Gemini.

## Deploy to Streamlit Community Cloud

1. Push this repository to a GitHub repository.
2. Open Streamlit Community Cloud and choose **New app**.
3. Select the repository and branch.
4. Set the main file path to `mvp/app.py`.
5. Deploy the app. Streamlit will install dependencies from the root
   `requirements.txt`.
6. In the app settings, add the secret:

   ```toml
   GEMINI_API_KEY = "your_gemini_api_key"
   ```

7. Reboot the app and verify all four simulated profiles, both recommendation
   actions, and the demo analytics panel.

No API key is embedded in frontend code or committed to the repository.

## Measurement concept

The product hypothesis would eventually be measured using New Category Adoption
Rate, supported by recommendation impression-to-interaction rate, CTR,
add-to-cart rate, new-category purchase rate, checkout conversion, time to
checkout, dismissal rate, and cancellation/return rate.

The current app only logs events in Streamlit session state. It does not claim
to provide production Blinkit metrics.

## Limitations

- Shopper profiles and products are simulated.
- There is no database, authentication, payment flow, or persistent analytics.
- The MVP displays at most one recommendation.
- Gemini quality and latency depend on the configured API and model.
- The local fallback is deterministic demo behavior, not a substitute for a
  production recommendation model.
- The validation layer protects category and product integrity but does not
  replace offline evaluation, experimentation, or production safety review.
