import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import FinancialIndicator, FinancialStatement, Stock
from app.schemas.screener import FilterCondition, ScreenerRequest
from app.services.screener import ScreenerEngine


class ScreenerRecentPeriodsTests(unittest.TestCase):
    def setUp(self):
        self.db_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.db_engine)
        self.session = sessionmaker(bind=self.db_engine)()
        for symbol in ("000001", "000002", "000003", "000004", "000005"):
            self.session.add(Stock(symbol=symbol, name=symbol, market="SZ"))

        # 旧年达标但最新年不达标；仅最近一年达标；连续两年达标；
        # 最新值缺失；以及只有一份年报。
        annual_roes = {
            "000001": (0.20, 0.10),
            "000002": (0.10, 0.20),
            "000003": (0.20, 0.20),
            "000004": (0.20, None),
            "000005": (None, 0.20),
        }
        for symbol, (old_roe, recent_roe) in annual_roes.items():
            periods = [(2025, recent_roe)]
            if old_roe is not None:
                periods.append((2024, old_roe))
            for year, roe in periods:
                self.session.add(FinancialIndicator(
                    symbol=symbol,
                    report_date=date(year, 12, 31),
                    report_type="annual",
                    fiscal_year=year,
                    roe=roe,
                ))
                self.session.add(FinancialStatement(
                    symbol=symbol,
                    report_date=date(year, 12, 31),
                    report_type="annual",
                    fiscal_year=year,
                    operating_revenue=200 if roe is not None and roe >= 0.15 else 50,
                ))

        # 半年报数值不能影响年报筛选和结果展示。
        self.session.add(FinancialIndicator(
            symbol="000003", report_date=date(2026, 6, 30),
            report_type="semi_annual", fiscal_year=2026, roe=0.01,
        ))
        self.session.commit()
        self.screener = ScreenerEngine(self.session)

    def tearDown(self):
        self.session.close()
        self.db_engine.dispose()

    def test_only_the_latest_annual_report_can_satisfy_one_year(self):
        matched = self.screener._evaluate_metric_condition(
            "roe", ">=", 0.15, 1, "annual"
        )
        self.assertEqual(matched, {"000002", "000003", "000005"})

    def test_both_latest_reports_must_pass_for_two_years(self):
        matched = self.screener._evaluate_metric_condition(
            "roe", ">=", 0.15, 2, "annual"
        )
        self.assertEqual(matched, {"000003"})

    def test_statement_fields_use_the_same_recent_period_rule(self):
        matched = self.screener._evaluate_metric_condition(
            "operating_revenue", ">=", 100, 2, "annual"
        )
        self.assertEqual(matched, {"000003"})

    def test_result_values_match_the_selected_report_type(self):
        result = self.screener.search(ScreenerRequest(
            conditions=[FilterCondition(metric="roe", operator=">=", value=0.15)],
            report_type="annual",
        ))
        item = next(item for item in result["items"] if item.symbol == "000003")
        self.assertEqual(item.match_detail.latest_values["roe"], 0.20)


if __name__ == "__main__":
    unittest.main()
