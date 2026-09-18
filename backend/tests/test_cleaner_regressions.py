import unittest

import pandas as pd

from app.services.etl.cleaner import DataCleaner


class CleanerRegressionTests(unittest.TestCase):
    def setUp(self):
        self.cleaner = DataCleaner()

    def test_large_bank_assets_are_not_rescaled(self):
        total_assets = 53_480_000_000_000
        raw = pd.DataFrame(
            {
                "REPORT_DATE": ["2025-12-31"],
                "TOTAL_ASSETS": [total_assets],
                "TOTAL_LIABILITIES": [48_000_000_000_000],
                "TOTAL_EQUITY": [5_480_000_000_000],
                "TOTAL_CURRENT_LIAB": [None],
                "TOTAL_CURRENT_LIABILITIES": [1_230_000_000_000],
            }
        )

        cleaned = self.cleaner.clean_balance_sheet(raw, "601398")

        self.assertEqual(cleaned.loc[0, "total_assets"], total_assets)
        self.assertEqual(cleaned.loc[0, "current_liabilities"], 1_230_000_000_000)
        self.assertEqual(list(cleaned.columns).count("current_liabilities"), 1)

    def test_duplicate_cashflow_aliases_are_coalesced(self):
        raw = pd.DataFrame(
            {
                "REPORT_DATE": ["2025-06-30", "2025-12-31"],
                "NETCASH_INVEST": [None, 100.0],
                "INVEST_NETCASH_BALANCE": [-50.0, None],
            }
        )

        cleaned = self.cleaner.clean_cash_flow(raw, "601398")

        self.assertEqual(cleaned["net_investing_cashflow"].tolist(), [-50.0, 100.0])
        self.assertEqual(list(cleaned.columns).count("net_investing_cashflow"), 1)

    def test_report_cashflow_capex_field_is_mapped(self):
        raw = pd.DataFrame(
            {
                "REPORT_DATE": ["2025-12-31"],
                "NETCASH_OPERATE": [61_522_204_989.35],
                "CONSTRUCT_LONG_ASSET": [3_127_594_916.41],
            }
        )

        cleaned = self.cleaner.clean_cash_flow(raw, "600519")

        self.assertEqual(cleaned.loc[0, "capital_expenditure"], 3_127_594_916.41)


if __name__ == "__main__":
    unittest.main()
