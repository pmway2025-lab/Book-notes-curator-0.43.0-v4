"""portfolio.py 的單元測試：python3 -m unittest discover -s <此目錄>"""

import unittest

import portfolio as p


class TestEmergency(unittest.TestCase):
    def test_target(self):
        self.assertEqual(p.emergency_fund(45000, 6), 270000)

    def test_months_by_stability(self):
        self.assertEqual(p.recommended_months("stable"), 6)
        self.assertEqual(p.recommended_months("irregular"), 12)
        self.assertEqual(p.recommended_months("unknown"), 6)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            p.emergency_fund(-1, 6)


class TestTargetWeight(unittest.TestCase):
    def test_base_rule(self):
        # 110 法則、32 歲、variable 不調整、緊急金 6 個月不加減
        self.assertAlmostEqual(
            p.target_equity_weight(32, "moderate", "variable", 0, 6.0), 0.78
        )

    def test_stability_and_dependents(self):
        stable = p.target_equity_weight(40, "moderate", "stable", 0, 12.0)
        loaded = p.target_equity_weight(40, "moderate", "irregular", 2, 3.0)
        self.assertGreater(stable, loaded)

    def test_adjust_capped_at_20pp(self):
        # irregular(-10) + 2 dependents(-10) + 緊急金不足(-10) = -30 → 夾成 -20
        w = p.target_equity_weight(30, "aggressive", "irregular", 2, 1.0)
        self.assertAlmostEqual(w, (120 - 30 - 20) / 100)

    def test_short_horizon_is_zero_equity(self):
        self.assertEqual(
            p.target_equity_weight(30, "aggressive", "stable", 0, 12.0, years_to_goal=3),
            0.0,
        )

    def test_medium_horizon_capped(self):
        self.assertLessEqual(
            p.target_equity_weight(30, "aggressive", "stable", 0, 12.0, years_to_goal=7),
            0.50,
        )

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            p.target_equity_weight(0)
        with self.assertRaises(ValueError):
            p.target_equity_weight(30, "gambler")


class TestAllocationTable(unittest.TestCase):
    def test_weights_sum_to_one(self):
        rows = p.allocation_table(0.7, 1_000_000)
        self.assertAlmostEqual(sum(r["weight"] for r in rows), 1.0)
        self.assertAlmostEqual(sum(r["amount"] for r in rows), 1_000_000)

    def test_equity_capped_by_cash_floor(self):
        rows = p.allocation_table(0.95)
        self.assertAlmostEqual(rows[0]["weight"], 0.90)
        self.assertAlmostEqual(rows[1]["weight"], 0.0)


class TestRebalance(unittest.TestCase):
    def setUp(self):
        self.targets = {"股票": 0.6, "債券": 0.3, "現金": 0.1}

    def test_trades_close_the_gap(self):
        holdings = {"股票": 700000, "債券": 200000, "現金": 100000}
        rows = {r.asset: r for r in p.rebalance(holdings, self.targets)}
        self.assertAlmostEqual(rows["股票"].trade, -100000)
        self.assertAlmostEqual(rows["債券"].trade, 100000)
        self.assertAlmostEqual(rows["現金"].trade, 0)
        self.assertAlmostEqual(sum(r.trade for r in rows.values()), 0)

    def test_new_cash_included(self):
        holdings = {"股票": 600000, "債券": 300000, "現金": 100000}
        rows = {r.asset: r for r in p.rebalance(holdings, self.targets, 200000)}
        self.assertAlmostEqual(sum(r.trade for r in rows.values()), 200000)
        self.assertAlmostEqual(rows["股票"].target_amount, 720000)

    def test_missing_holding_treated_as_zero(self):
        rows = {r.asset: r for r in p.rebalance({"股票": 1000}, {"股票": 0.5, "債券": 0.5})}
        self.assertAlmostEqual(rows["債券"].trade, 500)

    def test_bad_targets_rejected(self):
        with self.assertRaises(ValueError):
            p.rebalance({"股票": 100}, {"股票": 0.9})
        with self.assertRaises(ValueError):
            p.rebalance({"股票": 100}, {"股票": 1.2, "債券": -0.2})

    def test_negative_cash_rejected(self):
        with self.assertRaises(ValueError):
            p.rebalance({"股票": 100}, {"股票": 1.0}, -5)


