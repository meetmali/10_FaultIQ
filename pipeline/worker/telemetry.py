"""OpenTelemetry tracing for the worker (ADR 0012).

Spans always exist, so every log line about a job carries the trace ID of the API request that
queued it. They are exported over OTLP/HTTP only when OTEL_EXPORTER_OTLP_ENDPOINT is set. Spans
never carry sensor values, file contents or credentials.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing() -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": "faultiq-worker"}))
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    return provider
