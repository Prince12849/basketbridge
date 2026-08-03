"""Deterministic guardrails around Gemini recommendation output."""

from dataclasses import dataclass

from .catalog import Product, catalog_by_id


REQUIRED_FIELDS = {
    "show_recommendation",
    "product_id",
    "new_category",
    "reason",
    "confidence_type",
    "confidence_message",
}

ALLOWED_CONFIDENCE_TYPES = {
    "contextual_relevance",
    "discount",
    "trust_social_proof",
    "product_information",
}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    error: str = ""


def validate_recommendation(
    payload,
    catalog: tuple[Product, ...],
    previously_purchased_categories: tuple[str, ...] | list[str] | set[str],
) -> ValidationResult:
    """Validate the complete recommendation contract and business rules."""

    if not isinstance(payload, dict):
        return ValidationResult(False, "AI response must be a JSON object")

    if set(payload) != REQUIRED_FIELDS:
        missing = REQUIRED_FIELDS - set(payload)
        extra = set(payload) - REQUIRED_FIELDS
        details = []
        if missing:
            details.append(f"missing fields: {sorted(missing)}")
        if extra:
            details.append(f"unexpected fields: {sorted(extra)}")
        return ValidationResult(False, "; ".join(details))

    show = payload["show_recommendation"]
    if not isinstance(show, bool):
        return ValidationResult(False, "show_recommendation must be boolean")

    reason = payload["reason"]
    if not isinstance(reason, str) or not reason.strip():
        return ValidationResult(False, "reason must be a non-empty string")

    if not show:
        null_fields = (
            "product_id",
            "new_category",
            "confidence_type",
            "confidence_message",
        )
        if any(payload[field] is not None for field in null_fields):
            return ValidationResult(
                False, "suppressed recommendations must have null product fields"
            )
        return ValidationResult(True)

    product_id = payload["product_id"]
    new_category = payload["new_category"]
    confidence_type = payload["confidence_type"]
    confidence_message = payload["confidence_message"]

    if not isinstance(product_id, str) or not product_id.strip():
        return ValidationResult(False, "product_id must be a non-empty string")
    if not isinstance(new_category, str) or not new_category.strip():
        return ValidationResult(False, "new_category must be a non-empty string")
    if confidence_type not in ALLOWED_CONFIDENCE_TYPES:
        return ValidationResult(False, "confidence_type is not allowed")
    if not isinstance(confidence_message, str) or not confidence_message.strip():
        return ValidationResult(False, "confidence_message must be non-empty")

    products = catalog_by_id(catalog)
    product = products.get(product_id)
    if product is None:
        return ValidationResult(False, f"unknown product_id: {product_id}")
    if product.category != new_category:
        return ValidationResult(
            False,
            f"product category mismatch: {product.category} != {new_category}",
        )
    if new_category in set(previously_purchased_categories):
        return ValidationResult(
            False,
            f"category already purchased: {new_category}",
        )

    return ValidationResult(True)
