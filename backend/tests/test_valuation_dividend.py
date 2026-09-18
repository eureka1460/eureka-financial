import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import FinancialStatement, Stock
from app.core.exceptions import ValuationParameterError
from app.schemas.valuation import DCFRequest, DDMRequest
from app.services.valuation import ValuationEngine


class DividendAutofillTests(unittest.TestCase):
    def setUp(self):
        self.db_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.db_engine)
        self.session = sessionmaker(bind=self.db_engine, expire_on_commit=False)()
        self.session.add(Stock(symbol="601398", name="工商银行", market="SH"))
        self.session.add_all(
            [
                FinancialStatement(
                    symbol="601398",
                    report_date=date(2026, 6, 30),
                    report_type="semi_annual",
                    fiscal_year=2026,
                    basic_eps=0.47,
                    paid_in_capital=1_256_197_800,
                    total_assets=309_050_784_569.31,
                    total_equity=262_096_352_174.36,
                ),
                FinancialStatement(
                    symbol="601398",
                    report_date=date(2025, 12, 31),
                    report_type="annual",
                    fiscal_year=2025,
                    basic_eps=1.00,
                ),
            ]
        )
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.db_engine.dispose()

    def test_dividend_estimate_uses_latest_annual_eps(self):
        value, source = ValuationEngine(self.session)._auto_fill_dividend("601398")

        self.assertEqual(source, "estimated")
        self.assertEqual(value, 0.3)

    def test_total_shares_prefers_paid_in_capital_over_eps_estimate(self):
        value = ValuationEngine(self.session)._auto_fill_total_shares("601398")

        self.assertEqual(value, 1_256_197_800)

    def test_wacc_does_not_treat_operating_liabilities_as_debt(self):
        wacc, detail = ValuationEngine(self.session)._auto_fill_wacc("601398")

        self.assertEqual(detail.debt_weight, 0.0)
        self.assertEqual(detail.equity_weight, 1.0)
        self.assertEqual(wacc, 0.08)

    def test_dcf_rejects_non_positive_base_fcf(self):
        request = DCFRequest(
            symbol="600519",
            fcf_base=-1,
            total_shares=1_252_270_215,
            net_debt=0,
            wacc=0.09,
        )

        with self.assertRaises(ValuationParameterError):
            ValuationEngine(self.session).calculate_dcf(request)

    def test_ddm_rejects_non_positive_dividend(self):
        request = DDMRequest(symbol="601398", d0=0)

        with self.assertRaises(ValuationParameterError):
            ValuationEngine(self.session).calculate_ddm(request)


if __name__ == "__main__":
    unittest.main()
