"""Golden dataset schema validation and loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.intent.models import IntentCategory


class GoldenRecord(BaseModel):
    """Single record in the golden dataset."""

    query: str = Field(..., min_length=1)
    expected_intent: str
    expected_slots: dict[str, Any] = Field(default_factory=dict)
    expected_answer_fragment: str = ""
    expected_audit_level: str = Field(..., pattern=r"^(auto|medium|manual)$")
    dimension: str = Field(..., min_length=1)

    @field_validator("expected_intent")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        try:
            IntentCategory(v)
        except ValueError as exc:
            valid = [i.value for i in IntentCategory]
            raise ValueError(f"Invalid intent '{v}'. Must be one of: {valid}") from exc
        return v


class GoldenDataset(BaseModel):
    """Validated golden dataset with metadata."""

    records: list[GoldenRecord]
    source_path: str | None = None

    @property
    def total_records(self) -> int:
        return len(self.records)

    @property
    def dimension_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            dim = record.dimension
            counts[dim] = counts.get(dim, 0) + 1
        return counts

    def filter_by_dimension(self, dimension: str) -> list[GoldenRecord]:
        return [r for r in self.records if r.dimension == dimension]

    def filter_by_intent(self, intent: str) -> list[GoldenRecord]:
        return [r for r in self.records if r.expected_intent == intent]


def load_golden_dataset(path: str | Path) -> GoldenDataset:
    """Load and validate a golden dataset from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        Validated GoldenDataset instance.

    Raises:
        ValueError: If the file contains invalid records.
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    records: list[GoldenRecord] = []
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
                record = GoldenRecord.model_validate(raw)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Validation failed on line {line_number}: {exc}") from exc
            records.append(record)

    return GoldenDataset(records=records, source_path=str(file_path))


def validate_dataset_dimensions(
    dataset: GoldenDataset,
    expected_dimensions: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Validate that a dataset meets dimension count requirements.

    Args:
        dataset: The dataset to validate.
        expected_dimensions: Mapping of dimension name to minimum expected count.

    Returns:
        Validation result with ``valid`` flag and ``details``.
    """
    if expected_dimensions is None:
        expected_dimensions = {
            "order_query": 30,
            "refund_apply": 25,
            "policy_inquiry": 25,
            "product_query": 20,
            "ambiguous_intent": 20,
            "multi_intent": 15,
            "abnormal_input": 15,
            "long_conversation": 10,
        }

    actual = dataset.dimension_counts
    details: dict[str, Any] = {}
    all_valid = True

    for dim, min_count in expected_dimensions.items():
        count = actual.get(dim, 0)
        dim_valid = count >= min_count
        details[dim] = {"expected": min_count, "actual": count, "valid": dim_valid}
        if not dim_valid:
            all_valid = False

    total_expected = sum(expected_dimensions.values())
    details["total"] = {
        "expected_min": total_expected,
        "actual": dataset.total_records,
        "valid": dataset.total_records >= total_expected,
    }

    return {"valid": all_valid and dataset.total_records >= total_expected, "details": details}
