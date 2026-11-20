"""Run the Collector's test groups T01-T08 and record one result per group.

Run from the repository root with the backend's environment:

    backend/.venv/bin/python docs/tech-evidence/function_checks.py

T01-T08 are references used in the technical evidence log. Each runs a
selection of the existing pytest suite; none is an additional test.
Results are written to docs/tech-evidence/function-results.json.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
C, K = "tests/test_collection.py", "tests/test_company.py"

CHECKS = [
    (
        "T01",
        "Pass signing and signature rejection",
        [
            [
                C,
                "-k",
                "forged or rubbish or tampered or one_nursery_fails or invalid_check",
            ]
        ],
    ),
    (
        "T02",
        "Revocation, reissue and one-off passes",
        [[C, "-k", "revok or reissue or leaving or one_off or future_regular"]],
    ),
    (
        "T03",
        "Door verification and release",
        [
            [
                C,
                "-k",
                (
                    "authorise_check_release or daily_code or code_does_not_work or refusal_needs"
                    " or decided_once or release_needs_the_id or refusal_does_not_need or wrong_codes_pause"
                    " or parents_cannot_use_the_door"
                ),
            ]
        ],
    ),
    (
        "T04",
        "One release per child per day under concurrent checks",
        [
            [
                C,
                "-k",
                (
                    "second_collector or two_valid_checks or refusal_does_not_count"
                    " or yesterdays or sibling"
                ),
            ]
        ],
    ),
    (
        "T05",
        "Nursery isolation",
        [
            [
                C,
                "-k",
                (
                    "another_child or not_theirs or another_familys or another_nurserys"
                    " or one_nursery_fails"
                ),
            ],
            [K, "-k", "portals_do_not_cross or nurseries_cannot_read"],
        ],
    ),
    (
        "T06",
        "Operator blindness and role separation",
        [
            [K, "-k", "counts_but_never_names or portals_do_not_cross or suspending"],
            [
                C,
                "-k",
                "first_name_only or staff_cannot_reach_admin or staff_cannot_read_the_activity",
            ],
        ],
    ),
    (
        "T07",
        "Reconciliation with the nursery's sign-out register",
        [["tests/test_reconciliation.py"]],
    ),
    (
        "T08",
        "Parent notification, handover record and evidence export",
        [
            [
                C,
                "-k",
                (
                    "tell_both_parents or refusal_needs or handovers_are_never_edited"
                    " or admin_sees_handovers or export_and_the_activity"
                ),
            ],
            ["tests/test_contacts_reports.py"],
        ],
    ),
]


def run(args: list[str]) -> tuple[int, int, int]:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        check=False,
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    last = (result.stdout.strip().splitlines() or [""])[-1]
    found = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|error)", last)}
    return (
        found.get("passed", 0),
        found.get("failed", 0) + found.get("error", 0),
        result.returncode,
    )


def main() -> int:
    rows, failed = [], False
    print(f"Run at {datetime.now(UTC):%Y-%m-%d %H:%M UTC}")
    for cid, description, selections in CHECKS:
        passed = fails = 0
        for args in selections:
            p, f, code = run(args)
            passed, fails = (
                passed + p,
                fails + f + (1 if code not in (0,) and not f else 0),
            )
        status = "PASS" if passed and not fails else "FAIL"
        failed |= status == "FAIL"
        rows.append(
            {
                "id": cid,
                "description": description,
                "status": status,
                "passed": passed,
                "failed": fails,
            }
        )
        print(f"{status} | {cid} | {description} | {passed} passed, {fails} failed")
    out = ROOT / "docs" / "tech-evidence" / "function-results.json"
    out.write_text(json.dumps(rows, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
