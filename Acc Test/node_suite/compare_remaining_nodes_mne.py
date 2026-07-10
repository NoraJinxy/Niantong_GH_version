"""Run all local MNE comparisons for the remaining-node suite."""

from __future__ import annotations

import argparse
import json

from node_mne_common import CASE_RUNNERS, METRICS_PATH, SUMMARY_PATH, run_all


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        action="append",
        choices=sorted(CASE_RUNNERS),
        help="Run one case. Repeat to run several. Defaults to all cases.",
    )
    args = parser.parse_args()
    results = run_all(args.case)
    print(
        json.dumps(
            {
                "cases": {key: value.get("status") for key, value in results.items()},
                "metrics_path": str(METRICS_PATH),
                "summary_path": str(SUMMARY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
