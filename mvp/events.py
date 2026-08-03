"""Session-only event tracking for the MVP demo analytics panel."""

from datetime import datetime, timezone


EVENT_NAMES = {
    "recommendation_requested",
    "recommendation_generated",
    "recommendation_impression",
    "new_category_product_added",
    "recommendation_dismissed",
    "checkout_started",
}


def record_event(events: list[dict], event_name: str, **properties) -> dict:
    """Append a validated event to a Streamlit session-state list."""

    if event_name not in EVENT_NAMES:
        raise ValueError(f"Unknown MVP event: {event_name}")

    event = {
        "event_name": event_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **properties,
    }
    events.append(event)
    return event
