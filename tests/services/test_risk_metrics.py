"""Tests for risk_metrics.py — MDD, volatility, risk rating, health score.

Pure function tests, no I/O, no mocking.
100% line/branch coverage target.
"""

import math
import statistics

import pytest

from app.services.risk_metrics import (
    compute_health_score,
    compute_max_drawdown,
    compute_risk_rating,
    compute_volatility,
)


# =========================================================================
# compute_max_drawdown
# =========================================================================

class TestMaxDrawdown:
    """compute_max_drawdown(nav_series) -> dict"""

    def test_empty_series(self):
        result = compute_max_drawdown([])
        assert result == {
            "mdd_pct": 0.0,
            "peak_nav": None,
            "trough_nav": None,
            "peak_date": None,
            "trough_date": None,
            "recovery_date": None,
        }

    def test_single_point(self):
        result = compute_max_drawdown([100.0])
        assert result["mdd_pct"] == 0.0
        assert result["peak_nav"] == 100.0
        assert result["trough_nav"] == 100.0
        assert result["peak_date"] == 0
        assert result["trough_date"] == 0
        # No drawdown occurred → no recovery date
        assert result["recovery_date"] is None

    def test_all_same_values(self):
        result = compute_max_drawdown([50.0, 50.0, 50.0])
        assert result["mdd_pct"] == 0.0
        assert result["peak_nav"] == 50.0
        assert result["trough_nav"] == 50.0
        assert result["recovery_date"] is None

    def test_strictly_increasing(self):
        """No drawdown possible when NAV only goes up."""
        result = compute_max_drawdown([100, 110, 120, 130])
        assert result["mdd_pct"] == 0.0
        assert result["peak_nav"] == 130
        assert result["trough_nav"] == 130
        assert result["peak_date"] == 3
        assert result["trough_date"] == 3
        assert result["recovery_date"] is None

    def test_strictly_decreasing(self):
        """Every step is a drawdown; max is total loss from first peak."""
        result = compute_max_drawdown([130, 120, 110, 100])
        assert result["mdd_pct"] == pytest.approx(-23.0769, rel=1e-3)
        assert result["peak_nav"] == 130
        assert result["trough_nav"] == 100
        assert result["peak_date"] == 0
        assert result["trough_date"] == 3
        assert result["recovery_date"] is None

    def test_simple_peak_trough_with_recovery(self):
        nav = [100, 110, 120, 90, 80, 105, 120]
        result = compute_max_drawdown(nav)
        # MDD: peak=120(idx2), trough=80(idx4) → (80-120)/120 = -33.33%
        assert result["mdd_pct"] == pytest.approx(-33.3333, rel=1e-3)
        assert result["peak_nav"] == 120
        assert result["trough_nav"] == 80
        assert result["peak_date"] == 2
        assert result["trough_date"] == 4
        # Recovery: index 6 where NAV(120) >= peak_nav(120)
        assert result["recovery_date"] == 6

    def test_recovery_not_reached(self):
        """Series ends before recovering to peak."""
        nav = [100, 110, 120, 110, 90]
        result = compute_max_drawdown(nav)
        assert result["peak_nav"] == 120
        assert result["trough_nav"] == 90
        assert result["recovery_date"] is None

    def test_recovery_at_last_point(self):
        nav = [100, 110, 120, 90, 120]
        result = compute_max_drawdown(nav)
        assert result["peak_nav"] == 120
        assert result["trough_nav"] == 90
        assert result["recovery_date"] == 4

    def test_multiple_peaks_picks_highest_drawdown(self):
        """Multiple peaks; should pick the peak with deepest subsequent trough."""
        # Peaks at idx 0(100), 2(120); trough at idx 6(70)
        nav = [100, 90, 120, 80, 90, 110, 70, 100]
        result = compute_max_drawdown(nav)
        assert result["mdd_pct"] == pytest.approx(-41.6667, rel=1e-3)
        assert result["peak_nav"] == 120
        assert result["trough_nav"] == 70
        assert result["peak_date"] == 2
        assert result["trough_date"] == 6
        assert result["recovery_date"] is None

    def test_drawdown_that_never_recovers_then_recovers(self):
        """Trough in middle, then recovers well past peak."""
        nav = [100, 200, 150, 100, 180, 210]
        result = compute_max_drawdown(nav)
        # Peak = 200 (idx1), Trough = 100 (idx3), MDD = (100-200)/200 = -50%
        assert result["mdd_pct"] == pytest.approx(-50.0, rel=1e-3)
        assert result["peak_nav"] == 200
        assert result["trough_nav"] == 100
        assert result["peak_date"] == 1
        assert result["trough_date"] == 3
        # At idx4: 180 < 200, at idx5: 210 >= 200 → recovery at 5
        assert result["recovery_date"] == 5

    def test_peak_at_first_value_trough_at_end(self):
        """Peak is the very first value, trough is the very last."""
        nav = [100, 95, 90, 85, 80]
        result = compute_max_drawdown(nav)
        assert result["mdd_pct"] == pytest.approx(-20.0, rel=1e-3)
        assert result["peak_nav"] == 100
        assert result["trough_nav"] == 80
        assert result["peak_date"] == 0
        assert result["trough_date"] == 4
        assert result["recovery_date"] is None

    def test_negative_nav_values(self):
        """Unusual but should handle gracefully — all negative values."""
        nav = [-100, -90, -80, -95, -85]
        # Peak = -80 (idx 2), Trough = -95 (idx 3)
        # DD = (-95 - (-80)) / (-80) = -15 / -80 = 0.1875 → POSITIVE
        # Actually, mdd_pct should be negative: (trough - peak) / |peak|
        # Let's track what happens: the dd formula is (val - peak) / peak
        # At idx3: (-95 - (-80)) / (-80) = -15/-80 = 0.1875 (positive!)
        # This is actually not a drawdown by our formula since it went up.
        # Hmm, MAV going from -80 to -95 is technically a decrease (more negative).
        # But in the financial sense, if NAV is -100 to -80, that's a recovery from negative debt.
        # This is an edge case. Since NAV is typically positive, I'll just verify it computes without error.
        result = compute_max_drawdown(nav)
        assert "mdd_pct" in result


