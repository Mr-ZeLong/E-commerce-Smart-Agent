# Grafana Loki Integration Guide

This document describes how to integrate the E-commerce Smart Agent structured JSON logs with Grafana Loki for centralized log aggregation, search, and visualization.

## Overview

The application outputs structured JSON logs via ``app.core.structured_logging.JsonFormatter``. Each log line contains:

- ``timestamp`` - ISO-8601 formatted timestamp
- ``level`` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- ``logger`` - Logger name
- ``message`` - Log message
- ``correlation_id`` - Request correlation ID
- ``trace_id`` / ``span_id`` - OpenTelemetry trace context
- ``source_file`` / ``line_number`` - Source location
- ``stack_trace`` - Exception traceback (ERROR) or stack info (WARNING+)

## Architecture

```
┌─────────────────────────┐
│  E-commerce Smart Agent │
│  (JSON logs to stdout)  │
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    │               │
┌───▼────┐    ┌─────▼──────┐
│Filebeat│    │  Fluentd   │
└───┬────┘    └─────┬──────┘
    │               │
    └───────┬───────┘
            │
    ┌───────▼────────┐
    │  Grafana Loki  │
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │ Grafana Explore│
    │  (Dashboards)  │
    └────────────────┘
```

## Configuration

### Application Settings

Set the following environment variable in your ``.env`` file:

```bash
# JSON format for production (text for local development)
LOG_FORMAT=json
```

The application automatically configures the root logger and uvicorn loggers with ``JsonFormatter`` at startup.

### Option 1: Filebeat

Filebeat is recommended for VM or Docker deployments.

See ``configs/filebeat.yml`` for a complete configuration example.

Quick start:

```bash
# Install Filebeat (Debian/Ubuntu)
curl -L -O https://artifacts.elastic.co/downloads/beats/filebeat/filebeat-8.12.0-amd64.deb
sudo dpkg -i filebeat-8.12.0-amd64.deb

# Copy configuration
sudo cp configs/filebeat.yml /etc/filebeat/filebeat.yml

# Enable and start
sudo systemctl enable filebeat
sudo systemctl start filebeat
```

**Important**: The provided configuration uses the experimental Loki output. Alternatively, use the standard Elasticsearch output or install the [Grafana Loki Filebeat output plugin](https://github.com/grafana/loki/tree/main/clients/cmd/filebeat).

### Option 2: Fluentd

Fluentd is recommended for Kubernetes environments.

See ``configs/fluentd.conf`` for a complete configuration example.

Quick start with Docker:

```bash
# Build Fluentd image with Loki plugin
docker build -t fluentd-loki -f - . << 'EOF'
FROM fluent/fluentd:v1.16-debian
USER root
RUN gem install fluent-plugin-grafana-loki
USER fluent
COPY configs/fluentd.conf /fluentd/etc/fluent.conf
EOF

# Run
docker run -d \
  -v /var/log/ecommerce-agent:/var/log/ecommerce-agent:ro \
  -e ENVIRONMENT=production \
  fluentd-loki
```

### Option 3: Docker Logging Driver

For simple Docker deployments, use the Loki logging driver:

```bash
# Install the Loki Docker plugin
docker plugin install grafana/loki-docker-driver:latest --alias loki --grant-all-permissions

# Run the application
docker run -d \
  --log-driver=loki \
  --log-opt loki-url="http://loki:3100/loki/api/v1/push" \
  --log-opt loki-external-labels="job=ecommerce-agent,environment=production" \
  ecommerce-smart-agent:latest
```

## Grafana Dashboard Queries

### Basic Queries

Find all ERROR logs:

```logql
{job="ecommerce-agent"} |= "level": "ERROR"
```

Filter by correlation ID:

```logql
{job="ecommerce-agent"} |= "correlation_id": "abc123"
```

Filter by trace ID:

```logql
{job="ecommerce-agent"} |= "trace_id": "00000000000000000000000000abc123"
```

Filter by logger name:

```logql
{job="ecommerce-agent", logger="app.api.v1.chat"}
```

### Structured Queries with JSON Parser

Parse JSON and filter by level:

```logql
{job="ecommerce-agent"}
  | json
  | level = "ERROR"
```

Show error rate over time:

```logql
sum by (level) (
  rate(
    {job="ecommerce-agent"}
    | json
    | __error__ = ""
    [1m]
  )
)
```

Find slow requests with latency information:

```logql
{job="ecommerce-agent"}
  | json
  | latency_ms > 5000
```

### Stack Trace Analysis

Find all logs with stack traces:

```logql
{job="ecommerce-agent"}
  | json
  | stack_trace != ""
```

Count errors by exception type:

```logql
sum by (exception_type) (
  {job="ecommerce-agent"}
  | json
  | level = "ERROR"
  | pattern `<_?><exception_type>: <_?>`
  | __error__ = ""
  [5m]
)
```

## Alerting

Create Grafana alert rules based on log queries:

### High Error Rate

```logql
sum by (job) (
  rate(
    {job="ecommerce-agent"}
    | json
    | level = "ERROR"
    [5m]
  )
) > 0.1
```

### Critical Exceptions

```logql
{job="ecommerce-agent"}
  | json
  | level = "CRITICAL"
```

### Missing Correlation IDs

```logql
{job="ecommerce-agent"}
  | json
  | correlation_id = "-"
```

## Labels Best Practices

The following labels are recommended for efficient querying:

| Label | Source | Purpose |
|-------|--------|---------|
| ``job`` | Static | Identify the service |
| ``level`` | Log field | Filter by severity |
| ``logger`` | Log field | Filter by component |
| ``correlation_id`` | Log field | Trace a single request |
| ``trace_id`` | Log field | Distributed tracing correlation |
| ``environment`` | Static | Separate prod/staging/dev |

**Note**: Avoid high-cardinality labels (like raw trace_id) in stream labels if you have high traffic. Instead, use log line filtering.

## Performance Considerations

1. **Batching**: Configure Filebeat/Fluentd to batch log lines before sending to Loki
2. **Compression**: Enable gzip compression on the Loki client
3. **Buffering**: Use persistent queues to survive network outages
4. **Log Level**: In production, consider setting the minimum log level to INFO to reduce volume
5. **Sampling**: For high-traffic services, consider log sampling for DEBUG/INFO levels

## Troubleshooting

### Logs Not Appearing in Loki

1. Verify the application is outputting JSON:
   ```bash
   docker logs ecommerce-agent | head -n 5
   ```

2. Check Filebeat/Fluentd logs:
   ```bash
   sudo journalctl -u filebeat -f
   docker logs fluentd
   ```

3. Verify Loki is accessible:
   ```bash
   curl http://loki:3100/ready
   ```

### Incorrect Timestamp Parsing

If timestamps appear wrong in Grafana, verify the time format in the parser configuration matches the application output:

```python
# Application format (ISO-8601 with timezone)
"2024-01-15T09:30:00.123456+00:00"
```

### High Memory Usage

If the log shipper uses too much memory:

1. Reduce ``batch_size`` and ``queue_limit_length``
2. Increase ``flush_interval``
3. Add log level filtering at the shipper level

## References

- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [LogQL Reference](https://grafana.com/docs/loki/latest/query/)
- [Filebeat Loki Output](https://github.com/grafana/loki/tree/main/clients/cmd/filebeat)
- [Fluentd Loki Plugin](https://grafana.com/docs/loki/latest/send-data/fluentd/)
