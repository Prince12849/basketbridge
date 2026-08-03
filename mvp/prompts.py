"""Prompt construction for the single-product discovery decision."""

import json

from .catalog import Product
from .profiles import ShopperProfile


SYSTEM_PROMPT = """
You are the recommendation decision engine for a quick-commerce discovery MVP.
The catalogue and shopper are simulated demo data, not real Blinkit data.

Your goal is to decide whether to show exactly ONE product from a category the
shopper has never purchased before, during the shopping mission already in
progress.

You must consider the shopper profile, purchase history, previously purchased
categories, current cart, product pairings, price and discount, ratings,
reviews count, and brand/trust information.

Return ONLY one valid JSON object with exactly these fields:
{
  "show_recommendation": true,
  "product_id": "P000",
  "new_category": "Category",
  "reason": "A specific explanation grounded in the current cart or profile.",
  "confidence_type": "contextual_relevance",
  "confidence_message": "A confidence signal appropriate for this shopper."
}

Allowed confidence_type values:
- contextual_relevance
- discount
- trust_social_proof
- product_information

If discovery would create friction, return:
{
  "show_recommendation": false,
  "product_id": null,
  "new_category": null,
  "reason": "A specific explanation for suppressing discovery.",
  "confidence_type": null,
  "confidence_message": null
}

Rules:
1. Recommend at most one product.
2. The product_id must exist in the supplied catalogue.
3. The product's category must exactly match new_category.
4. new_category must not be in previously_purchased_categories.
5. Never call a category new if the shopper already purchased it.
6. Routine Restockers should prioritize a clear pairing with the current cart.
7. Deal-Sensitive Restockers should prioritize meaningful savings and explain it.
8. Trust-First Shoppers should prioritize ratings, rating count, and trust signals.
9. Urgency Shoppers should usually be suppressed to protect checkout speed.
10. The reason must mention actual context; do not say only "You might like this".
11. Do not add fields, Markdown, or commentary outside the JSON object.
""".strip()


def build_user_prompt(
    profile: ShopperProfile,
    cart: tuple[Product, ...],
    catalog: tuple[Product, ...],
) -> str:
    """Serialize the complete decision context for Gemini."""

    payload = {
        "shopper": {
            "profile_id": profile.profile_id,
            "profile_name": profile.profile_name,
            "description": profile.description,
            "shopping_behavior": list(profile.shopping_behavior),
            "previously_purchased_categories": list(
                profile.previously_purchased_categories
            ),
            "purchase_history": list(profile.purchase_history),
            "primary_confidence_trigger": profile.primary_confidence_trigger,
            "urgency_level": profile.urgency_level,
            "discovery_receptivity": profile.discovery_receptivity,
        },
        "current_cart": [product.to_dict() for product in cart],
        "available_simulated_catalogue": [product.to_dict() for product in catalog],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