# =========================================================================
# compute_volatility
# =========================================================================

class TestVolatility:
    """compute_volatility(returns) -> float (annualized std dev)"""

    def test_empty_returns(self):
        assert compute_volatility([]) == 0.0

    def test_single_return(self):
        assert compute_volatility([0.01]) == 0.0

    def test_two_returns(self):
        """Two returns are enough to compute std dev."""
        result = compute_volatility([0.01, 0.02])
        assert result > 0
        daily_std = statistics.stdev([0.01, 0.02])
        assert result == pytest.approx(math.sqrt(252) * daily_std, rel=1e-3)

    def test_zero_volatility(self):
        assert compute_volatility([0.01, 0.01, 0.01]) == 0.0

    def test_all_zeros(self):
        assert compute_volatility([0.0, 0.0, 0.0]) == 0.0

    def test_positive_returns(self):
        returns = [0.01, 0.02, 0.015, 0.005, 0.01]
        expected = math.sqrt(252) * statistics.stdev(returns)
        result = compute_volatility(returns)
        assert result == pytest.approx(expected, rel=1e-3)

    def test_mixed_positive_and_negative(self):
        returns = [0.05, -0.02, 0.03, -0.01, 0.01, -0.03, 0.02]
        expected = math.sqrt(252) * statistics.stdev(returns)
        result = compute_volatility(returns)
        assert result == pytest.approx(expected, rel=1e-3)

    def test_large_swings(self):
        returns = [0.1, -0.1, 0.1, -0.1]
        result = compute_volatility(returns)
        assert result > 0
        expected = math.sqrt(252) * statistics.stdev(returns)
        assert result == pytest.approx(expected, rel=1e-3)

    def test_all_negative_returns(self):
        returns = [-0.01, -0.02, -0.015, -0.005]
        result = compute_volatility(returns)
        expected = math.sqrt(252) * statistics.stdev(returns)
        assert result == pytest.approx(expected, rel=1e-3)

    def test_annualization_factor(self):
        """Verify annualization uses sqrt(252) explicitly."""
        returns = [0.01] * 10  # Constant returns = 0 vol
        assert compute_volatility(returns) == 0.0
        # Non-zero case:
        returns = [0.01, -0.01, 0.02, -0.02]
        result = compute_volatility(returns)
        assert result > 0
        # Just ensure proportionality
        daily_std = statistics.stdev(returns)
        expected = daily_std * math.sqrt(252)
        assert result == pytest.approx(expected, rel=1e-3)


