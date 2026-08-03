import unittest
from types import SimpleNamespace

from mvp.catalog import load_catalog
from mvp.events import record_event
from mvp.profiles import get_profile
from mvp.recommender import recommend
from mvp.session import add_to_cart, category_breadth
from mvp.validators import validate_recommendation
from utils.llm import LLMConfigurationError


class MvpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        cls.products = {product.product_id: product for product in cls.catalog}

    def demo_fallback_recommendation(self, profile):
        def unavailable(_system, _user):
            raise LLMConfigurationError("offline test mode")

        return recommend(
            profile,
            profile.default_cart,
            self.catalog,
            llm_call=unavailable,
        )

    def test_routine_restocker_gets_contextual_new_category(self):
        profile = get_profile("routine_restocker")
        result = self.demo_fallback_recommendation(profile)

        self.assertTrue(result.show_recommendation)
        self.assertNotIn(result.new_category, profile.previously_purchased_categories)
        self.assertEqual(self.products[result.product_id].category, result.new_category)
        self.assertEqual(result.confidence_type, "contextual_relevance")
        self.assertIn("cart", result.reason.lower())

    def test_deal_sensitive_recommendation_emphasizes_discount(self):
        profile = get_profile("deal_sensitive_restocker")
        result = self.demo_fallback_recommendation(profile)

        self.assertTrue(result.show_recommendation)
        self.assertEqual(result.confidence_type, "discount")
        self.assertIn("off", result.reason.lower())

    def test_trust_first_recommendation_emphasizes_social_proof(self):
        profile = get_profile("trust_first_shopper")
        result = self.demo_fallback_recommendation(profile)

        self.assertTrue(result.show_recommendation)
        self.assertEqual(result.confidence_type, "trust_social_proof")
        self.assertIn("ratings", result.reason.lower())

    def test_urgency_shopper_can_be_suppressed(self):
        profile = get_profile("urgency_shopper")
        result = self.demo_fallback_recommendation(profile)

        self.assertFalse(result.show_recommendation)
        self.assertIsNone(result.product_id)
        self.assertIn("urgent", result.reason.lower())

    def test_valid_gemini_response_is_used(self):
        profile = get_profile("routine_restocker")
        payload = {
            "show_recommendation": True,
            "product_id": "P014",
            "new_category": "Dips & Spreads",
            "reason": "Pairs naturally with the chips already in your cart.",
            "confidence_type": "contextual_relevance",
            "confidence_message": "Highly rated accompaniment for this order.",
        }

        result = recommend(
            profile,
            profile.default_cart,
            self.catalog,
            llm_call=lambda _system, _user: payload,
        )

        self.assertTrue(result.show_recommendation)
        self.assertEqual(result.source, "gemini")
        self.assertEqual(result.product_id, "P014")

    def test_already_purchased_category_is_rejected(self):
        payload = {
            "show_recommendation": True,
            "product_id": "P001",
            "new_category": "Groceries",
            "reason": "This is relevant to the cart.",
            "confidence_type": "contextual_relevance",
            "confidence_message": "Highly rated product.",
        }
        result = validate_recommendation(
            payload,
            self.catalog,
            ("Groceries", "Snacks & Beverages"),
        )

        self.assertFalse(result.valid)
        self.assertIn("already purchased", result.error)

    def test_invalid_product_is_rejected(self):
        payload = {
            "show_recommendation": True,
            "product_id": "P999",
            "new_category": "Dips & Spreads",
            "reason": "Pairs with the current cart.",
            "confidence_type": "contextual_relevance",
            "confidence_message": "Highly rated accompaniment.",
        }
        result = validate_recommendation(payload, self.catalog, ("Groceries",))

        self.assertFalse(result.valid)
        self.assertIn("unknown product", result.error)

    def test_malformed_gemini_response_is_suppressed_without_crashing(self):
        profile = get_profile("routine_restocker")
        responses = iter([["not an object"], {"unexpected": "shape"}])
        result = recommend(
            profile,
            profile.default_cart,
            self.catalog,
            llm_call=lambda _system, _user: next(responses),
        )

        self.assertFalse(result.show_recommendation)
        self.assertEqual(result.source, "safe_fallback")
        self.assertIn("validation", result.reason.lower())

    def test_add_to_cart_updates_category_breadth(self):
        profile = get_profile("routine_restocker")
        cart = list(profile.default_cart)
        before = category_breadth(cart, self.catalog)
        add_to_cart(cart, "P014", self.catalog)
        after = category_breadth(cart, self.catalog)

        self.assertEqual(before, 2)
        self.assertEqual(after, 3)
        self.assertIn("P014", cart)

    def test_not_interested_event_is_recorded(self):
        events = []
        record_event(
            events,
            "recommendation_dismissed",
            product_id="P014",
            category="Dips & Spreads",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_name"], "recommendation_dismissed")

    def test_missing_api_key_uses_graceful_demo_fallback(self):
        profile = get_profile("routine_restocker")

        def missing_key(_system, _user):
            raise LLMConfigurationError("missing test key")

        result = recommend(
            profile,
            profile.default_cart,
            self.catalog,
            llm_call=missing_key,
        )

        self.assertTrue(result.show_recommendation)
        self.assertEqual(result.source, "demo_fallback")
        self.assertIn("missing test key", result.error)

    def test_existing_generate_json_array_contract_remains_compatible(self):
        import utils.llm as llm

        original = llm._generate_content
        try:
            llm._generate_content = lambda _system, _user: SimpleNamespace(
                text='[{"status":"working"}]'
            )
            self.assertEqual(
                llm.generate_json("system", "user"),
                [{"status": "working"}],
            )
        finally:
            llm._generate_content = original

    def test_object_parser_accepts_only_object(self):
        import utils.llm as llm

        original = llm._generate_content
        try:
            llm._generate_content = lambda _system, _user: SimpleNamespace(
                text='{"status":"working"}'
            )
            self.assertEqual(
                llm.generate_json_object("system", "user"),
                {"status": "working"},
            )
        finally:
            llm._generate_content = original


if __name__ == "__main__":
    unittest.main()
