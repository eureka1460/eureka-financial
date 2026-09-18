import unittest

from app.services.etl.loader import (
    calculate_free_cash_flow,
    normalize_ths_indicator_value,
)


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

    def test_fcf_subtracts_capex_not_net_investing_cashflow(self):
        self.assertAlmostEqual(
            calculate_free_cash_flow(61_522_204_989.35, 3_127_594_916.41),
            58_394_610_072.94,
            places=2,
        )

    def test_fcf_is_unavailable_when_capex_is_missing(self):
        self.assertIsNone(calculate_free_cash_flow(61_522_204_989.35, None))


if __name__ == "__main__":
    unittest.main()
