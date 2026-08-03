"""Pure session helpers shared by the UI and automated tests."""

from .catalog import Product, catalog_by_id


def category_breadth(cart_ids: list[str] | tuple[str, ...], catalog: tuple[Product, ...]) -> int:
    products = catalog_by_id(catalog)
    return len({products[product_id].category for product_id in cart_ids if product_id in products})


def add_to_cart(
    cart_ids: list[str], product_id: str, catalog: tuple[Product, ...]
) -> list[str]:
    """Add one product if valid and not already in the cart."""

    products = catalog_by_id(catalog)
    if product_id not in products:
        raise ValueError(f"Cannot add unknown product: {product_id}")
    if product_id not in cart_ids:
        cart_ids.append(product_id)
    return cart_ids


def remove_from_cart(cart_ids: list[str], product_id: str) -> list[str]:
    if product_id in cart_ids:
        cart_ids.remove(product_id)
    return cart_ids
