"""Simulated shopper profiles for the category discovery MVP.

These profiles are fictional demo personas. They do not represent real
Blinkit customers or production customer data.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ShopperProfile:
    """A fictional shopper context used by the MVP recommendation flow."""

    profile_id: str
    profile_name: str
    description: str
    shopping_behavior: tuple[str, ...]
    previously_purchased_categories: tuple[str, ...]
    purchase_history: tuple[str, ...]
    default_cart: tuple[str, ...]
    primary_confidence_trigger: str
    urgency_level: str
    discovery_receptivity: str


PROFILES: tuple[ShopperProfile, ...] = (
    ShopperProfile(
        profile_id="routine_restocker",
        profile_name="Routine Restocker",
        description=(
            "A frequent shopper who completes familiar missions quickly and "
            "rarely browses beyond known categories."
        ),
        shopping_behavior=(
            "Frequently replenishes groceries and snacks",
            "Usually starts with Search or Previous Orders",
            "Keeps a narrow category mix",
            "Open to discovery when it fits the current mission",
        ),
        previously_purchased_categories=(
            "Groceries",
            "Snacks & Beverages",
        ),
        purchase_history=(
            "Milk",
            "Whole Wheat Bread",
            "Farm Eggs (6 pack)",
            "Classic Potato Chips",
            "Sparkling Cola",
            "Long Grain Rice",
            "Chakki Atta",
        ),
        default_cart=(
            "P002",  # Whole Wheat Bread
            "P008",  # Cheddar Cheese
            "P004",  # Classic Potato Chips
        ),
        primary_confidence_trigger="Contextual relevance",
        urgency_level="Medium",
        discovery_receptivity="Medium",
    ),
    ShopperProfile(
        profile_id="deal_sensitive_restocker",
        profile_name="Deal-Sensitive Restocker",
        description=(
            "A regular shopper who checks Offers and experiments when the "
            "financial risk of trying something new feels low."
        ),
        shopping_behavior=(
            "Restocks familiar grocery and snack staples",
            "Checks Offers before adding unfamiliar products",
            "Compares prices and responds to visible savings",
            "More receptive to a discounted trial than an unexplained suggestion",
        ),
        previously_purchased_categories=(
            "Groceries",
            "Snacks & Beverages",
        ),
        purchase_history=(
            "Milk",
            "Whole Wheat Bread",
            "Farm Eggs (6 pack)",
            "Classic Potato Chips",
            "Sparkling Cola",
            "Oat Cookies",
            "Salted Peanuts",
        ),
        default_cart=(
            "P001",  # Milk
            "P002",  # Whole Wheat Bread
            "P004",  # Classic Potato Chips
        ),
        primary_confidence_trigger="Discount / attractive price",
        urgency_level="Low",
        discovery_receptivity="High when discounted",
    ),
    ShopperProfile(
        profile_id="urgency_shopper",
        profile_name="Urgency Shopper",
        description=(
            "A high-intent shopper who opens quick commerce to solve an "
            "immediate need and wants to check out with minimal friction."
        ),
        shopping_behavior=(
            "Searches directly for a known product",
            "Has very low browsing intent during urgent missions",
            "Prioritizes speed over exploration",
            "Should usually be protected from additional discovery friction",
        ),
        previously_purchased_categories=(
            "Groceries",
            "Snacks & Beverages",
        ),
        purchase_history=(
            "Milk",
            "Whole Wheat Bread",
            "Farm Eggs (6 pack)",
            "Classic Potato Chips",
            "Sparkling Cola",
        ),
        default_cart=(
            "P001",  # Milk
            "P003",  # Farm Eggs (6 pack)
            "P002",  # Whole Wheat Bread
        ),
        primary_confidence_trigger="Fast checkout / low friction",
        urgency_level="High",
        discovery_receptivity="Very low",
    ),
    ShopperProfile(
        profile_id="trust_first_shopper",
        profile_name="Trust-First Shopper",
        description=(
            "A risk-sensitive shopper who needs a familiar brand, strong "
            "ratings, and enough product information before experimenting."
        ),
        shopping_behavior=(
            "Searches for known brands or product names",
            "Looks at ratings and reviews before trying something unfamiliar",
            "Prefers clear product information and trusted brands",
            "Can explore when social proof reduces uncertainty",
        ),
        previously_purchased_categories=(
            "Groceries",
            "Snacks & Beverages",
        ),
        purchase_history=(
            "DailyDairy Full-Cream Milk",
            "Harvest Whole Wheat Bread",
            "Farm Eggs (6 pack)",
            "CrispCo Classic Potato Chips",
            "FizzUp Sparkling Cola",
        ),
        default_cart=(
            "P002",  # Whole Wheat Bread
            "P008",  # Cheddar Cheese
            "P004",  # Classic Potato Chips
        ),
        primary_confidence_trigger="Trust / ratings and reviews",
        urgency_level="Low",
        discovery_receptivity="Medium with strong social proof",
    ),
)


_PROFILES_BY_ID = {profile.profile_id: profile for profile in PROFILES}


def get_profile(profile_id: str) -> ShopperProfile:
    """Return a simulated shopper profile by ID."""

    try:
        return _PROFILES_BY_ID[profile_id]
    except KeyError as exc:
        valid_ids = ", ".join(sorted(_PROFILES_BY_ID))
        raise ValueError(
            f"Unknown shopper profile '{profile_id}'. Valid IDs: {valid_ids}"
        ) from exc
