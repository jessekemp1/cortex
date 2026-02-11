"""Shared test helpers for standalone Pupil tests."""

from pupil.schemas import CustomerProfile


def make_profile(
    profile_id: str = "test-001",
    segment: str = "mass_market",
    age: int = 35,
    province: str = "ON",
    credit_score: int = 720,
    annual_income: float = 65000.0,
    total_deposits: float = 25000.0,
    tenure_years: float = 5.0,
    products: list | None = None,
) -> CustomerProfile:
    """Factory for test CustomerProfiles using Pupil's vendored type."""
    return CustomerProfile(
        profile_id=profile_id,
        age=age,
        province=province,
        fsa="M5V",
        segment=segment,
        annual_income=annual_income,
        household_income=annual_income * 1.5,
        credit_score=credit_score,
        products_held=products or ["chequing", "savings"],
        total_deposits=total_deposits,
        total_credit_outstanding=5000.0,
        digital_adoption="hybrid",
        primary_channel="mobile",
        tenure_years=tenure_years,
        products_per_household=2,
    )


def make_profiles(n: int = 50, segment: str = "mass_market") -> list[CustomerProfile]:
    """Create n profiles of a given segment."""
    return [make_profile(profile_id=f"{segment}-{i}", segment=segment) for i in range(n)]


def make_mixed_profiles(n: int = 75) -> list[CustomerProfile]:
    """Create a mixed-segment population for realistic testing."""
    profiles = []
    segments = [
        ("mass_market", int(n * 0.40)),
        ("mass_affluent", int(n * 0.20)),
        ("new_to_canada", int(n * 0.13)),
        ("affluent", int(n * 0.10)),
        ("small_business", int(n * 0.07)),
        ("high_net_worth", int(n * 0.05)),
    ]
    allocated = sum(count for _, count in segments)
    if allocated < n:
        segments[0] = ("mass_market", segments[0][1] + (n - allocated))

    idx = 0
    segment_configs = {
        "mass_market": {"credit_score": 700, "income": 60000, "deposits": 20000},
        "mass_affluent": {"credit_score": 740, "income": 110000, "deposits": 75000},
        "new_to_canada": {"credit_score": 640, "income": 50000, "deposits": 10000},
        "affluent": {"credit_score": 770, "income": 250000, "deposits": 200000},
        "small_business": {"credit_score": 710, "income": 85000, "deposits": 45000},
        "high_net_worth": {"credit_score": 800, "income": 400000, "deposits": 500000},
    }

    for seg, count in segments:
        cfg = segment_configs[seg]
        for _ in range(count):
            profiles.append(make_profile(
                profile_id=f"mix-{idx:03d}",
                segment=seg,
                credit_score=cfg["credit_score"],
                annual_income=cfg["income"],
                total_deposits=cfg["deposits"],
            ))
            idx += 1

    return profiles