class TestFiveTwentyFive(unittest.TestCase):
    def test_absolute_band(self):
        self.assertTrue(p.is_triggered(0.65, 0.60))
        self.assertFalse(p.is_triggered(0.63, 0.60))

    def test_exact_band_edge_not_lost_to_float_error(self):
        # 0.30 - 0.25 在浮點下是 0.049999...，仍必須觸發
        self.assertTrue(p.is_triggered(0.30, 0.25))

    def test_relative_band_for_small_weights(self):
        # 目標 8%：相對 25% ＝ 2 個百分點先觸發
        self.assertTrue(p.is_triggered(0.10, 0.08))
        self.assertFalse(p.is_triggered(0.09, 0.08))


class TestProjection(unittest.TestCase):
    def test_zero_return_is_sum_of_contributions(self):
        self.assertAlmostEqual(p.project(100000, 10000, 10, 0.0), 100000 + 1200000)

    def test_growth_beats_contributions(self):
        self.assertGreater(p.project(0, 10000, 20, 0.065), 10000 * 12 * 20)

    def test_real_value_below_nominal(self):
        self.assertLess(p.real_value(1000000, 20), 1000000)

    def test_negative_years_rejected(self):
        with self.assertRaises(ValueError):
            p.project(0, 1000, -1, 0.05)


class TestFire(unittest.TestCase):
    def test_number(self):
        self.assertAlmostEqual(p.fire_number(720000, 0.035), 720000 / 0.035)

    def test_invalid_swr(self):
        with self.assertRaises(ValueError):
            p.fire_number(720000, 0)


class TestCheckup(unittest.TestCase):
    def base_profile(self, **kw):
        profile = {
            "age": 32,
            "monthly_income": 75000,
            "monthly_expense": 45000,
            "annual_lumpy_expense": 120000,
            "income_stability": "variable",
            "cash": 600000,
            "investments": 800000,
            "debts": [],
            "risk_profile": "moderate",
            "dependents": 0,
        }
        profile.update(kw)
        return profile

    def test_core_numbers(self):
        r = p.checkup(self.base_profile())
        self.assertAlmostEqual(r["monthly_savings"], 75000 - 45000 - 10000)
        self.assertAlmostEqual(r["savings_rate"], 20000 / 75000)
        self.assertAlmostEqual(r["net_worth"], 1_400_000)

    def test_high_rate_debt_flagged_first(self):
        r = p.checkup(self.base_profile(
            debts=[{"name": "信貸", "balance": 300000, "rate": 0.068,
                    "monthly_payment": 9000}]))
        self.assertTrue(any("信貸" in a for a in r["actions"]))
        self.assertAlmostEqual(r["net_worth"], 1_100_000)

    def test_thin_emergency_fund_flagged(self):
        r = p.checkup(self.base_profile(cash=100000))
        self.assertTrue(any("緊急預備金" in a for a in r["actions"]))

    def test_all_clear(self):
        r = p.checkup(self.base_profile(cash=1_000_000))
        self.assertEqual(len(r["actions"]), 1)
        self.assertIn("安全順序已達標", r["actions"][0])

    def test_zero_income_rejected(self):
        with self.assertRaises(ValueError):
            p.checkup(self.base_profile(monthly_income=0))


class TestCli(unittest.TestCase):
    def test_all_subcommands_exit_zero(self):
        cases = [
            ["emergency", "--expense", "45000", "--cash", "300000"],
            ["target", "--age", "32", "--total", "1000000"],
            ["project", "--initial", "500000", "--monthly", "20000", "--years", "20"],
            ["fire", "--annual-expense", "720000", "--current", "1400000",
             "--monthly", "20000"],
        ]
        for argv in cases:
            with self.subTest(cmd=argv[0]):
                self.assertEqual(p.main(argv), 0)

    def test_missing_file_returns_error_code(self):
        self.assertEqual(p.main(["checkup", "--file", "/nonexistent.json"]), 1)


if __name__ == "__main__":
    unittest.main()