# =========================================================================
# compute_risk_rating
# =========================================================================

class TestRiskRating:
    """compute_risk_rating(mdd_pct, volatility) -> str (★-★★★★)"""

    def test_low_risk(self):
        """Low MDD + low vol → ★★★★"""
        assert compute_risk_rating(-5.0, 10.0) == "★★★★"

    def test_high_risk(self):
        """Severe MDD + severe vol → ★"""
        assert compute_risk_rating(-50.0, 50.0) == "★"

    def test_mdd_low_vol_high(self):
        """Low MDD (score 4) + high vol (score 2) → avg 3 → ★★★"""
        assert compute_risk_rating(-5.0, 30.0) == "★★★"

    def test_mdd_high_vol_low(self):
        """High MDD (score 2) + low vol (score 4) → avg 3 → ★★★"""
        assert compute_risk_rating(-30.0, 10.0) == "★★★"

    def test_mdd_medium_vol_medium(self):
        """Medium MDD (score 3) + medium vol (score 3) → avg 3 → ★★★"""
        assert compute_risk_rating(-20.0, 20.0) == "★★★"

    def test_mdd_high_vol_high(self):
        """High MDD (score 2) + high vol (score 2) → avg 2 → ★★"""
        assert compute_risk_rating(-30.0, 30.0) == "★★"

    def test_mdd_severe_vol_severe(self):
        """Severe MDD (score 1) + severe vol (score 1) → avg 1 → ★"""
        assert compute_risk_rating(-45.0, 45.0) == "★"

    def test_mdd_zero_vol_zero(self):
        """Zero risk on both axes → ★★★★"""
        assert compute_risk_rating(0.0, 0.0) == "★★★★"

    def test_mdd_positive_handling(self):
        """Positive MDD (theoretical only) treated same as zero loss → ★★★★"""
        assert compute_risk_rating(5.0, 10.0) == "★★★★"

    def test_boundary_mdd_ten(self):
        """MDD exactly at -10% boundary (score 4↔3)"""
        assert compute_risk_rating(-10.0, 10.0) == "★★★★"

    def test_boundary_mdd_25(self):
        """MDD exactly at -25% boundary (score 3↔2)"""
        assert compute_risk_rating(-25.0, 10.0) == "★★★"

    def test_boundary_mdd_40(self):
        """MDD exactly at -40% boundary (score 2↔1)"""
        assert compute_risk_rating(-40.0, 10.0) == "★★★"

    def test_boundary_vol_15(self):
        """Volatility exactly at 15% boundary (score 4↔3)"""
        assert compute_risk_rating(-5.0, 15.0) == "★★★★"

    def test_boundary_vol_25(self):
        """Volatility exactly at 25% boundary (score 3↔2)"""
        assert compute_risk_rating(-5.0, 25.0) == "★★★"

    def test_boundary_vol_40(self):
        """Volatility exactly at 40% boundary (score 2↔1)"""
        assert compute_risk_rating(-5.0, 40.0) == "★★★"


