import unittest

from app.services.etl.loader import normalize_ths_indicator_value


class IndicatorNormalizationTests(unittest.TestCase):
    def test_negative_growth_percentage_is_scaled_once(self):
        self.assertEqual(
            normalize_ths_indicator_value("net_profit_yoy", "-112.20%"),
            -1.122,
        )

    def test_small_percentage_is_always_scaled(self):
        self.assertEqual(
            normalize_ths_indicator_value("revenue_yoy", "0.45"),
            0.0045,
        )

    def test_quick_ratio_remains_a_multiple(self):
        self.assertEqual(
            normalize_ths_indicator_value("quick_ratio", "2.48"),
            2.48,
        )

    def test_current_ratio_below_one_is_unchanged(self):
        self.assertEqual(
            normalize_ths_indicator_value("current_ratio", "0.49"),
            0.49,
        )


if __name__ == "__main__":
    unittest.main()
