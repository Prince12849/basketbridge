"""AI-native single-product discovery recommender with safe fallbacks."""

from dataclasses import dataclass
from typing import Callable

from .catalog import Product, catalog_by_id, load_catalog
from .profiles import ShopperProfile
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .validators import ValidationResult, validate_recommendation


LLMCallable = Callable[[str, str], dict]


@dataclass(frozen=True)
class RecommendationResult:
    show_recommendation: bool
    product_id: str | None
    new_category: str | None
    reason: str
    confidence_type: str | None
    confidence_message: str | None
    source: str
    error: str | None = None
    attempts: int = 0

    @classmethod
    def from_payload(
        cls, payload: dict, source: str = "gemini", attempts: int = 1
    ) -> "RecommendationResult":
        return cls(
            show_recommendation=payload["show_recommendation"],
            product_id=payload["product_id"],
            new_category=payload["new_category"],
            reason=payload["reason"],
            confidence_type=payload["confidence_type"],
            confidence_message=payload["confidence_message"],
            source=source,
            attempts=attempts,
        )

    def to_dict(self) -> dict:
        return {
            "show_recommendation": self.show_recommendation,
            "product_id": self.product_id,
            "new_category": self.new_category,
            "reason": self.reason,
            "confidence_type": self.confidence_type,
            "confidence_message": self.confidence_message,
        }


def _suppressed(
    reason: str,
    source: str,
    error: str | None = None,
    attempts: int = 0,
) -> RecommendationResult:
    return RecommendationResult(
        show_recommendation=False,
        product_id=None,
        new_category=None,
        reason=reason,
        confidence_type=None,
        confidence_message=None,
        source=source,
        error=error,
        attempts=attempts,
    )


def _default_llm_call(system_prompt: str, user_prompt: str) -> dict:
    # Lazy import keeps catalogue/profile tests and the no-key UI path safe.
    from utils.llm import generate_json_object

    return generate_json_object(system_prompt, user_prompt)


def _pair_hits(product: Product, cart: tuple[Product, ...]) -> list[str]:
    cart_text = " ".join(
        f"{item.product_name} {item.category} {item.subcategory}".lower()
        for item in cart
    )
    return [pair for pair in product.pairs_with if pair in cart_text]


def _fallback_score(
    product: Product,
    profile: ShopperProfile,
    cart: tuple[Product, ...],
) -> float:
    pair_score = len(_pair_hits(product, cart))
    discount_score = product.discount_percent
    rating_score = product.rating * 10 + min(product.rating_count / 1000, 10)
    trigger = profile.primary_confidence_trigger.lower()

    if "discount" in trigger or "price" in trigger:
        return pair_score * 15 + discount_score * 3 + rating_score
    if "trust" in trigger or "rating" in trigger:
        return pair_score * 10 + rating_score * 4 + discount_score
    return pair_score * 30 + rating_score + discount_score * 0.25


def _demo_fallback(
    profile: ShopperProfile,
    cart: tuple[Product, ...],
    catalog: tuple[Product, ...],
    error: str,
) -> RecommendationResult:
    """Provide a transparent demo-only fallback when Gemini is unavailable."""

    if profile.urgency_level == "High":
        return _suppressed(
            "High-intent urgent shopping session detected. Avoiding additional "
            "discovery friction.",
            source="demo_fallback",
            error=error,
        )

    purchased = set(profile.previously_purchased_categories)
    candidates = [product for product in catalog if product.category not in purchased]
    if not candidates:
        return _suppressed(
            "No eligible new category is available in the simulated catalogue.",
            source="demo_fallback",
            error=error,
        )

    product = max(
        candidates,
        key=lambda item: _fallback_score(item, profile, cart),
    )
    hits = _pair_hits(product, cart)
    cart_names = ", ".join(item.product_name for item in cart[:2])
    trigger = profile.primary_confidence_trigger.lower()

    if "discount" in trigger or "price" in trigger:
        reason = (
            f"{product.discount_percent}% off lowers the price barrier for trying "
            f"{product.category} alongside {cart_names}."
        )
        confidence_type = "discount"
        confidence_message = (
            f"Save {product.discount_percent}% on this simulated first-category trial."
        )
    elif "trust" in trigger or "rating" in trigger:
        reason = (
            f"{product.rating:.1f} stars from {product.rating_count:,} ratings and "
            f"{product.trust_signal.lower()} reduce uncertainty about trying "
            f"{product.category}."
        )
        confidence_type = "trust_social_proof"
        confidence_message = (
            f"{product.rating:.1f} stars from {product.rating_count:,} ratings."
        )
    elif hits:
        reason = (
            f"Pairs naturally with {', '.join(hits)} already represented by "
            f"{cart_names} in your cart."
        )
        confidence_type = "contextual_relevance"
        confidence_message = "A simulated catalogue pairing connected to this order."
    else:
        reason = (
            f"You frequently purchase familiar staples, and this is a relevant "
            f"adjacent category for the current mission."
        )
        confidence_type = "contextual_relevance"
        confidence_message = "A simulated adjacent-category suggestion."

    return RecommendationResult(
        show_recommendation=True,
        product_id=product.product_id,
        new_category=product.category,
        reason=reason,
        confidence_type=confidence_type,
        confidence_message=confidence_message,
        source="demo_fallback",
        error=error,
    )


def recommend(
    profile: ShopperProfile,
    cart_ids: list[str] | tuple[str, ...],
    catalog: tuple[Product, ...] | None = None,
    llm_call: LLMCallable | None = None,
) -> RecommendationResult:
    """Generate and validate exactly one discovery decision.

    Gemini is the primary decision-maker. Invalid AI output is never shown;
    the call is retried once, then safely suppressed. A missing/unavailable
    Gemini configuration uses a clearly labelled deterministic demo fallback.
    """

    catalog = catalog or load_catalog()
    products = catalog_by_id(catalog)
    missing_cart_products = [product_id for product_id in cart_ids if product_id not in products]
    if missing_cart_products:
        return _suppressed(
            "The current cart contains an unavailable simulated product.",
            source="safe_fallback",
            error=f"Unknown cart product IDs: {missing_cart_products}",
        )

    cart = tuple(products[product_id] for product_id in cart_ids)
    generate = llm_call or _default_llm_call
    user_prompt = build_user_prompt(profile, cart, catalog)
    last_error = ""

    for attempt in range(1, 3):
        try:
            payload = generate(SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            if llm_call is None or exc.__class__.__name__ == "LLMConfigurationError":
                return _demo_fallback(profile, cart, catalog, error)
            return _suppressed(
                "The recommendation engine could not complete a safe decision.",
                source="safe_fallback",
                error=error,
                attempts=attempt,
            )

        validation: ValidationResult = validate_recommendation(
            payload,
            catalog,
            profile.previously_purchased_categories,
        )
        if validation.valid:
            # A deterministic friction guardrail protects urgent sessions even
            # if a model returns an over-eager positive recommendation.
            if profile.urgency_level == "High" and payload["show_recommendation"]:
                return _suppressed(
                    "High-intent urgent shopping session detected. Avoiding "
                    "additional discovery friction.",
                    source="guardrail",
                    attempts=attempt,
                )
            return RecommendationResult.from_payload(
                payload, source="gemini", attempts=attempt
            )

        last_error = validation.error
        user_prompt = (
            f"{user_prompt}\n\nYour previous response failed validation: {last_error}. "
            "Return a corrected JSON object only."
        )

    return _suppressed(
        "Recommendation suppressed because the AI response failed validation.",
        source="safe_fallback",
        error=last_error,
        attempts=2,
    )
