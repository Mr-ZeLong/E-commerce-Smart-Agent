# Continuous Improvement Loop

## Overview

The continuous improvement loop automates quality audits from production data and feeds findings back into the Golden Dataset for model optimization.

## Flow

```
Production Conversations → Weekly Audit (5% sampling) → Root Cause Annotation →
Golden Dataset Update → Prompt/Model Optimization → A/B Testing → Production Validation
```

## Components

### `app/services/continuous_improvement.py`

- `ContinuousImprovementService.sample_conversations()`: Stratified sampling by intent category
- `ContinuousImprovementService.run_audit()`: Executes full audit and logs results
- `ContinuousImprovementService.merge_feedback_into_dataset()`: Merges annotated samples into golden dataset

### `app/tasks/continuous_improvement_tasks.py`

Celery task `continuous_improvement.run_weekly_audit` runs every week:
- Samples 5% of conversations from the past 7 days
- Stratifies by intent category to ensure balanced representation
- Returns audit batch metadata

### API Endpoint

`POST /admin/continuous-improvement/audit`

Triggers a manual audit run. Requires admin authentication.

## Root Cause Categories

| Category | Description | Dataset Dimension |
|----------|-------------|-------------------|
| `intent_error` | Misclassified intent | `ambiguous_intent` |
| `hallucination` | LLM generated false information | `abnormal_input` |
| `latency` | Response too slow | `long_conversation` |
| `safety` | Safety filter failure | `abnormal_input` |
| `tone` | Inconsistent tone | `abnormal_input` |
| `other` | Uncategorized issues | `abnormal_input` |

## Usage

### Manual Trigger

```bash
curl -X POST http://localhost:8000/api/v1/admin/continuous-improvement/audit \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Automated Schedule

Configure Celery beat to run `continuous_improvement.run_weekly_audit` weekly.

## Merging Feedback

After reviewing audit samples and annotating root causes:

```python
from app.services.continuous_improvement import ContinuousImprovementService

service = ContinuousImprovementService(db_session=session)
batch = await service.run_audit(days=7, sample_rate=0.05)

# Annotate root causes on batch.samples
for sample in batch.samples:
    sample.root_cause = RootCause.INTENT_ERROR

# Merge into dataset
ContinuousImprovementService.merge_feedback_into_dataset(
    dataset_path="data/golden_dataset_v2.jsonl",
    audit_batch=batch,
)
```
