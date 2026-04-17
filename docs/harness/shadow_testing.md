# Shadow Testing

## Overview

Shadow testing runs a new model/prompt version in parallel with production, comparing outputs without user impact.

## Architecture

```
User Query → Production Graph (serves user)
         └→ Shadow Graph (discards response)
              ↓
         Comparison Engine
              ↓
         Report Generator
```

## Components

### `app/evaluation/shadow.py`

- `ShadowOrchestrator.should_sample()`: Deterministic 10% sampling via thread_id hash
- `ShadowOrchestrator.run_shadow()`: Runs both graphs on same query
- `ShadowOrchestrator.compare_results()`: Compares intent, answer, latency
- `ShadowOrchestrator.generate_report()`: Aggregates comparison metrics

### `app/tasks/shadow_tasks.py`

Celery task `shadow.run_shadow_test`:
- Initializes production graph (default model) and shadow graph (different model)
- Samples 10% of queries deterministically
- Runs both graphs and compares results
- Returns comparison metrics and regression flags

### API Endpoint

`POST /admin/shadow-test/run?query={query}`

Triggers a shadow test for a specific query. Requires admin authentication.

## Configuration

Set shadow model via environment variable or settings:

```python
SHADOW_MODEL = "gpt-4o-mini"  # Different from production model
```

## Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `intent_match_rate` | % of queries with matching intent | > 0.95 |
| `avg_answer_similarity` | Jaccard similarity of answers | > 0.80 |
| `latency_regression` | Shadow latency > production + 500ms | False |

## Usage

### Manual Trigger

```bash
curl -X POST "http://localhost:8000/api/v1/admin/shadow-test/run?query=check+my+order" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Interpreting Results

```json
{
  "sampled": true,
  "query": "check my order",
  "comparison": {
    "intent_match": true,
    "answer_similarity": 0.92,
    "latency_delta_ms": 50
  },
  "report": {
    "intent_match_rate": 1.0,
    "avg_answer_similarity": 0.92,
    "latency_regression": false
  }
}
```

## Deployment

1. Deploy shadow environment with different model/prompt
2. Configure `SHADOW_MODEL` setting
3. Monitor shadow test results via admin dashboard
4. Promote shadow to production when metrics meet thresholds
