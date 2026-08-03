"""Loader and typed representation for the simulated MVP catalogue."""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "data" / "mvp" / "product_catalog.csv"

REQUIRED_CATALOG_FIELDS = {
    "product_id",
    "product_name",
    "category",
    "subcategory",
    "brand",
    "price",
    "discounted_price",
    "rating",
    "rating_count",
    "trust_signal",
    "description",
    "pairs_with",
}


@dataclass(frozen=True)
class Product:
    product_id: str
    product_name: str
    category: str
    subcategory: str
    brand: str
    price: float
    discounted_price: float
    rating: float
    rating_count: int
    trust_signal: str
    description: str
    pairs_with: tuple[str, ...]

    @property
    def discount_percent(self) -> int:
        if self.price <= 0 or self.discounted_price >= self.price:
            return 0
        return round((self.price - self.discounted_price) / self.price * 100)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["pairs_with"] = list(self.pairs_with)
        data["discount_percent"] = self.discount_percent
        return data


def load_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> tuple[Product, ...]:
    """Load and validate the simulated catalogue from CSV."""

    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalogue not found: {catalog_path}")

    with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED_CATALOG_FIELDS - fields
        if missing:
            raise ValueError(f"Catalogue is missing fields: {sorted(missing)}")

        products = []
        seen_ids = set()
        for row_number, row in enumerate(reader, start=2):
            product_id = (row.get("product_id") or "").strip()
            if not product_id:
                raise ValueError(f"Catalogue row {row_number} has no product_id")
            if product_id in seen_ids:
                raise ValueError(f"Duplicate product_id in catalogue: {product_id}")
            seen_ids.add(product_id)

            price = float(row["price"])
            discounted_price = float(row["discounted_price"])
            rating = float(row["rating"])
            rating_count = int(row["rating_count"])
            if discounted_price > price:
                raise ValueError(f"Discounted price exceeds price for {product_id}")
            if not 0 <= rating <= 5:
                raise ValueError(f"Rating out of range for {product_id}")
            if rating_count < 0:
                raise ValueError(f"Negative rating count for {product_id}")

            products.append(
                Product(
                    product_id=product_id,
                    product_name=row["product_name"].strip(),
                    category=row["category"].strip(),
                    subcategory=row["subcategory"].strip(),
                    brand=row["brand"].strip(),
                    price=price,
                    discounted_price=discounted_price,
                    rating=rating,
                    rating_count=rating_count,
                    trust_signal=row["trust_signal"].strip(),
                    description=row["description"].strip(),
                    pairs_with=tuple(
                        item.strip().lower()
                        for item in row["pairs_with"].split(";")
                        if item.strip()
                    ),
                )
            )

    if not products:
        raise ValueError("Catalogue is empty")
    return tuple(products)


def catalog_by_id(catalog: tuple[Product, ...]) -> dict[str, Product]:
    return {product.product_id: product for product in catalog}
