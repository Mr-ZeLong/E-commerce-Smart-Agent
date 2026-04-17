"""CLI to run the adversarial test suite and generate a markdown report."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI

from app.evaluation.adversarial import AdversarialRunner
from app.main import lifespan


def _generate_markdown(report) -> str:  # noqa: ANN001
    """Generate a markdown security report from an AdversarialReport."""
    lines: list[str] = []
    lines.append("# Adversarial Security Test Report\n")
    lines.append(f"**Total Cases:** {report.total_cases}")
    lines.append(f"**Passed:** {report.passed_cases}")
    lines.append(f"**Failed:** {report.failed_cases}")
    lines.append(f"**Pass Rate:** {report.pass_rate:.2%}\n")

    lines.append("## Category Breakdown\n")
    lines.append("| Category | Total | Passed | Failed | Pass Rate |")
    lines.append("|----------|-------|--------|--------|-----------|")
    for category, stats in sorted(report.category_breakdown.items()):
        lines.append(
            f"| {category} | {stats['total']} | {stats['passed']} | "
            f"{stats['failed']} | {stats['pass_rate']:.2%} |"
        )
    lines.append("")

    lines.append("## Severity Breakdown\n")
    lines.append("| Severity | Total | Passed | Failed | Pass Rate |")
    lines.append("|----------|-------|--------|--------|-----------|")
    for severity, stats in sorted(report.severity_breakdown.items()):
        lines.append(
            f"| {severity} | {stats['total']} | {stats['passed']} | "
            f"{stats['failed']} | {stats['pass_rate']:.2%} |"
        )
    lines.append("")

    failed = [r for r in report.results if not r.passed]
    if failed:
        lines.append(f"## Failed Cases ({len(failed)})\n")
        for result in failed:
            lines.append(f"### Query: `{result.query[:80]}`")
            lines.append(f"- **Category:** {result.category}")
            lines.append(f"- **Severity:** {result.severity}")
            lines.append(f"- **Expected:** {result.expected_behavior}")
            lines.append(f"- **Actual:** {result.actual_behavior}")
            lines.append(f"- **Blocked:** {result.safety_blocked}")
            if result.clarification_question:
                lines.append(f"- **Clarification:** {result.clarification_question}")
            lines.append("")
    else:
        lines.append("## Failed Cases\n")
        lines.append("All adversarial cases passed.\n")

    return "\n".join(lines)


async def _run(dataset_path: str, report_path: str) -> int:
    app = FastAPI(lifespan=lifespan)
    async with lifespan(app):
        runner = AdversarialRunner(intent_service=app.state.intent_service)
        report = await runner.run(dataset_path)

    markdown = _generate_markdown(report)
    Path(report_path).write_text(markdown, encoding="utf-8")
    print(f"Report written to {report_path}")
    return 0 if report.failed_cases == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run adversarial test suite.")
    parser.add_argument(
        "--dataset",
        default="tests/evaluation/adversarial_suite.jsonl",
        help="Path to the adversarial dataset (JSONL).",
    )
    parser.add_argument(
        "--report",
        default="adversarial_report.md",
        help="Path to the output markdown report.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args.dataset, args.report))


if __name__ == "__main__":
    sys.exit(main())
