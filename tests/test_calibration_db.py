import importlib

import pytest


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Point the db module at a throwaway SQLite file so these tests never
    touch real saved reports or calibration data."""
    monkeypatch.setenv("SITEIQ_DATA_DIR", str(tmp_path))
    import siteiq.config as config
    importlib.reload(config)
    import siteiq.core.db as db
    importlib.reload(db)
    db.init()
    yield db


def test_calibration_factor_defaults_to_one_with_no_benchmarks(isolated_db):
    factor, n = isolated_db.calibration_factor("deli")
    assert factor == 1.0
    assert n == 0


def test_calibration_factor_reflects_saved_benchmark(isolated_db):
    isolated_db.save_benchmark(label="My Store", address="1 Test St", concept="deli",
                               actual_daily_sales=6000, monthly_rent=8000, sqft=1200,
                               modeled_daily=5000, ratio=1.2, notes="")
    factor, n = isolated_db.calibration_factor("deli")
    assert n == 1
    assert factor == pytest.approx(1.2)


def test_calibration_factor_excludes_nonsense_outliers(isolated_db):
    # A ratio this extreme (actual sales 10x the model) is far more likely to
    # be a data-entry error than a real signal, so it is excluded entirely
    # rather than allowed to distort the correction.
    isolated_db.save_benchmark(label="Bad Entry", address="2 Test St", concept="deli",
                               actual_daily_sales=50000, monthly_rent=8000, sqft=1200,
                               modeled_daily=5000, ratio=10.0, notes="")
    factor, n = isolated_db.calibration_factor("deli")
    assert n == 0
    assert factor == 1.0


def test_calibration_factor_clamps_a_borderline_high_ratio(isolated_db):
    # A ratio inside the sanity window but above the clamp ceiling must still
    # be capped, so one unusually strong store cannot swing every future
    # estimate by more than the app is willing to trust.
    isolated_db.save_benchmark(label="Strong Store", address="3 Test St", concept="deli",
                               actual_daily_sales=9000, monthly_rent=8000, sqft=1200,
                               modeled_daily=2000, ratio=4.5, notes="")
    factor, n = isolated_db.calibration_factor("deli")
    assert n == 1
    assert factor == 1.8


def test_calibration_factor_is_scoped_per_concept(isolated_db):
    isolated_db.save_benchmark(label="Deli", address="1 Test St", concept="deli",
                               actual_daily_sales=6000, monthly_rent=8000, sqft=1200,
                               modeled_daily=5000, ratio=1.2, notes="")
    factor, n = isolated_db.calibration_factor("cafe")
    assert n == 0
    assert factor == 1.0
