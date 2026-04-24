# app/observability/otel_setup.py
"""OpenTelemetry setup for FastAPI and Celery instrumentation."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult

from app.core.config import settings


class NoOpSpanExporter(SpanExporter):
    """No-op span exporter for environments without an OTLP collector."""

    def export(self, spans):
        _ = spans
        return SpanExportResult.SUCCESS

    def shutdown(self): ...

    def force_flush(self, timeout_millis=30000):
        _ = timeout_millis
        return True


def setup_otel_tracing(service_name: str = "ecommerce-smart-agent") -> TracerProvider:
    """Configure OpenTelemetry tracing with OTLP or no-op export."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    exporter = OTLPSpanExporter(endpoint=endpoint, timeout=5) if endpoint else NoOpSpanExporter()

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)
    return provider


def instrument_fastapi(app) -> None:
    """Instrument a FastAPI application with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(app)


def setup_celery_tracing() -> None:
    """Instrument Celery with OpenTelemetry tracing.

    Must be called after the Celery app is created and before tasks are
    dispatched so that trace context is automatically propagated across
    the broker boundary.
    """
    CeleryInstrumentor().instrument()
