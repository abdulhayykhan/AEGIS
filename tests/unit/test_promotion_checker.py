from pathlib import Path

from ops.check_promotion_criteria import PromotionTargetRung, check_promotion_eligibility
from src.storage.db import Database


def test_promotion_refused_when_no_runs(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "promo_empty.db")
    res = check_promotion_eligibility(db, target_rung=PromotionTargetRung.PAPER_EXECUTION)
    assert res.eligible is False
    assert any("Insufficient runs" in reason for reason in res.failing_reasons)


def test_promotion_refused_on_active_demotion(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "promo_demote.db")
    # Record 60 mock successful runs
    for i in range(60):
        db.record_run_start(f"RUN-{i}", "PAPER")
        db.record_run_complete(f"RUN-{i}", "SUCCESS")

    # Record active unresolved demotion
    db.record_demotion("INC-01", "RECOMMEND_ONLY", "Reconciliation mismatch detected")

    res = check_promotion_eligibility(db, target_rung=PromotionTargetRung.LIVE_WITH_APPROVAL)
    assert res.eligible is False
    assert any("active unresolved demotion" in reason.lower() for reason in res.failing_reasons)


def test_promotion_accepted_when_evidence_criteria_met(tmp_path: Path) -> None:
    db = Database(db_path=tmp_path / "promo_success.db")
    # Record 56 successful paper runs (8 weeks)
    for i in range(56):
        db.record_run_start(f"RUN-{i}", "PAPER")
        db.record_run_complete(f"RUN-{i}", "SUCCESS")

    res = check_promotion_eligibility(db, target_rung=PromotionTargetRung.LIVE_WITH_APPROVAL)
    assert res.eligible is True
    assert len(res.failing_reasons) == 0
    assert len(res.passed_checks) >= 3
