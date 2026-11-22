import argparse
import sys
from pathlib import Path

from ops.dashboard import AegisDashboard
from ops.scheduler import AutonomousScheduler, SchedulerConfig
from src.agent.loop import AgentConfig
from src.connector.server import AegisConnectorServer
from src.gate.kill_switch import DEFAULT_LOCK_FILE, StandaloneKillSwitch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aegis",
        description="AEGIS: Autonomous Execution with Governed Investment Safeguards CLI"
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # 1. Dashboard
    subparsers.add_parser("dashboard", help="Render operational metrics and risk budget dashboard")

    # 2. Run Cycle
    run_parser = subparsers.add_parser("run", help="Execute an autonomous trading cycle")
    run_parser.add_argument(
        "--mode",
        choices=["RECOMMEND_ONLY", "PAPER_EXECUTION", "LIVE_WITH_APPROVAL", "FULL_AUTONOMY"],
        default="PAPER_EXECUTION",
        help="Operating execution mode"
    )

    # 3. Emergency Kill Switch
    kill_parser = subparsers.add_parser("kill", help="Emergency Kill Switch management")
    kill_parser.add_argument("--reason", default="Manual CLI intervention", help="Reason for halting")
    kill_parser.add_argument("--owner", default="Abdul Hayy Khan", help="Operator identity")
    kill_parser.add_argument("--disengage", action="store_true", help="Disengage the kill switch")
    kill_parser.add_argument("--token", default=None, help="Owner security token required to disengage")
    kill_parser.add_argument("--lock-path", default=str(DEFAULT_LOCK_FILE), help="Path to lock file")

    # 4. Restore Autonomy Rung from Demotion
    restore_parser = subparsers.add_parser("restore", help="Resolve active demotion and restore autonomy rung (B8)")
    restore_parser.add_argument("--incident", required=True, help="Incident ID to resolve")
    restore_parser.add_argument("--owner", default="Abdul Hayy Khan", help="Operator identity")
    restore_parser.add_argument("--token", default=None, help="Owner security token")

    # 5. Emergency Flatten
    flatten_parser = subparsers.add_parser("flatten", help="Emergency flatten: close all open positions with reduce-only orders (B6)")
    flatten_parser.add_argument("--owner", default="Abdul Hayy Khan", help="Operator identity")
    flatten_parser.add_argument("--token", default=None, help="Owner security token required to execute emergency flatten")

    # 6. Reconcile
    subparsers.add_parser("reconcile", help="Verify minor-unit reconciliation between DB and broker")

    # 7. Check Promotion Eligibility
    promote_parser = subparsers.add_parser("promote", help="Check database evidence against autonomy promotion exit criteria")
    promote_parser.add_argument(
        "--target",
        choices=["PAPER_EXECUTION", "LIVE_WITH_APPROVAL", "FULL_AUTONOMY"],
        default="PAPER_EXECUTION",
        help="Target autonomy rung"
    )

    # 8. Weekly Performance Report
    subparsers.add_parser("report", help="Generate weekly performance and audit report from database")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    mode_arg = getattr(args, "mode", "PAPER_EXECUTION")
    conn_mode = "LIVE" if mode_arg in ("LIVE_WITH_APPROVAL", "FULL_AUTONOMY") else "PAPER"
    server = AegisConnectorServer(mode=conn_mode)
    server.seed_mock_data()

    if args.subcommand == "dashboard":
        dash = AegisDashboard(connector=server)
        print(dash.render_markdown())
        return 0

    elif args.subcommand == "run":
        sched_config = SchedulerConfig(lock_file=Path("scheduler_cli.lock"))
        agent_config = AgentConfig(mode=args.mode)
        scheduler = AutonomousScheduler(
            connector=server,
            scheduler_config=sched_config,
            agent_config=agent_config
        )
        report = scheduler.run_scheduled_cycle()
        print(f"Run completed with status: {'SUCCESS' if report.success else 'FAILED'}")
        print(report.summary)
        return 0 if report.success else 1

    elif args.subcommand == "kill":
        lock_file = Path(args.lock_path)
        ks = StandaloneKillSwitch(lock_file_path=lock_file)
        if args.disengage:
            try:
                ks.disengage(operator=args.owner, token=args.token)
                print(f"Kill switch DISENGAGED by {args.owner}. Operations may resume.")
            except Exception as e:  # noqa: BLE001
                print(f"Error disengaging kill switch: {e}")
                return 1
        else:
            ks.engage(reason=args.reason, operator=args.owner)
            print(f"Kill switch ENGAGED by {args.owner}. Reason: {args.reason}")
        return 0

    elif args.subcommand == "restore":
        import hmac
        import os
        restore_secret = (
            os.environ.get("AEGIS_RESTORE_SECRET")
            or os.environ.get("AEGIS_OWNER_SECRET")
            or os.environ.get("AEGIS_OWNER_TOKEN")
        )
        if not restore_secret or not args.token or not hmac.compare_digest(args.token, restore_secret):
            print("Error: Invalid or missing owner restore security token. Cannot resolve demotion incident (fail-closed).")
            return 1
        server.db.resolve_demotion(incident_id=args.incident, operator=args.owner)
        print(f"Incident '{args.incident}' resolved by {args.owner}. Autonomy rung restored.")
        return 0

    elif args.subcommand == "flatten":
        import hmac
        import os
        flatten_secret = (
            os.environ.get("AEGIS_FLATTEN_SECRET")
            or os.environ.get("AEGIS_OWNER_SECRET")
            or os.environ.get("AEGIS_OWNER_TOKEN")
        )
        if not flatten_secret or not args.token or not hmac.compare_digest(args.token, flatten_secret):
            print("Error: Invalid or missing flatten security token. Emergency flatten rejected (fail-closed).")
            return 1
        try:
            results = server.flatten_positions(operator=args.owner, token=args.token)
        except PermissionError as e:
            print(f"Error: {e}")
            return 1
        print(f"Emergency Flatten executed by {args.owner}. Closed {len(results)} positions.")
        for r in results:
            print(f"- {r['symbol']}: {r['size']} units at ${r['price']} ({r['status']})")
        return 0

    elif args.subcommand == "reconcile":
        sched_config = SchedulerConfig(lock_file=Path("scheduler_rec.lock"))
        scheduler = AutonomousScheduler(
            connector=server,
            scheduler_config=sched_config
        )
        db_state = scheduler._get_db_ledger_state()
        broker_state = scheduler._get_broker_state()
        from src.gate.reconcile import reconcile_states
        res = reconcile_states(db_state, broker_state)
        print("--- RECONCILIATION RESULT ---")
        print(f"Status: {'MATCH' if res.match else 'MISMATCH'}")
        if res.diffs:
            for d in res.diffs:
                print(f"- {d}")
        return 0 if res.match else 1

    elif args.subcommand == "promote":
        from ops.check_promotion_criteria import check_promotion_eligibility
        promo_res = check_promotion_eligibility(db=server.db, target_rung=args.target)
        print(f"--- AUTONOMY PROMOTION CHECK: {args.target} ---")
        print(f"Eligible: {'YES (APPROVED)' if promo_res.eligible else 'NO (REFUSED)'}")
        if promo_res.passed_checks:
            print("Passed Requirements:")
            for p in promo_res.passed_checks:
                print(f"  [PASS] {p}")
        if promo_res.failing_reasons:
            print("Unmet Requirements:")
            for f in promo_res.failing_reasons:
                print(f"  [FAIL] {f}")
        return 0 if promo_res.eligible else 1

    elif args.subcommand == "report":
        from ops.weekly_report import generate_weekly_report
        rep = generate_weekly_report(db=server.db)
        print(rep.to_markdown())
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
