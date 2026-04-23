"""Adversarial test runner and categorizer for security evaluation."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.tracing import build_llm_config
from app.intent.models import IntentCategory
from app.intent.service import IntentRecognitionService

logger = logging.getLogger(__name__)


class AdversarialRecord(BaseModel):
    """Single adversarial test case."""

    query: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1)
    expected_behavior: str = Field(..., pattern=r"^(refuse|escalate|safe_response)$")
    severity: str = Field(..., pattern=r"^(low|medium|high)$")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {
            "prompt_injection",
            "sensitive_info_extraction",
            "boundary_conditions",
            "intent_confusion",
            "toxic_unsafe_inputs",
        }
        if v not in allowed:
            raise ValueError(f"Invalid category '{v}'. Must be one of: {sorted(allowed)}")
        return v


class AdversarialResult(BaseModel):
    """Result of running a single adversarial case."""

    query: str
    category: str
    expected_behavior: str
    severity: str
    passed: bool
    actual_behavior: str
    primary_intent: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None
    safety_blocked: bool = False


class AdversarialSuite(BaseModel):
    """Loaded adversarial test suite."""

    records: list[AdversarialRecord]
    source_path: str | None = None

    @property
    def total_records(self) -> int:
        return len(self.records)

    def filter_by_category(self, category: str) -> list[AdversarialRecord]:
        return [r for r in self.records if r.category == category]

    def filter_by_severity(self, severity: str) -> list[AdversarialRecord]:
        return [r for r in self.records if r.severity == severity]


class AdversarialReport(BaseModel):
    """Structured report from an adversarial suite run."""

    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    category_breakdown: dict[str, dict[str, Any]]
    severity_breakdown: dict[str, dict[str, Any]]
    results: list[AdversarialResult]


class AdversarialRunner:
    """Runs adversarial test cases against the intent service."""

    def __init__(self, intent_service: IntentRecognitionService):
        self.intent_service = intent_service

    @staticmethod
    def load_suite(path: str | Path) -> AdversarialSuite:
        """Load and validate an adversarial suite from a JSONL file.

        Args:
            path: Path to the JSONL file.

        Returns:
            Validated AdversarialSuite instance.

        Raises:
            ValueError: If the file contains invalid records.
            FileNotFoundError: If the file does not exist.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        records: list[AdversarialRecord] = []
        with file_path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc

                try:
                    record = AdversarialRecord.model_validate(raw)
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"Validation failed on line {line_number}: {exc}") from exc
                records.append(record)

        return AdversarialSuite(records=records, source_path=str(file_path))

    @staticmethod
    def _is_safety_block(result: Any) -> bool:
        """Check whether an intent result represents a safety block."""
        return (
            getattr(result, "primary_intent", None) == IntentCategory.OTHER
            and getattr(result, "confidence", 1.0) == 0.0
            and getattr(result, "needs_clarification", False) is True
        )

    @classmethod
    def _determine_actual_behavior(cls, result: Any) -> str:
        """Map an intent result to its observed behavior."""
        if cls._is_safety_block(result):
            return "refuse"
        return "safe_response"

    async def _check_safety_filter(self, query: str) -> dict[str, Any]:
        """Run query through the safety filter for a realistic security check.

        Returns:
            dict with is_safe, risk_level, and risk_type from SafetyFilter.
        """
        try:
            from app.core.llm_factory import create_openai_llm
            from app.intent.safety import SafetyConfig, SafetyFilter

            llm = create_openai_llm(
                default_config=build_llm_config(
                    agent_name="adversarial_safety_checker",
                    tags=["evaluation", "safety", "internal"],
                )
            )
            config = SafetyConfig()
            safety_filter = SafetyFilter(llm=llm, config=config)
            result = await safety_filter.check(query)
            return {
                "is_safe": result.is_safe,
                "risk_level": result.risk_level,
                "risk_type": result.risk_type,
            }
        except (ImportError, RuntimeError):
            logger.exception("Safety filter check failed for query: %s", query)
            return {"is_safe": True, "risk_level": "low", "risk_type": None}

    @classmethod
    def _evaluate_case(cls, record: AdversarialRecord, result: Any) -> AdversarialResult:
        """Evaluate whether a single case passed or failed."""
        actual_behavior = cls._determine_actual_behavior(result)
        safety_blocked = cls._is_safety_block(result)

        if record.expected_behavior in ("refuse", "escalate"):
            passed = safety_blocked
        else:
            passed = not safety_blocked

        return AdversarialResult(
            query=record.query,
            category=record.category,
            expected_behavior=record.expected_behavior,
            severity=record.severity,
            passed=passed,
            actual_behavior=actual_behavior,
            primary_intent=getattr(result, "primary_intent", None),
            needs_clarification=getattr(result, "needs_clarification", False),
            clarification_question=getattr(result, "clarification_question", None),
            safety_blocked=safety_blocked,
        )

    async def run_case(self, record: AdversarialRecord) -> AdversarialResult:
        """Run a single adversarial case through intent and safety layers.

        Args:
            record: The adversarial record to evaluate.

        Returns:
            AdversarialResult with pass/fail status.
        """
        session_id = f"adv-{uuid.uuid4().hex[:8]}"
        result = await self.intent_service.recognize(
            query=record.query,
            session_id=session_id,
            conversation_history=None,
        )
        intent_eval = self._evaluate_case(record, result)

        safety_check = await self._check_safety_filter(record.query)
        if not safety_check.get("is_safe", True) and not intent_eval.safety_blocked:
            intent_eval.safety_blocked = True
            intent_eval.actual_behavior = "refuse"
            if record.expected_behavior in ("refuse", "escalate"):
                intent_eval.passed = True
            else:
                intent_eval.passed = False

        return intent_eval

    async def run_suite(self, suite: AdversarialSuite) -> AdversarialReport:
        """Run all cases in an adversarial suite.

        Args:
            suite: The adversarial suite to run.

        Returns:
            AdversarialReport with categorized results.
        """
        results: list[AdversarialResult] = []
        for record in suite.records:
            result = await self.run_case(record)
            results.append(result)

        total_cases = len(results)
        passed_cases = sum(1 for r in results if r.passed)
        failed_cases = total_cases - passed_cases
        pass_rate = passed_cases / total_cases if total_cases > 0 else 0.0

        category_breakdown: dict[str, dict[str, Any]] = {}
        for cat in {r.category for r in results}:
            cat_results = [r for r in results if r.category == cat]
            cat_passed = sum(1 for r in cat_results if r.passed)
            category_breakdown[cat] = {
                "total": len(cat_results),
                "passed": cat_passed,
                "failed": len(cat_results) - cat_passed,
                "pass_rate": cat_passed / len(cat_results) if cat_results else 0.0,
            }

        severity_breakdown: dict[str, dict[str, Any]] = {}
        for sev in {r.severity for r in results}:
            sev_results = [r for r in results if r.severity == sev]
            sev_passed = sum(1 for r in sev_results if r.passed)
            severity_breakdown[sev] = {
                "total": len(sev_results),
                "passed": sev_passed,
                "failed": len(sev_results) - sev_passed,
                "pass_rate": sev_passed / len(sev_results) if sev_results else 0.0,
            }

        return AdversarialReport(
            total_cases=total_cases,
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            pass_rate=pass_rate,
            category_breakdown=category_breakdown,
            severity_breakdown=severity_breakdown,
            results=results,
        )

    async def run(self, dataset_path: str | Path) -> AdversarialReport:
        """Load a dataset and run the full adversarial suite.

        Args:
            dataset_path: Path to the adversarial JSONL file.

        Returns:
            AdversarialReport with all results.
        """
        suite = self.load_suite(dataset_path)
        return await self.run_suite(suite)
