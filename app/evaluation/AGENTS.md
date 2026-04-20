# AGENTS.md - Evaluation

> **IMPORTANT**: Read the root [`AGENTS.md`](../../AGENTS.md) first for repo-wide rules.

## Maintenance Contract

- This file is a living document for the evaluation framework.
- Update this file in the same PR when adding new evaluators, metrics, or evaluation pipelines.

## Read Order

1. Read the root [`AGENTS.md`](../../AGENTS.md) for repo-wide rules, commands, and routing.
2. Read this file for evaluation-specific guidance.

## Overview

Offline evaluation framework for assessing agent response quality, hallucination, containment, tone consistency, and token efficiency. Supports adversarial testing, shadow testing, and continuous improvement metrics.

## Key Files

| Role | File | Notes |
|------|------|-------|
| Evaluation pipeline | `app/evaluation/pipeline.py` | Orchestrates evaluation runs |
| Evaluation runner | `app/evaluation/run.py` | Executes evaluation scenarios |
| Adversarial testing | `app/evaluation/adversarial.py` | Adversarial example generation and testing |
| Shadow testing | `app/evaluation/shadow.py` | Shadow mode evaluation against production |
| Metrics | `app/evaluation/metrics.py` | Evaluation metrics (accuracy, relevance, etc.) |
| Hallucination detection | `app/evaluation/hallucination.py` | LLM-based hallucination detection |
| Tone consistency | `app/evaluation/tone_consistency.py` | Tone and style consistency evaluation |
| Baseline comparison | `app/evaluation/baseline.py` | Baseline model comparison |
| Dataset management | `app/evaluation/dataset.py` | Evaluation dataset curation |
| Containment | `app/evaluation/containment.py` | Response containment validation |
| Token efficiency | `app/evaluation/token_efficiency.py` | Token usage optimization metrics |
| Few-shot evaluation | `app/evaluation/few_shot_eval.py` | Few-shot prompt evaluation |

## Commands

```bash
# Run evaluation module tests
uv run pytest tests/evaluation/
```

## Code Style

General Python rules are defined in the root `AGENTS.md`. Evaluation-specific conventions:

- **Type hints**: All metric functions and evaluation methods must be fully typed.
- **Immutability**: Evaluation datasets should be treated as immutable; create new versions rather than modifying existing ones.
- **Reproducibility**: Fix random seeds and document LLM model versions for reproducible evaluation results.

## Testing Patterns

- Mock LLM calls in evaluation tests to avoid non-determinism.
- Use synthetic datasets for unit tests; reserve real data for integration tests.
- Test each metric independently with known inputs/outputs.
- Verify pipeline orchestration with mocked components.

## Conventions

- **Metric range**: All metrics should return scores in the range [0, 1] where 1 is optimal.
- **Hallucination detection**: Binary scoring (0.0 or 1.0); target false positive rate ≤ 0.05.
- **Containment check**: Verify responses are contained within retrieved context; flag violations.
- **Dataset versioning**: Version evaluation datasets to track changes over time.

## Anti-Patterns

- **Evaluating on training data**: Never evaluate on data used for prompt engineering or fine-tuning.
- **Single-metric evaluation**: Use multiple complementary metrics for robust assessment.
- **Ignoring edge cases**: Include adversarial and edge cases in evaluation datasets.

## Related Files

- `app/agents/evaluator.py` — Uses evaluation metrics for agent response scoring.
- `app/services/online_eval.py` — Online evaluation service for real-time feedback.
- `app/tasks/evaluation_tasks.py` — Celery tasks for async evaluation runs.
