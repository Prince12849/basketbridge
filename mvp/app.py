"""Streamlit UI for the simulated Worth Trying With Your Order MVP."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from mvp.catalog import catalog_by_id, load_catalog
from mvp.events import record_event
from mvp.profiles import PROFILES, get_profile
from mvp.recommender import RecommendationResult, recommend
from mvp.session import add_to_cart, category_breadth, remove_from_cart


st.set_page_config(
    page_title="Worth Trying With Your Order",
    page_icon="🛒",
    layout="wide",
)

CATALOG = load_catalog()
PRODUCTS = catalog_by_id(CATALOG)
PROFILE_IDS = [profile.profile_id for profile in PROFILES]


def _initialize_state() -> None:
    if "active_profile_id" not in st.session_state:
        st.session_state.active_profile_id = PROFILE_IDS[0]
    if "cart_ids" not in st.session_state:
        st.session_state.cart_ids = list(get_profile(PROFILE_IDS[0]).default_cart)
    if "events" not in st.session_state:
        st.session_state.events = []
    if "recommendation" not in st.session_state:
        st.session_state.recommendation = None
    if "breadth_before" not in st.session_state:
        st.session_state.breadth_before = category_breadth(
            st.session_state.cart_ids, CATALOG
        )
    if "feedback_captured" not in st.session_state:
        st.session_state.feedback_captured = False
    if "flash_message" not in st.session_state:
        st.session_state.flash_message = None


def _reset_for_profile(profile_id: str) -> None:
    profile = get_profile(profile_id)
    st.session_state.active_profile_id = profile_id
    st.session_state.cart_ids = list(profile.default_cart)
    st.session_state.events = []
    st.session_state.recommendation = None
    st.session_state.breadth_before = category_breadth(profile.default_cart, CATALOG)
    st.session_state.feedback_captured = False


def _format_price(value: float) -> str:
    return f"₹{value:,.0f}"


def _has_event(event_name: str) -> bool:
    return any(event["event_name"] == event_name for event in st.session_state.events)


def _render_profile(profile) -> None:
    st.subheader("Shopper profile")
    st.markdown(f"**{profile.profile_name}**")
    st.write(profile.description)
    st.caption("Simulated shopper profile for MVP demonstration only.")

    with st.expander("Shopping behavior", expanded=True):
        for behavior in profile.shopping_behavior:
            st.markdown(f"- {behavior}")

    st.markdown("**Previously purchased categories**")
    st.write(" · ".join(profile.previously_purchased_categories))
    st.markdown("**Typical purchases**")
    st.write(" · ".join(profile.purchase_history))
    st.markdown("**Primary confidence trigger**")
    st.info(profile.primary_confidence_trigger)


def _render_cart() -> None:
    st.subheader("Current cart")
    cart_ids = st.session_state.cart_ids
    if not cart_ids:
        st.info("Your cart is empty.")
        return

    total = 0.0
    for product_id in list(cart_ids):
        product = PRODUCTS[product_id]
        total += product.discounted_price
        item_col, price_col, action_col = st.columns([4, 2, 1])
        with item_col:
            st.markdown(f"**{product.product_name}**")
            st.caption(product.category)
        with price_col:
            st.write(_format_price(product.discounted_price))
        with action_col:
            if st.button("Remove", key=f"remove_{product_id}"):
                remove_from_cart(st.session_state.cart_ids, product_id)
                st.session_state.recommendation = None
                st.rerun()

    st.divider()
    st.markdown(f"**Cart total:** {_format_price(total)}")
    st.markdown(
        f"**Category breadth:** {category_breadth(cart_ids, CATALOG)} categories"
    )


def _render_recommendation(result: RecommendationResult, profile) -> None:
    if not result.show_recommendation:
        st.info("NO DISCOVERY INTERRUPTION")
        st.markdown(
            "This appears to be a high-intent or unsafe-to-interrupt session, "
            "so the recommendation engine chose not to interrupt checkout."
        )
        st.markdown("**AI decision:** Recommendation suppressed")
        st.markdown(f"**Reason:** {result.reason}")
        if result.error:
            st.caption(f"System note: {result.error}")
        return

    product = PRODUCTS.get(result.product_id)
    if product is None:
        st.error("The validated product is unavailable and was not displayed.")
        return

    st.success("WORTH TRYING WITH YOUR ORDER")
    st.markdown(f"## {product.product_name}")
    st.markdown(f"**NEW CATEGORY FOR YOU · {result.new_category}**")
    st.write(
        f"⭐ {product.rating:.1f} · {product.rating_count:,} ratings · "
        f"{product.brand}"
    )

    st.markdown("**WHY THIS?**")
    st.write(result.reason)

    if product.discount_percent:
        st.markdown(
            f"~~{_format_price(product.price)}~~ "
            f"**{_format_price(product.discounted_price)}** "
            f"· {product.discount_percent}% introductory discount"
        )
    else:
        st.markdown(f"**{_format_price(product.discounted_price)}**")

    st.info(f"Confidence signal · {result.confidence_message}")
    if result.source == "demo_fallback":
        st.caption(
            "Demo fallback: Gemini was unavailable, so this simulated suggestion "
            "was selected by the local safety fallback."
        )

    add_col, dismiss_col = st.columns(2)
    with add_col:
        if st.button("ADD TO CART", type="primary", key="add_recommendation"):
            before = category_breadth(st.session_state.cart_ids, CATALOG)
            add_to_cart(st.session_state.cart_ids, product.product_id, CATALOG)
            after = category_breadth(st.session_state.cart_ids, CATALOG)
            record_event(
                st.session_state.events,
                "new_category_product_added",
                product_id=product.product_id,
                category=product.category,
                category_breadth_before=before,
                category_breadth_after=after,
            )
            st.session_state.recommendation = None
            st.session_state.flash_message = "New category added to your cart."
            st.rerun()
    with dismiss_col:
        if st.button("NOT INTERESTED", key="dismiss_recommendation"):
            record_event(
                st.session_state.events,
                "recommendation_dismissed",
                product_id=product.product_id,
                category=product.category,
            )
            st.session_state.recommendation = None
            st.session_state.feedback_captured = True
            st.rerun()


def _render_analytics(profile) -> None:
    events = st.session_state.events
    shown = any(event["event_name"] == "recommendation_impression" for event in events)
    generated = [
        event for event in events if event["event_name"] == "recommendation_generated"
    ]
    recommended_category = "—"
    if generated:
        recommended_category = generated[-1].get("category") or "—"
    breadth_before = st.session_state.breadth_before
    breadth_now = category_breadth(st.session_state.cart_ids, CATALOG)

    with st.expander("MVP Analytics", expanded=False):
        st.caption("Demo session analytics · not production Blinkit metrics.")
        metric_cols = st.columns(3)
        metric_cols[0].metric("Recommendation shown", "Yes" if shown else "No")
        metric_cols[1].metric("New category added", "Yes" if _has_event("new_category_product_added") else "No")
        metric_cols[2].metric("Recommendation dismissed", "Yes" if _has_event("recommendation_dismissed") else "No")
        st.write(f"Recommended category: **{recommended_category}**")
        st.write(f"Purchased-category breadth before: **{breadth_before}**")
        st.write(f"Current category breadth: **{breadth_now}**")
        if events:
            st.write("Session events")
            st.dataframe(events, use_container_width=True, hide_index=True)
        if st.session_state.feedback_captured:
            st.success("Feedback captured")


def main() -> None:
    _initialize_state()

    st.title("WORTH TRYING WITH YOUR ORDER")
    st.caption(
        "AI-native category discovery for routine shopping missions · simulated demo MVP"
    )
    st.write(
        "Bring one relevant product from a new category into the mission your "
        "shopper is already completing."
    )

    if st.session_state.flash_message:
        st.success(st.session_state.flash_message)
        st.session_state.flash_message = None

    selected_profile_id = st.sidebar.selectbox(
        "Select simulated shopper",
        PROFILE_IDS,
        index=PROFILE_IDS.index(st.session_state.active_profile_id),
        format_func=lambda profile_id: get_profile(profile_id).profile_name,
    )
    if selected_profile_id != st.session_state.active_profile_id:
        _reset_for_profile(selected_profile_id)
        st.rerun()

    profile = get_profile(selected_profile_id)
    mode = st.sidebar.radio("Experience", ["AI Variant", "Control"])
    st.sidebar.caption(
        "All shopper profiles and products are simulated demo data, not real Blinkit data."
    )

    profile_col, cart_col = st.columns([1, 1])
    with profile_col:
        _render_profile(profile)
    with cart_col:
        _render_cart()

    st.divider()
    st.subheader("AI discovery")
    if mode == "Control":
        st.info("Control experience selected: no discovery intervention is shown.")
    elif st.button("Find something worth trying", type="primary"):
        st.session_state.breadth_before = category_breadth(
            st.session_state.cart_ids, CATALOG
        )
        record_event(
            st.session_state.events,
            "recommendation_requested",
            profile_id=profile.profile_id,
            cart_product_ids=list(st.session_state.cart_ids),
        )
        with st.spinner("Finding a relevant new category..."):
            result = recommend(profile, st.session_state.cart_ids, CATALOG)
        st.session_state.recommendation = result
        record_event(
            st.session_state.events,
            "recommendation_generated",
            show_recommendation=result.show_recommendation,
            product_id=result.product_id,
            category=result.new_category,
            source=result.source,
            error=result.error,
        )
        if result.show_recommendation:
            record_event(
                st.session_state.events,
                "recommendation_impression",
                product_id=result.product_id,
                category=result.new_category,
            )

    if st.session_state.recommendation is not None:
        _render_recommendation(st.session_state.recommendation, profile)
    else:
        st.caption("Ask the AI to evaluate this shopping mission.")

    _render_analytics(profile)


if __name__ == "__main__":
    main()
