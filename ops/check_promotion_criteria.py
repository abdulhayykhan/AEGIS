"""AEGIS Autonomy Promotion Criteria Verifier.

Built by [Abdul Hayy Khan](https://abdulhayykhan.dev).
Citations:
- AEGIS PRD Section 17 & 18 (Autonomy Rung Transition Gate)
- AEGIS Project Review Report (Section 6.2: Automated Gate Progression Verification)
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.storage.db import Database


class PromotionTargetRung(str, Enum):
    PAPER_EXECUTION = "PAPER_EXECUTION"      # Phase 6
    LIVE_WITH_APPROVAL = "LIVE_WITH_APPROVAL"  # Phase 7
    FULL_AUTONOMY = "FULL_AUTONOMY"          # Phase 8


class PromotionCheckResult(BaseModel):
    """Audited evaluation result determining if autonomy promotion is mathematically permitted."""
    model_config = ConfigDict(frozen=True)

    target_rung: PromotionTargetRung
    eligible: bool
    passed_checks: list[str] = Field(default_factory=list)
    failing_reasons: list[str] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)


def check_promotion_eligibility(
    db: Database,
    target_rung: PromotionTargetRung | str
) -> PromotionCheckResult:
    """Evaluate database evidence against PRD Section 17 & 18 exit criteria before permitting promotion.
    
    Guarantees 'evidence, never it ran': refuses advancement unless verifiable DB records confirm compliance.
    """
    rung = PromotionTargetRung(target_rung)
    passed_checks: list[str] = []
    failing_reasons: list[str] = []

    # 1. Check active unresolved demotions
    active_demotion = db.get_active_demotion_rung()
    if active_demotion:
        failing_reasons.append(f"Active unresolved demotion present: system demoted to '{active_demotion}'.")
    else:
        passed_checks.append("Zero active unresolved demotions in database.")

    # 2. Query completed runs from database
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT run_id, mode, status, started_at FROM runs WHERE status = 'SUCCESS'")
        success_runs = cursor.fetchall()

        cursor.execute("SELECT run_id, mode, status FROM runs WHERE status != 'SUCCESS'")
        failed_runs = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) as cnt FROM gate_decisions WHERE passed = 0")
        rejected_decisions = cursor.fetchone()["cnt"]

    total_success = len(success_runs)
    total_failed = len(failed_runs)

    # 3. Evaluate rung-specific criteria
    if rung == PromotionTargetRung.PAPER_EXECUTION:
        # Phase 5 -> 6: Requires >= 14 successful Recommend-Only runs
        required_runs = 14
        if total_success < required_runs:
            failing_reasons.append(f"Insufficient runs: observed {total_success} < {required_runs} required.")
        else:
            passed_checks.append(f"Completed {total_success} successful pre-flight runs (>= {required_runs}).")

    elif rung == PromotionTargetRung.LIVE_WITH_APPROVAL:
        # Phase 6 -> 7: Requires >= 56 continuous successful paper runs (8 weeks)
        required_runs = 56
        if total_success < required_runs:
            failing_reasons.append(f"Insufficient runs: observed {total_success} < {required_runs} required.")
        else:
            passed_checks.append(f"Completed {total_success} continuous paper execution runs (>= {required_runs} required for 8 weeks).")

        if total_failed > 0:
            failing_reasons.append(f"Recorded {total_failed} failed scheduled runs in database (must be 0).")
        else:
            passed_checks.append("Zero failed scheduled runs.")

    elif rung == PromotionTargetRung.FULL_AUTONOMY:
        # Phase 7 -> 8: Requires >= 28 continuous successful live-approval runs (4 weeks)
        required_runs = 28
        if total_success < required_runs:
            failing_reasons.append(f"Insufficient runs: observed {total_success} < {required_runs} required.")
        else:
            passed_checks.append(f"Completed {total_success} successful live runs with owner approval (>= {required_runs} required).")

        if total_failed > 0:
            failing_reasons.append(f"Recorded {total_failed} failed runs (must be 0).")
        else:
            passed_checks.append("Zero failed scheduled runs.")

    eligible = len(failing_reasons) == 0

    return PromotionCheckResult(
        target_rung=rung,
        eligible=eligible,
        passed_checks=passed_checks,
        failing_reasons=failing_reasons,
        evidence_summary={
            "total_success_runs": total_success,
            "total_failed_runs": total_failed,
            "rejected_gate_decisions": rejected_decisions,
            "active_demotion": active_demotion
        }
    )
