#!/usr/bin/env python3
"""
OpenTelemetry Tracing & Exemplar Pipeline Demo
Standar: Kurikulum SRE GEMINI.md - Bab 05

Skrip ini mendemonstrasikan implementasi produksi:
1. Inisialisasi OpenTelemetry SDK (Tracer & Meter)
2. Propagasi Konteks Manual berbasis Standar W3C TraceContext
3. Sanitasi High Cardinality Attributes (Pencegahan TSDB Explosion)
4. Pencatatan Metrik Histogram dengan Exemplars Terkorelasi
"""

import time
import random
import re
from typing import Dict, Any

# OpenTelemetry Tracing API & SDK
from opentelemetry import trace, metrics
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

# OpenTelemetry Metrics SDK
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter


# ============================================================================
# 1. SETUP TELEMETRY PROVIDERS & PROPAGATORS
# ============================================================================
resource = Resource.create({
    "service.name": "checkout-transaction-engine",
    "service.version": "1.4.0",
    "deployment.environment": "production"
})

# Setup Tracing Pipeline
trace_provider = TracerProvider(resource=resource)
span_processor = BatchSpanProcessor(ConsoleSpanExporter())
trace_provider.add_span_processor(span_processor)
trace.set_tracer_provider(trace_provider)

# Setup Metrics Pipeline
metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=10000)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)

# Get Instances
tracer = trace.get_tracer("sre.deep.observability.tracer", "1.0.0")
meter = metrics.get_meter("sre.deep.observability.meter", "1.0.0")

# Setup W3C Trace Context Propagator
propagator = TraceContextTextMapPropagator()

# Inisialisasi Metric: Latency Histogram
checkout_duration_histogram = meter.create_histogram(
    name="http_server_duration_milliseconds",
    description="Durasi eksekusi transaksi checkout dengan pelacakan Exemplar",
    unit="ms"
)


