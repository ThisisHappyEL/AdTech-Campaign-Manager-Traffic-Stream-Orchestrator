import unittest
from app.services.weight_calc import recalculate_stream_weights


class TestWeightCalculator(unittest.TestCase):

    def test_equal_split_with_remainder(self):
        """3 активных оффера делят 100% -> 34, 33, 33."""
        offers = [
            {"offer_id": 1, "share": 0, "is_pinned": False, "status": "active"},
            {"offer_id": 2, "share": 0, "is_pinned": False, "status": "active"},
            {"offer_id": 3, "share": 0, "is_pinned": False, "status": "active"},
        ]
        res = recalculate_stream_weights(offers)
        shares = [o["share"] for o in res]
        self.assertEqual(shares, [34, 33, 33])
        self.assertEqual(sum(shares), 100)

    def test_pinned_offer_preserves_weight(self):
        """Один оффер запинен на 25%, остальные 3 делят 75% поровну (по 25%)."""
        offers = [
            {"offer_id": 1, "share": 25, "is_pinned": True, "status": "active"},
            {"offer_id": 2, "share": 50, "is_pinned": False, "status": "active"},
            {"offer_id": 3, "share": 25, "is_pinned": False, "status": "active"},
            {"offer_id": 4, "share": 0, "is_pinned": False, "status": "active"},
        ]
        res = recalculate_stream_weights(offers)
        self.assertEqual(res[0]["share"], 25)
        self.assertEqual([o["share"] for o in res[1:]], [25, 25, 25])
        self.assertEqual(sum(o["share"] for o in res), 100)

    def test_removed_offer_gets_zero_weight(self):
        """Удаленный оффер получает 0%, оставшиеся 2 делят 100% пополам."""
        offers = [
            {"offer_id": 1, "share": 34, "is_pinned": False, "status": "removed"},
            {"offer_id": 2, "share": 33, "is_pinned": False, "status": "active"},
            {"offer_id": 3, "share": 33, "is_pinned": False, "status": "active"},
        ]
        res = recalculate_stream_weights(offers)
        self.assertEqual(res[0]["share"], 0)
        self.assertEqual(res[1]["share"], 50)
        self.assertEqual(res[2]["share"], 50)


if __name__ == "__main__":
    unittest.main()