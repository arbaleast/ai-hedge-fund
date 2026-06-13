"""Financial risk metrics — pure functions.

All functions are stateless; no I/O, no API calls.
Designed for fund NAV analysis and portfolio health assessment.
"""

import math
import statistics
from typing import Any


def compute_max_drawdown(nav_series: list[float]) -> dict[str, Any]:
    """Compute maximum drawdown and its characteristics.

    Args:
        nav_series: Chronological list of NAV values (index = time step).

    Returns:
        dict with keys:
            mdd_pct:       Max drawdown as percentage (negative or 0).
            peak_nav:      NAV value at the peak before the trough.
            trough_nav:    NAV value at the trough.
            peak_date:     Index of the peak in nav_series.
            trough_date:   Index of the trough in nav_series.
            recovery_date: Index when NAV recovers to >= peak_nav, or None.
    """
    if not nav_series:
        return {
            "mdd_pct": 0.0,
            "peak_nav": None,
            "trough_nav": None,
            "peak_date": None,
            "trough_date": None,
            "recovery_date": None,
        }

    running_peak = nav_series[0]
    running_peak_date = 0

    # Tracks the worst drawdown encountered so far
    worst_mdd = 0.0  # 0 = no drawdown
    worst_peak = nav_series[0]
    worst_peak_date = 0
    worst_trough = nav_series[0]
    worst_trough_date = 0

    for i in range(1, len(nav_series)):
        val = nav_series[i]

        if val > running_peak:
            running_peak = val
            running_peak_date = i

        dd = (val - running_peak) / running_peak

        if dd < worst_mdd:
            worst_mdd = dd
            worst_peak = running_peak
            worst_peak_date = running_peak_date
            worst_trough = val
            worst_trough_date = i

    # Find recovery: first index after trough where NAV >= peak
    recovery_date: int | None = None
    if worst_mdd < 0.0:
        for i in range(worst_trough_date + 1, len(nav_series)):
            if nav_series[i] >= worst_peak:
                recovery_date = i
                break

    # When no drawdown occurred, report last point as both peak and trough
    if worst_mdd == 0.0:
        last_idx = len(nav_series) - 1
        worst_peak = nav_series[last_idx]
        worst_peak_date = last_idx
        worst_trough = nav_series[last_idx]
        worst_trough_date = last_idx

    return {
        "mdd_pct": worst_mdd * 100,  # Convert fraction to percentage
        "peak_nav": worst_peak,
        "trough_nav": worst_trough,
        "peak_date": worst_peak_date,
        "trough_date": worst_trough_date,
        "recovery_date": recovery_date,
    }


def compute_volatility(returns: list[float]) -> float:
    """Annualized volatility from a list of periodic returns.

    Assumes returns are daily; annualization factor = sqrt(252).

    Args:
        returns: List of return values (e.g., 0.01 for 1%).

    Returns:
        Annualized standard deviation as a float (0.0 if < 2 returns).
    """
    if len(returns) < 2:
        return 0.0
    daily_std = statistics.stdev(returns)
    return daily_std * math.sqrt(252)


def _mdd_score(mdd_pct: float) -> int:
    """Score 1-4 for max drawdown (lower = worse)."""
    if mdd_pct > -10.0:
        return 4
    if mdd_pct > -25.0:
        return 3
    if mdd_pct > -40.0:
        return 2
    return 1


def _vol_score(volatility: float) -> int:
    """Score 1-4 for volatility (lower = worse)."""
    if volatility < 15.0:
        return 4
    if volatility < 25.0:
        return 3
    if volatility < 40.0:
        return 2
    return 1


def compute_risk_rating(mdd_pct: float, volatility: float) -> str:
    """Combine MDD and volatility into a 4-tier star rating.

    Args:
        mdd_pct:    Max drawdown as a percentage (negative or 0).
        volatility: Annualized volatility (non-negative).

    Returns:
        "★★★★" (low risk) / "★★★" / "★★" / "★" (high risk).
    """
    s_mdd = _mdd_score(mdd_pct)
    s_vol = _vol_score(volatility)
    avg = (s_mdd + s_vol) / 2.0

    if avg >= 3.5:
        return "★★★★"
    if avg >= 2.5:
        return "★★★"
    if avg >= 1.5:
        return "★★"
    return "★"


def _score_concentration(holdings: list[dict]) -> float:
    """Score concentration risk from holding weights (higher = better)."""
    if not holdings:
        return 100.0
    max_w = max(h["weight"] for h in holdings)
    # Penalise every percentage point above a 10 % ideal.
    return max(0.0, 100.0 - (max_w - 10.0) * 1.25)


def _score_type_diversity(holdings: list[dict]) -> float:
    """Score type diversity from holding types (higher = better)."""
    unique_types = {h["type"] for h in holdings}
    return min(100.0, len(unique_types) * 25.0)


def _score_outperform(nav_series: list[float]) -> float:
    """Score how the NAV series outperformed (higher = better)."""
    if len(nav_series) < 2:
        return 60.0  # Flat / unknown → neutral
    total_return = (nav_series[-1] - nav_series[0]) / nav_series[0]
    pct = total_return * 100.0

    if pct >= 20.0:
        return 100.0
    if pct >= 10.0:
        return 80.0
    if pct >= 0.0:
        return 60.0
    if pct >= -10.0:
        return 40.0
    if pct >= -20.0:
        return 20.0
    return 0.0


def _score_holding_duration(holdings: list[dict]) -> float:
    """Score average holding duration in months (higher = better)."""
    if not holdings:
        return 0.0
    avg_dur = sum(h["duration"] for h in holdings) / len(holdings)

    if avg_dur >= 36.0:
        return 100.0
    if avg_dur >= 24.0:
        return 80.0
    if avg_dur >= 12.0:
        return 60.0
    if avg_dur >= 6.0:
        return 40.0
    if avg_dur >= 3.0:
        return 20.0
    return 0.0


def compute_health_score(
    holdings: list[dict],
    nav_series: list[float],
) -> dict[str, float]:
    """Compute a 0-100 health score from four weighted dimensions.

    Weights:
        concentration    30% — top holding weight penalty
        type_diversity   30% — variety of asset types
        outperform       20% — NAV total return performance
        holding_duration 20% — average hold period in months

    Args:
        holdings:   List of dicts with keys ``symbol``, ``weight``,
                    ``type``, ``duration``.
        nav_series: Chronological NAV values.

    Returns:
        dict with keys ``total``, ``concentration``, ``type_diversity``,
        ``outperform``, ``holding_duration``, each 0-100.
    """
    conc = _score_concentration(holdings)
    dive = _score_type_diversity(holdings)
    perf = _score_outperform(nav_series)
    dur = _score_holding_duration(holdings)

    total = conc * 0.30 + dive * 0.30 + perf * 0.20 + dur * 0.20

    return {
        "total": total,
        "concentration": conc,
        "type_diversity": dive,
        "outperform": perf,
        "holding_duration": dur,
    }