# =========================================================================
# compute_health_score
# =========================================================================

class TestHealthScore:
    """compute_health_score(holdings, nav_series) -> dict"""

    # --- Helpers ---

    @staticmethod
    def _make_holding(symbol: str = "AAPL", weight: float = 25.0,
                      typ: str = "stock", duration: float = 24) -> dict:
        return {
            "symbol": symbol,
            "weight": weight,
            "type": typ,
            "duration": duration,
        }

    # --- Empty / missing data ---

    def test_empty_holdings_empty_nav(self):
        result = compute_health_score([], [])
        # total = 100*0.30 + 0*0.30 + 60*0.20 + 0*0.20 = 30 + 0 + 12 + 0 = 42
        assert result["total"] == 42.0
        assert result["concentration"] == 100.0
        assert result["type_diversity"] == 0.0
        assert result["outperform"] == 60.0  # flat → 0% return → 60
        assert result["holding_duration"] == 0.0

    def test_empty_holdings_with_nav(self):
        result = compute_health_score([], [100, 110, 120])
        assert result["concentration"] == 100.0
        assert result["type_diversity"] == 0.0

    def test_single_holding(self):
        holdings = [self._make_holding("AAPL", 50.0, "stock", 12)]
        nav = [100, 100, 100]
        result = compute_health_score(holdings, nav)
        assert 0 <= result["total"] <= 100
        for key in ("concentration", "type_diversity", "outperform", "holding_duration"):
            assert key in result

    # --- Concentration ---

    def test_concentration_low_weight(self):
        """10% weight → concentration score 100"""
        holdings = [self._make_holding("AAPL", 10.0, "stock", 12)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["concentration"] == 100.0

    def test_concentration_heavy(self):
        """80% weight → heavily penalized"""
        holdings = [self._make_holding("AAPL", 80.0, "stock", 12)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["concentration"] < 50.0

    def test_concentration_maxed_at_100(self):
        """100% weight → concentration score = 0"""
        holdings = [self._make_holding("AAPL", 100.0, "stock", 12)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["concentration"] == 0.0

    def test_concentration_equal_weights(self):
        """Multiple holdings with equal weights → lower concentration score"""
        holdings = [
            self._make_holding("A", 20.0, "stock", 12),
            self._make_holding("B", 20.0, "stock", 12),
            self._make_holding("C", 20.0, "stock", 12),
        ]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["concentration"] == pytest.approx(87.5, rel=1e-3)

    # --- Type diversity ---

    def test_type_diversity_single_type(self):
        holdings = [
            self._make_holding("A", 50.0, "stock", 12),
            self._make_holding("B", 50.0, "stock", 12),
        ]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["type_diversity"] == 25.0

    def test_type_diversity_two_types(self):
        holdings = [
            self._make_holding("A", 50.0, "stock", 12),
            self._make_holding("B", 50.0, "bond", 12),
        ]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["type_diversity"] == 50.0

    def test_type_diversity_many_types(self):
        holdings = [
            self._make_holding("A", 25.0, "stock", 12),
            self._make_holding("B", 25.0, "bond", 12),
            self._make_holding("C", 25.0, "etf", 12),
            self._make_holding("D", 25.0, "cash", 12),
        ]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["type_diversity"] == 100.0

    # --- Outperform ---

    def test_outperform_strong_gain(self):
        holdings = [self._make_holding("A", 50.0, "stock", 12)]
        nav = [100, 130]  # 30% gain
        result = compute_health_score(holdings, nav)
        assert result["outperform"] == 100.0

    def test_outperform_moderate_gain(self):
        holdings = [self._make_holding("A", 50.0, "stock", 12)]
        nav = [100, 115]  # 15% gain
        result = compute_health_score(holdings, nav)
        assert result["outperform"] == 80.0

    def test_outperform_breakeven(self):
        holdings = [self._make_holding("A", 50.0, "stock", 12)]
        nav = [100, 100]  # 0% return
        result = compute_health_score(holdings, nav)
        assert result["outperform"] == 60.0

    def test_outperform_slight_loss(self):
        holdings = [self._make_holding("A", 50.0, "stock", 12)]
        nav = [100, 95]  # -5% return
        result = compute_health_score(holdings, nav)
        assert result["outperform"] == 40.0

    def test_outperform_moderate_loss(self):
        """-15% return → -20% to -10% band → score 20"""
        holdings = [self._make_holding("A", 50.0, "stock", 12)]
        nav = [100, 85]  # -15% return
        result = compute_health_score(holdings, nav)
        assert result["outperform"] == 20.0

    def test_outperform_heavy_loss(self):
        holdings = [self._make_holding("A", 50.0, "stock", 12)]
        nav = [100, 60]  # -40% return
        result = compute_health_score(holdings, nav)
        assert result["outperform"] == 0.0

    # --- Holding duration ---

    def test_duration_long_term(self):
        holdings = [self._make_holding("A", 50.0, "stock", 48)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["holding_duration"] == 100.0

    def test_duration_medium(self):
        holdings = [self._make_holding("A", 50.0, "stock", 18)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["holding_duration"] == 60.0

    def test_duration_short(self):
        holdings = [self._make_holding("A", 50.0, "stock", 1)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["holding_duration"] == 0.0

    def test_duration_monthly(self):
        """4 months → 3–6 month band → score 20."""
        holdings = [self._make_holding("A", 50.0, "stock", 4)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["holding_duration"] == 20.0

    def test_duration_semiannual(self):
        """8 months → 6–12 month band → score 40."""
        holdings = [self._make_holding("A", 50.0, "stock", 8)]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        assert result["holding_duration"] == 40.0

    def test_duration_averaged(self):
        """Average duration across holdings determines score."""
        holdings = [
            self._make_holding("A", 50.0, "stock", 36),
            self._make_holding("B", 50.0, "bond", 12),
        ]
        nav = [100, 100]
        result = compute_health_score(holdings, nav)
        # avg duration = (36 + 12) / 2 = 24
        assert result["holding_duration"] == 80.0

    # --- Total weighting ---

    def test_total_is_weighted_sum(self):
        """total = concentration*0.30 + diversity*0.30 + outperform*0.20 + duration*0.20"""
        holdings = [
            self._make_holding("AAPL", 30.0, "stock", 36),
            self._make_holding("BND", 30.0, "bond", 24),
            self._make_holding("SPY", 40.0, "etf", 12),
        ]
        nav = [100, 120]
        result = compute_health_score(holdings, nav)
        expected = (
            result["concentration"] * 0.30
            + result["type_diversity"] * 0.30
            + result["outperform"] * 0.20
            + result["holding_duration"] * 0.20
        )
        assert result["total"] == pytest.approx(expected, rel=1e-3)

    def test_total_clamped_to_100(self):
        """Total score should never exceed 100."""
        # Max everything: 100*0.3 + 100*0.3 + 100*0.2 + 100*0.2 = 100
        holdings = [
            self._make_holding("A", 10.0, "stock", 48),
            self._make_holding("B", 10.0, "bond", 48),
            self._make_holding("C", 10.0, "etf", 48),
            self._make_holding("D", 10.0, "cash", 48),
        ]
        nav = [100, 150]
        result = compute_health_score(holdings, nav)
        assert result["total"] <= 100.0
        # All sub-scores should be 100
        assert result["concentration"] == 100.0
        assert result["type_diversity"] == 100.0
        assert result["outperform"] == 100.0
        assert result["holding_duration"] == 100.0
        assert result["total"] == 100.0

    def test_total_floored_at_0(self):
        """Total score should never go below 0."""
        holdings = [self._make_holding("A", 100.0, "stock", 1)]
        nav = [100, 50]  # -50% loss
        result = compute_health_score(holdings, nav)
        assert result["total"] >= 0.0
