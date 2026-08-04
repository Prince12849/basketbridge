"""Public-facing Streamlit shopping prototype for the category discovery MVP."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from mvp.catalog import Product, catalog_by_id, load_catalog
from mvp.events import record_event
from mvp.profiles import PROFILES, ShopperProfile, get_profile
from mvp.recommender import RecommendationResult, recommend
from mvp.session import add_to_cart, category_breadth, remove_from_cart


st.set_page_config(
    page_title="BasketBridge",
    page_icon="🛒",
    layout="wide",
)


CATALOG = load_catalog()
PRODUCTS = catalog_by_id(CATALOG)
PROFILE_IDS = [profile.profile_id for profile in PROFILES]
CATEGORY_OPTIONS = ["All categories"] + sorted({product.category for product in CATALOG})


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: light !important;
            --bb-cream: #fffdf5;
            --bb-card: #ffffff;
            --bb-sidebar: #f5ffe8;
            --bb-ink: #143c22;
            --bb-charcoal: #1f2933;
            --bb-muted: #5d6b5f;
            --bb-border: #e5e8d3;
            --bb-green: #16853b;
            --bb-green-soft: #e3f6bd;
            --bb-coral: #df6a5e;
            --bb-blue-bg: #e8f1ff;
            --bb-blue-ink: #1f4f85;
        }
        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background: var(--bb-cream) !important;
            color: var(--bb-charcoal) !important;
        }
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"] {
            background: var(--bb-cream) !important;
            color: var(--bb-ink) !important;
        }
        [data-testid="stHeader"] [data-testid="stToolbar"] button,
        [data-testid="stHeader"] [data-testid="stToolbar"] a,
        [data-testid="stHeader"] [data-testid="stToolbar"] svg {
            color: var(--bb-ink) !important;
        }
        [data-testid="stHeader"] [data-testid="stToolbar"] svg {
            fill: currentColor !important;
            stroke: currentColor !important;
        }
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"],
        [data-testid="stSidebarUserContent"] {
            background: var(--bb-sidebar) !important;
            color: var(--bb-ink) !important;
            border-right-color: #d8e9b8 !important;
        }
        .stApp [data-testid="stMarkdownContainer"],
        .stApp [data-testid="stMarkdownContainer"] p,
        .stApp [data-testid="stMarkdownContainer"] li,
        .stApp [data-testid="stMarkdownContainer"] strong,
        .stApp [data-testid="stMarkdownContainer"] em,
        .stApp [data-testid="stMarkdownContainer"] h1,
        .stApp [data-testid="stMarkdownContainer"] h2,
        .stApp [data-testid="stMarkdownContainer"] h3,
        .stApp [data-testid="stMarkdownContainer"] h4,
        .stApp [data-testid="stCaptionContainer"],
        .stApp [data-testid="stCaptionContainer"] p,
        .stApp [data-testid="stWidgetLabel"],
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp label,
        .stApp [role="radiogroup"] label,
        .stApp [role="radiogroup"] p {
            color: var(--bb-charcoal) !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] label {
            color: var(--bb-ink) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--bb-card) !important;
            border-color: var(--bb-border) !important;
            color: var(--bb-charcoal) !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] * {
            color: inherit;
        }
        [data-testid="stExpander"],
        [data-testid="stExpander"] details,
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
            background: var(--bb-sidebar) !important;
            color: var(--bb-ink) !important;
            border-color: #d8e9b8 !important;
        }
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stExpander"] [data-testid="stCaptionContainer"] p {
            color: var(--bb-ink) !important;
        }
        [data-baseweb="select"] > div,
        [data-baseweb="select"] input,
        [data-baseweb="select"] span,
        [role="listbox"],
        [role="option"] {
            background: var(--bb-card) !important;
            color: var(--bb-ink) !important;
            border-color: #bdd5a1 !important;
        }
        [role="option"]:hover,
        [role="option"][aria-selected="true"] {
            background: var(--bb-green-soft) !important;
            color: var(--bb-ink) !important;
        }
        [data-testid="stAlert"] {
            background: var(--bb-blue-bg) !important;
            border-color: #a9c6eb !important;
            color: var(--bb-blue-ink) !important;
        }
        [data-testid="stAlert"] * {
            color: var(--bb-blue-ink) !important;
        }
        [data-testid="stAlertContainer"] {
            background: var(--bb-blue-bg) !important;
            border-color: #a9c6eb !important;
            color: var(--bb-blue-ink) !important;
        }
        [data-testid="stAlertContainer"] * {
            color: var(--bb-blue-ink) !important;
        }
        [data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-primary"] {
            background: var(--bb-coral) !important;
            border-color: var(--bb-coral) !important;
            color: #ffffff !important;
        }
        [data-testid="stBaseButton-primary"] *,
        button[data-testid="stBaseButton-primary"] * {
            color: #ffffff !important;
        }
        .stApp button[data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"],
        .stApp button[data-testid="stBaseButton-primary"] [data-testid="stMarkdownContainer"] p,
        .stApp button[data-testid="stBaseButton-primary"] span {
            color: #ffffff !important;
        }
        [data-testid="stBaseButton-secondary"],
        button[data-testid="stBaseButton-secondary"] {
            background: var(--bb-card) !important;
            border-color: #9fc98d !important;
            color: var(--bb-ink) !important;
        }
        [data-testid="stBaseButton-secondary"] *,
        button[data-testid="stBaseButton-secondary"] * {
            color: var(--bb-ink) !important;
        }
        .stApp button[data-testid="stBaseButton-secondary"] [data-testid="stMarkdownContainer"],
        .stApp button[data-testid="stBaseButton-secondary"] [data-testid="stMarkdownContainer"] p,
        .stApp button[data-testid="stBaseButton-secondary"] span {
            color: var(--bb-ink) !important;
        }
        [data-testid="stBaseButton-secondary"]:disabled,
        button[data-testid="stBaseButton-secondary"]:disabled {
            background: #edf4e8 !important;
            border-color: #cbdcc2 !important;
            color: var(--bb-muted) !important;
        }
        [data-testid="stBaseButton-secondary"]:disabled *,
        button[data-testid="stBaseButton-secondary"]:disabled * {
            color: var(--bb-muted) !important;
        }
        .stApp input,
        .stApp textarea {
            background: var(--bb-card) !important;
            color: var(--bb-ink) !important;
            caret-color: var(--bb-ink) !important;
        }
        .stApp input::placeholder,
        .stApp textarea::placeholder {
            color: var(--bb-muted) !important;
        }
        .brand-mark {
            color: var(--bb-green) !important;
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .hero {
            background: linear-gradient(115deg, #fff4a8 0%, #efffd8 100%);
            border: 1px solid #e5edb7;
            border-radius: 22px;
            padding: 1.35rem 1.5rem;
            margin: 0.35rem 0 1.25rem 0;
        }
        .hero h1 {
            color: var(--bb-ink) !important;
            font-size: clamp(1.8rem, 4vw, 3rem);
            line-height: 1.05;
            margin: 0.35rem 0;
        }
        .hero p {
            color: #4d5f45 !important;
            margin: 0;
        }
        .section-kicker {
            color: var(--bb-green) !important;
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--bb-border);
            border-radius: 16px;
            background: var(--bb-card);
        }
        .price-now {
            color: var(--bb-ink) !important;
            font-size: 1.05rem;
            font-weight: 800;
        }
        .price-old {
            color: #6c786c !important;
            text-decoration: line-through;
            margin-left: 0.35rem;
        }
        .discount-pill {
            background: var(--bb-green-soft) !important;
            border-radius: 999px;
            color: #26703a !important;
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 0.18rem 0.5rem;
        }
        .demo-note {
            color: var(--bb-muted) !important;
            font-size: 0.78rem;
        }
        .cart-heading {
            color: var(--bb-ink) !important;
            font-size: 1.25rem;
            font-weight: 800;
        }
        .recommendation-strip {
            background: var(--bb-green) !important;
            border-radius: 14px 14px 0 0;
            color: #ffffff !important;
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            padding: 0.65rem 0.85rem;
            text-transform: uppercase;
        }
        .recommendation-strip * {
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _initialize_state() -> None:
    default_profile = get_profile("routine_restocker")
    if "active_profile_id" not in st.session_state:
        st.session_state.active_profile_id = default_profile.profile_id
    if "cart_ids" not in st.session_state:
        st.session_state.cart_ids = list(default_profile.default_cart)
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
    if "catalog_category" not in st.session_state:
        st.session_state.catalog_category = CATEGORY_OPTIONS[0]


def _reset_for_profile(profile_id: str) -> None:
    profile = get_profile(profile_id)
    st.session_state.active_profile_id = profile_id
    st.session_state.cart_ids = list(profile.default_cart)
    st.session_state.events = []
    st.session_state.recommendation = None
    st.session_state.breadth_before = category_breadth(profile.default_cart, CATALOG)
    st.session_state.feedback_captured = False
    st.session_state.flash_message = None
    st.session_state.catalog_category = CATEGORY_OPTIONS[0]


def _format_price(value: float) -> str:
    return f"₹{value:,.0f}"


def _format_profile(profile_id: str) -> str:
    return get_profile(profile_id).profile_name


def _has_event(event_name: str) -> bool:
    return any(event["event_name"] == event_name for event in st.session_state.events)


def _render_sidebar(profile: ShopperProfile, mode: str) -> None:
    with st.sidebar:
        st.markdown('<div class="brand-mark">Independent case-study prototype</div>', unsafe_allow_html=True)
        st.markdown("### BasketBridge")
        st.markdown("**Contextual category discovery**")
        st.caption(
            "A simulated quick-commerce experience for testing contextual "
            "new-category discovery."
        )
        st.caption("Not an official Blinkit product.")

        with st.expander("Demo controls", expanded=False):
            st.selectbox(
                "Shopper preset",
                PROFILE_IDS,
                index=PROFILE_IDS.index(st.session_state.active_profile_id),
                format_func=_format_profile,
                key="profile_selector",
            )
            st.radio(
                "Experience",
                ["AI Variant", "Control"],
                index=0,
                key="experience_mode",
            )
            st.caption("AI Variant is the default. Controls are for case-study demonstration.")

        with st.expander("Simulated shopper context", expanded=False):
            st.markdown(f"**{profile.profile_name}**")
            st.write(profile.description)
            st.markdown("**Previously purchased categories**")
            st.write(" · ".join(profile.previously_purchased_categories))
            st.markdown("**Typical purchases**")
            st.write(" · ".join(profile.purchase_history))
            st.markdown("**Shopping behavior**")
            for behavior in profile.shopping_behavior:
                st.markdown(f"- {behavior}")
            st.info(f"Confidence trigger: {profile.primary_confidence_trigger}")

        _render_analytics_sidebar()


def _render_analytics_sidebar() -> None:
    events = st.session_state.events
    generated = [
        event for event in events if event["event_name"] == "recommendation_generated"
    ]
    recommended_category = generated[-1].get("category") or "—" if generated else "—"
    current_breadth = category_breadth(st.session_state.cart_ids, CATALOG)

    with st.expander("Demo session analytics", expanded=False):
        st.caption("Demo session analytics · not production Blinkit metrics.")
        st.write(
            f"Recommendation shown: **{'Yes' if _has_event('recommendation_impression') else 'No'}**"
        )
        st.write(f"Recommended category: **{recommended_category}**")
        st.write(
            f"New category added: **{'Yes' if _has_event('new_category_product_added') else 'No'}**"
        )
        st.write(
            f"Recommendation dismissed: **{'Yes' if _has_event('recommendation_dismissed') else 'No'}**"
        )
        st.write(f"Current category breadth: **{current_breadth}**")
        if st.session_state.feedback_captured:
            st.success("Feedback captured")
        if events:
            st.dataframe(events, use_container_width=True, hide_index=True)


def _render_product_card(product: Product) -> None:
    already_added = product.product_id in st.session_state.cart_ids
    with st.container(border=True):
        st.markdown(f"**{product.product_name}**")
        st.caption(f"{product.category} · {product.subcategory}")
        st.write(f"⭐ {product.rating:.1f} · {product.rating_count:,} ratings")

        if product.discount_percent:
            st.markdown(
                f'<span class="price-now">{_format_price(product.discounted_price)}</span>'
                f'<span class="price-old">{_format_price(product.price)}</span> '
                f'<span class="discount-pill">{product.discount_percent}% off</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span class="price-now">{_format_price(product.discounted_price)}</span>',
                unsafe_allow_html=True,
            )

        st.caption(product.description)
        if already_added:
            st.button(
                "ADDED TO CART",
                key=f"catalog_added_{product.product_id}",
                disabled=True,
                use_container_width=True,
            )
        elif st.button(
            "ADD",
            key=f"catalog_add_{product.product_id}",
            type="secondary",
            use_container_width=True,
        ):
            add_to_cart(st.session_state.cart_ids, product.product_id, CATALOG)
            st.session_state.recommendation = None
            st.session_state.flash_message = f"{product.product_name} added to your cart."
            st.rerun()


def _render_catalogue() -> None:
    st.markdown('<div class="section-kicker">Browse the simulated catalogue</div>', unsafe_allow_html=True)
    st.markdown("## Build your order")
    st.caption("Add a few familiar or exploratory products. Your live cart is the shopping-intent signal.")

    selected_category = st.selectbox(
        "Browse by category",
        CATEGORY_OPTIONS,
        key="catalog_category",
        label_visibility="collapsed",
    )
    products = [
        product
        for product in CATALOG
        if selected_category == "All categories" or product.category == selected_category
    ]

    for start in range(0, len(products), 3):
        columns = st.columns(3, gap="medium")
        for column, product in zip(columns, products[start : start + 3]):
            with column:
                _render_product_card(product)


def _render_cart(profile: ShopperProfile, mode: str) -> None:
    with st.container(border=True):
        st.markdown('<div class="cart-heading">Your live cart</div>', unsafe_allow_html=True)
        st.caption("This is the mission the recommendation engine will evaluate.")

        cart_ids = st.session_state.cart_ids
        if not cart_ids:
            st.info("Your cart is empty. Add something from the catalogue to begin.")
        else:
            total = 0.0
            for product_id in list(cart_ids):
                product = PRODUCTS[product_id]
                total += product.discounted_price
                item_col, price_col, action_col = st.columns([4.5, 1.8, 3.7])
                with item_col:
                    st.markdown(f"**{product.product_name}**")
                    st.caption(product.category)
                with price_col:
                    st.write(_format_price(product.discounted_price))
                with action_col:
                    if st.button(
                        "Remove",
                        key=f"remove_{product_id}",
                    ):
                        remove_from_cart(st.session_state.cart_ids, product_id)
                        st.session_state.recommendation = None
                        st.rerun()

            st.divider()
            st.markdown(f"**Cart total:** {_format_price(total)}")
            st.markdown(
                f"**Category breadth:** {category_breadth(cart_ids, CATALOG)} categories"
            )

        st.divider()
        if mode == "AI Variant":
            if st.button(
                "Find something worth trying",
                type="primary",
                use_container_width=True,
            ):
                _request_recommendation(profile)
        else:
            st.caption("Control experience: the discovery intervention is hidden.")


def _request_recommendation(profile: ShopperProfile) -> None:
    st.session_state.breadth_before = category_breadth(
        st.session_state.cart_ids, CATALOG
    )
    record_event(
        st.session_state.events,
        "recommendation_requested",
        profile_id=profile.profile_id,
        cart_product_ids=list(st.session_state.cart_ids),
    )
    with st.spinner("Finding one relevant new category..."):
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


def _render_recommendation(result: RecommendationResult) -> None:
    with st.container(border=True):
        if not result.show_recommendation:
            st.markdown('<div class="recommendation-strip">No discovery interruption</div>', unsafe_allow_html=True)
            st.markdown("### Checkout stays focused")
            st.write(result.reason)
            with st.expander("AI decision detail"):
                st.write("Recommendation suppressed")
                if result.error:
                    st.caption(f"System note: {result.error}")
            return

        product = PRODUCTS.get(result.product_id)
        if product is None:
            st.error("The validated product is unavailable and was not displayed.")
            return

        st.markdown('<div class="recommendation-strip">WORTH TRYING WITH YOUR ORDER</div>', unsafe_allow_html=True)
        st.markdown(f"### {product.product_name}")
        st.markdown(f"**NEW CATEGORY FOR YOU · {result.new_category}**")
        st.write(
            f"⭐ {product.rating:.1f} · {product.rating_count:,} ratings · {product.brand}"
        )
        st.markdown("**Why this?**")
        st.write(result.reason)

        if product.discount_percent:
            st.markdown(
                f'<span class="price-now">{_format_price(product.discounted_price)}</span>'
                f'<span class="price-old">{_format_price(product.price)}</span> '
                f'<span class="discount-pill">{product.discount_percent}% introductory discount</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span class="price-now">{_format_price(product.discounted_price)}</span>',
                unsafe_allow_html=True,
            )

        st.info(f"Confidence signal · {result.confidence_message}")
        if result.source == "demo_fallback":
            st.caption(
                "Demo fallback: Gemini was unavailable, so this simulated suggestion "
                "was selected by the local safety fallback."
            )

        add_col, dismiss_col = st.columns(2)
        with add_col:
            if st.button("ADD TO CART", type="primary", key="add_recommendation", use_container_width=True):
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
            if st.button("NOT INTERESTED", key="dismiss_recommendation", use_container_width=True):
                record_event(
                    st.session_state.events,
                    "recommendation_dismissed",
                    product_id=product.product_id,
                    category=product.category,
                )
                st.session_state.recommendation = None
                st.session_state.feedback_captured = True
                st.rerun()

        with st.expander("AI decision detail"):
            st.write(f"Decision source: {result.source}")
            st.write(f"Validation attempts: {result.attempts}")
            st.write(result.confidence_message)


def main() -> None:
    _initialize_state()
    _inject_styles()

    selected_profile_id = st.session_state.get("profile_selector", "routine_restocker")
    if selected_profile_id != st.session_state.active_profile_id:
        _reset_for_profile(selected_profile_id)
    profile = get_profile(st.session_state.active_profile_id)
    mode = st.session_state.get("experience_mode", "AI Variant")

    _render_sidebar(profile, mode)

    # The sidebar selectbox is rendered above; a changed value is applied on
    # the next Streamlit rerun without changing the recommendation backend.
    selected_profile_id = st.session_state.get("profile_selector", profile.profile_id)
    if selected_profile_id != profile.profile_id:
        _reset_for_profile(selected_profile_id)
        st.rerun()
    profile = get_profile(st.session_state.active_profile_id)
    mode = st.session_state.get("experience_mode", "AI Variant")

    st.markdown('<div class="hero"><div class="brand-mark">BasketBridge · independent case-study prototype</div><h1>Shop your usual.<br>Discover beyond it.</h1><p>Build your basket as usual. BasketBridge uses the live shopping mission to find one relevant new-category discovery opportunity.</p></div>', unsafe_allow_html=True)

    if st.session_state.flash_message:
        st.success(st.session_state.flash_message)
        st.session_state.flash_message = None

    catalogue_col, cart_col = st.columns([1.3, 1], gap="large")
    with catalogue_col:
        _render_catalogue()
    with cart_col:
        _render_cart(profile, mode)

    st.divider()
    if st.session_state.recommendation is None:
        st.markdown('<div class="section-kicker">Contextual discovery</div>', unsafe_allow_html=True)
        st.caption("Add products to your live cart, then choose “Find something worth trying”.")
    else:
        _render_recommendation(st.session_state.recommendation)


if __name__ == "__main__":
    main()