# ============================================================================
# 2. HIGH CARDINALITY ATTRIBUTE SANITIZER
# ============================================================================
class TelemetrySanitizer:
    """
    Sanitizer untuk mencegah polusi label pada TSDB dan kebocoran data sensitif (PII).
    Memisahkan data dimensi aman (label TSDB) dari data jejak (Span attributes).
    """
    SENSITIVE_PATTERNS = [
        (re.compile(r"card|token|secret|password", re.IGNORECASE), "[REDACTED]"),
        (re.compile(r"^\d{4}-\d{4}-\d{4}-\d{4}$"), "[CARD_MASKED]"),
    ]

    @classmethod
    def sanitize_metric_attributes(cls, raw_attributes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hanya mengizinkan label kardinalitas rendah untuk metrik TSDB.
        """
        ALLOWED_METRIC_KEYS = {"http.method", "http.route", "http.status_code"}
        sanitized = {}
        for k, v in raw_attributes.items():
            if k in ALLOWED_METRIC_KEYS:
                sanitized[k] = v
        return sanitized

    @classmethod
    def sanitize_span_attributes(cls, raw_attributes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Menyaring data sensitif sebelum disimpan ke dalam Tracing Span backend.
        """
        cleaned = {}
        for k, v in raw_attributes.items():
            str_v = str(v)
            is_sensitive = False
            for pattern, mask in cls.SENSITIVE_PATTERNS:
                if pattern.search(k) or pattern.search(str_v):
                    cleaned[k] = mask
                    is_sensitive = True
                    break
            if not is_sensitive:
                cleaned[k] = v
        return cleaned


# ============================================================================
# 3. MICROSERVICES SIMULATION WITH W3C PROPAGATION
# ============================================================================
def mock_payment_downstream_service(carrier_headers: Dict[str, str]):
    """
    Mensimulasikan downstream microservice yang mengekstrak konteks W3C dari header.
    """
    extracted_context = propagator.extract(carrier=carrier_headers)
    
    with tracer.start_as_current_span("payment_downstream_process", context=extracted_context) as child_span:
        current_span_context = child_span.get_span_context()
        trace_id = format(current_span_context.trace_id, "032x")
        span_id = format(current_span_context.span_id, "016x")
        
        child_span.set_attribute("rpc.system", "grpc")
        child_span.set_attribute("rpc.service", "PaymentVault")
        
        # Simulasi latensi eksekusi
        execution_time = random.uniform(0.05, 0.20)
        time.sleep(execution_time)
        
        print(f"  [Payment Service] Terkoneksi ke downstream! TraceID: {trace_id}, ParentSpanID: {span_id}")


def mock_checkout_api_endpoint(request_payload: Dict[str, Any]):
    """
    Mensimulasikan API Gateway Ingress yang menerima HTTP request tanpa context,
    membuat root trace, mencatat latensi dengan Exemplar, dan memanggil downstream.
    """
    start_time = time.time()
    raw_attributes = {
        "http.method": "POST",
        "http.route": "/api/v1/checkout",
        "http.status_code": 200,
        "user.id": request_payload.get("user_id"),                  # High Cardinality
        "user.email": request_payload.get("user_email"),            # PII
        "payment.card_number": request_payload.get("credit_card"),  # Sensitive
    }

    # Mulai Root Span
    with tracer.start_as_current_span("ingress_checkout_transaction") as root_span:
        span_ctx = root_span.get_span_context()
        trace_id = format(span_ctx.trace_id, "032x")
        
        # 1. Sanitasi dan Set Atribut Span
        safe_span_attrs = TelemetrySanitizer.sanitize_span_attributes(raw_attributes)
        root_span.set_attributes(safe_span_attrs)

        # 2. Simulasi Propagasi Konteks Keluar (Outbound W3C Injection)
        carrier = {}
        propagator.inject(carrier=carrier)
        print(f"\n[API Gateway] Transaksi Diterima. TraceID: {trace_id}")
        print(f"[API Gateway] Terbentuk W3C Header traceparent: {carrier.get('traceparent')}")

        # 3. Panggil Downstream Service
        mock_payment_downstream_service(carrier_headers=carrier)

        # 4. Rekam Latensi Akhir
        duration_ms = (time.time() - start_time) * 1000

        # Sanitasi dimensi metrik untuk mencegah High Cardinality TSDB Explosion
        safe_metric_labels = TelemetrySanitizer.sanitize_metric_attributes(raw_attributes)

        # Injeksi Exemplar langsung mengaitkan TraceID saat ini ke histogram metrik
        # Di OpenTelemetry Python SDK, context trace aktif otomatis ditautkan sebagai Exemplar
        checkout_duration_histogram.record(
            amount=duration_ms,
            attributes=safe_metric_labels
        )
        print(f"[API Gateway] Latensi Transaksi: {duration_ms:.2f}ms dicatat dengan aman ke TSDB.")


# ============================================================================
# 4. EXECUTION DRIVER
# ============================================================================
if __name__ == "__main__":
    print("==================================================================")
    print("🚀 MENJALANKAN OPENTELEMETRY TRACING & EXEMPLAR PIPELINE DEMO")
    print("==================================================================")

    # Payload simulasi request dengan dimensi berbahaya (High Cardinality & PII)
    sample_requests = [
        {
            "user_id": "usr_998124_alpha",
            "user_email": "budi.santoso@corporate.id",
            "credit_card": "4532-1234-5678-9012"
        },
        {
            "user_id": "usr_771239_beta",
            "user_email": "siti.aminah@startup.io",
            "credit_card": "5500-9876-5432-1098"
        }
    ]

    for req in sample_requests:
        mock_checkout_api_endpoint(req)
        time.sleep(1)

    print("\n[INFO] Menunggu flush exporter telemetri...")
    # Memberi waktu bagi Batch Processor dan Periodic Metric Reader untuk ekspor ke console
    time.sleep(2)
    print("Selesai.")