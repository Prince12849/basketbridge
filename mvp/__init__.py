"""AI-native category discovery MVP package.

The package contains demo-only shopper profiles and catalogue data for the
"Worth Trying With Your Order" prototype. It is intentionally separate from
the existing research pipeline.
"""

from .profiles import PROFILES, ShopperProfile, get_profile

__all__ = ["PROFILES", "ShopperProfile", "get_profile"]
