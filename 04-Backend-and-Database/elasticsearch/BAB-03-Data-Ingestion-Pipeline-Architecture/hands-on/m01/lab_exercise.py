#!/usr/bin/env python3
"""
Lab Exercise M01: Ingest Pipeline Architecture & Processor Simulation
BAB-03: Data Ingestion Pipeline Architecture (Elasticsearch)

Simulasi mandiri Ingest Node pipeline processor, document enrichment,
conditional execution, drop conditions, serta on_failure handling.
"""

import re
import sys
import time
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


class IngestProcessorException(Exception):
    """Exception khusus kegagalan eksekusi processor."""
    pass


class IngestPipelineSimulator:
    """Simulasi Ingest Pipeline Node Elasticsearch dengan dukungan berbagai processor standar."""

    def __init__(self, pipeline_id: str, description: str):
        self.pipeline_id = pipeline_id
        self.description = description
        self.processors: List[Dict[str, Any]] = []
        self.on_failure: List[Dict[str, Any]] = []

    def add_processor(self, processor_type: str, config: Dict[str, Any]) -> None:
        self.processors.append({"type": processor_type, "config": config})

    def add_on_failure_processor(self, processor_type: str, config: Dict[str, Any]) -> None:
        self.on_failure.append({"type": processor_type, "config": config})

    def _execute_processor(self, processor: Dict[str, Any], doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        p_type = processor["type"]
        cfg = processor["config"]

        # Evaluasi kondisi 'if' (Painless conditional simulation)
        if "if" in cfg:
            condition = cfg["if"]
            try:
                # Simulasi sederhana ekspresi kondisi boolean
                ctx = {"ctx": doc}
                if not eval(condition, {"__builtins__": {}}, ctx):
                    return True, "Skipped by conditional if"
            except Exception as e:
                raise IngestProcessorException(f"Condition evaluation error '{condition}': {str(e)}")

        if p_type == "grok":
            field = cfg["field"]
            pattern = cfg["pattern"]
            target_field = cfg.get("target_field")
            if field not in doc:
                raise IngestProcessorException(f"Field '{field}' tidak ditemukan pada dokumen")
            raw_val = str(doc[field])
            match = re.match(pattern, raw_val)
            if not match:
                raise IngestProcessorException(f"Grok pattern mismatch untuk input: '{raw_val}'")
            extracted = match.groupdict()
            if target_field:
                doc[target_field] = extracted
            else:
                doc.update(extracted)

        elif p_type == "date":
            field = cfg["field"]
            target_field = cfg.get("target_field", "@timestamp")
            formats = cfg.get("formats", ["%d/%b/%Y:%H:%M:%S %z"])
            if field not in doc:
                raise IngestProcessorException(f"Field '{field}' tidak ada untuk date parsing")
            raw_date = doc[field]
            parsed = False
            for fmt in formats:
                try:
                    dt = datetime.strptime(raw_date, fmt)
                    doc[target_field] = dt.astimezone(timezone.utc).isoformat()
                    parsed = True
                    break
                except ValueError:
                    continue
            if not parsed:
                raise IngestProcessorException(f"Gagal memparsing format tanggal '{raw_date}'")

        elif p_type == "convert":
            field = cfg["field"]
            target_type = cfg["type"]
            target_field = cfg.get("target_field", field)
            if field in doc:
                try:
                    if target_type == "integer":
                        doc[target_field] = int(doc[field])
                    elif target_type == "float":
                        doc[target_field] = float(doc[field])
                    elif target_type == "boolean":
                        doc[target_field] = bool(doc[field])
                    elif target_type == "string":
                        doc[target_field] = str(doc[field])
                except (ValueError, TypeError) as err:
                    raise IngestProcessorException(f"Konversi field '{field}' ke {target_type} gagal: {err}")

        elif p_type == "set":
            field = cfg["field"]
            value = cfg["value"]
            doc[field] = value

        elif p_type == "rename":
            field = cfg["field"]
            target_field = cfg["target_field"]
            if field in doc:
                doc[target_field] = doc.pop(field)
            elif not cfg.get("ignore_missing", False):
                raise IngestProcessorException(f"Field '{field}' tidak ditemukan untuk rename")

        elif p_type == "remove":
            field = cfg["field"]
            if field in doc:
                del doc[field]
            elif not cfg.get("ignore_missing", False):
                raise IngestProcessorException(f"Field '{field}' tidak ditemukan untuk remove")

        elif p_type == "geoip_mock":
            field = cfg["field"]
            target_field = cfg.get("target_field", "geoip")
            ip = doc.get(field, "")
            # Simulasi enrichment GeoIP database lookup
            if ip.startswith("10.") or ip.startswith("192.168.") or ip == "127.0.0.1":
                doc[target_field] = {"country_name": "Private Network", "continent_code": "LOC", "location": {"lat": 0.0, "lon": 0.0}}
            else:
                doc[target_field] = {"country_name": "Indonesia", "country_iso_code": "ID", "city_name": "Jakarta", "location": {"lat": -6.2088, "lon": 106.8456}}

        else:
            raise IngestProcessorException(f"Tipe processor tidak dikenal: '{p_type}'")

        return True, "Success"

    def simulate(self, raw_document: Dict[str, Any]) -> Dict[str, Any]:
        """Meniru endpoint Elasticsearch _ingest/pipeline/<id>/_simulate"""
        doc = json.loads(json.dumps(raw_document))  # deep copy
        trace_logs = []
        pipeline_status = "SUCCESS"

        print(f"\n{Colors.BOLD}{Colors.CYAN}--- Memulai Ingestion Document [{doc.get('_id', 'gen-id')}] ---{Colors.RESET}")
        print(f"{Colors.YELLOW}Dokumen Awal:{Colors.RESET} {json.dumps(doc)}")

        idx = 1
        failed = False
        error_info: Optional[str] = None

        for proc in self.processors:
            step_name = f"{proc['type'].upper()} ({json.dumps(proc['config'])})"
            start_t = time.perf_counter_ns()
            try:
                ok, note = self._execute_processor(proc, doc)
                dur_ms = (time.perf_counter_ns() - start_t) / 1_000_000
                trace_logs.append({"step": idx, "type": proc["type"], "status": "OK", "duration_ms": round(dur_ms, 3), "note": note})
                print(f"  [{Colors.GREEN}STEP {idx:02d}{Colors.RESET}] {Colors.BOLD}{proc['type']}{Colors.RESET} -> {note} ({dur_ms:.3f}ms)")
            except IngestProcessorException as exc:
                dur_ms = (time.perf_counter_ns() - start_t) / 1_000_000
                error_info = str(exc)
                trace_logs.append({"step": idx, "type": proc["type"], "status": "FAILED", "duration_ms": round(dur_ms, 3), "error": error_info})
                print(f"  [{Colors.RED}STEP {idx:02d} FAILED{Colors.RESET}] {Colors.BOLD}{proc['type']}{Colors.RESET} -> Error: {error_info}")
                failed = True
                break
            idx += 1

        if failed:
            pipeline_status = "TRIGGERED_ON_FAILURE"
            print(f"\n{Colors.RED}{Colors.BOLD}Memanggil blok on_failure pipeline...{Colors.RESET}")
            doc["_error"] = {"message": error_info, "failed_step": idx, "timestamp": datetime.now(timezone.utc).isoformat()}
            of_idx = 1
            for of_proc in self.on_failure:
                try:
                    self._execute_processor(of_proc, doc)
                    print(f"  [{Colors.YELLOW}ON_FAILURE {of_idx:02d}{Colors.RESET}] {of_proc['type']} berhasil diaplikasikan.")
                except Exception as of_err:
                    print(f"  [{Colors.RED}FATAL ON_FAILURE{Colors.RESET}] Gagal menangani error: {of_err}")
                of_idx += 1

        print(f"\n{Colors.GREEN}{Colors.BOLD}Status Pipeline:{Colors.RESET} {Colors.HEADER}{pipeline_status}{Colors.RESET}")
        print(f"{Colors.GREEN}Dokumen Hasil Akhir:{Colors.RESET}")
        print(json.dumps(doc, indent=2))

        return {
            "status": pipeline_status,
            "document": doc,
            "trace": trace_logs,
            "error": error_info
        }


def build_ecommerce_access_pipeline() -> IngestPipelineSimulator:
    """Membangun arsitektur pipeline log akses web e-commerce."""
    pipeline = IngestPipelineSimulator(
        pipeline_id="ecommerce-access-logs-pipeline",
        description="Parsing, enrichment, date normalizing, and routing for web access events."
    )

    # 1. Grok Processor: parsing format access log gabungan
    # Pattern: ^(?P<client_ip>\S+) - (?P<ident>\S+) \[(?P<log_time>[^\]]+)\] "(?P<http_method>\S+) (?P<request_url>\S+) HTTP/(?P<http_version>\S+)" (?P<response_code>\d+) (?P<body_bytes_sent>\d+) (?P<duration_ms>\d+)$
    grok_pattern = (
        r'^(?P<client_ip>\S+)\s+-\s+(?P<ident>\S+)\s+\[(?P<log_time>[^\]]+)\]\s+'
        r'"(?P<http_method>\S+)\s+(?P<request_url>\S+)\s+HTTP/(?P<http_version>\S+)"\s+'
        r'(?P<response_code>\d+)\s+(?P<body_bytes_sent>\d+)\s+(?P<duration_ms>\d+)$'
    )
    pipeline.add_processor("grok", {"field": "message", "pattern": grok_pattern})

    # 2. Date Processor: parse '06/Oct/2026:14:32:10 +0700' ke ISO8601 @timestamp
    pipeline.add_processor("date", {
        "field": "log_time",
        "target_field": "@timestamp",
        "formats": ["%d/%b/%Y:%H:%M:%S %z"]
    })

    # 3. Convert Processor: Ubah response_code, body_bytes_sent, duration_ms ke tipe numerik
    pipeline.add_processor("convert", {"field": "response_code", "type": "integer"})
    pipeline.add_processor("convert", {"field": "body_bytes_sent", "type": "integer"})
    pipeline.add_processor("convert", {"field": "duration_ms", "type": "integer"})

    # 4. GeoIP Processor: Enrichment lokasi geografis berdasarkan client_ip
    pipeline.add_processor("geoip_mock", {"field": "client_ip", "target_field": "source_geo"})

    # 5. Set Processor dengan Conditional Painless logic: Tandai slow request jika duration_ms > 2000
    pipeline.add_processor("set", {
        "if": "ctx.get('duration_ms', 0) > 2000",
        "field": "event.performance_tier",
        "value": "SLOW_LATENCY_ALERT"
    })

    # 6. Set Environment tag
    pipeline.add_processor("set", {"field": "environment", "value": "production-cluster"})

    # 7. Remove raw unparsed redundant fields
    pipeline.add_processor("remove", {"field": "ident", "ignore_missing": True})
    pipeline.add_processor("remove", {"field": "log_time", "ignore_missing": True})

    # On Failure Processors (DLQ / Fallback Routing)
    pipeline.add_on_failure_processor("set", {"field": "_target_index", "value": "dead-letter-queue-ingest"})
    pipeline.add_on_failure_processor("set", {"field": "tags", "value": ["pipeline_parse_failure"]})

    return pipeline


def print_banner() -> None:
    print(f"{Colors.HEADER}{Colors.BOLD}" + "=" * 70)
    print(" ELASTICSEARCH INGEST PIPELINE ARCHITECTURE (BAB-03) - SIMULATOR")
    print("=" * 70 + f"{Colors.RESET}")
    print(f"{Colors.CYAN}Simulasi interaktif Ingest Node, Processor Chaining, dan Error Recovery.{Colors.RESET}\n")


def run_interactive_lab():
    print_banner()
    pipeline = build_ecommerce_access_pipeline()

    sample_logs = [
        {
            "title": "Log Normal (Checkout API - Fast)",
            "doc": {
                "_id": "doc-101",
                "_index": "logs-ecommerce-raw",
                "message": '202.67.40.15 - frank [06/Oct/2026:14:32:10 +0700] "POST /api/v1/checkout HTTP/1.1" 200 4820 185'
            }
        },
        {
            "title": "Log Slow Request (Catalog Query - Trigger Conditional Processor)",
            "doc": {
                "_id": "doc-102",
                "_index": "logs-ecommerce-raw",
                "message": '192.168.1.50 - internal_bot [06/Oct/2026:14:32:15 +0700] "GET /api/v1/search?q=laptop HTTP/1.1" 200 89400 3250'
            }
        },
        {
            "title": "Log Malformed (Grok Mismatch -> Trigger on_failure / DLQ routing)",
            "doc": {
                "_id": "doc-103",
                "_index": "logs-ecommerce-raw",
                "message": 'MALFORMED RAW PACKET DUMP NO HTTP HEADER FORMAT 500 ERROR'
            }
        }
    ]

    while True:
        print(f"\n{Colors.BOLD}--- Pilihan Menu Lab ---{Colors.RESET}")
        for i, s in enumerate(sample_logs, 1):
            print(f" {i}. Uji Sample: {s['title']}")
        print(" 4. Masukkan Log Custom Mandiri")
        print(" 5. Tampilkan Arsitektur & Metadata Pipeline")
        print(" 0. Keluar")

        try:
            choice = input(f"\n{Colors.YELLOW}Pilih opsi [0-5]: {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab.")
            break

        if choice == "0":
            print(f"{Colors.GREEN}Selesai. Lab simulasi Ingest Pipeline ditutup.{Colors.RESET}")
            break
        elif choice in ["1", "2", "3"]:
            selected = sample_logs[int(choice) - 1]
            print(f"\n{Colors.BOLD}>>> Menjalankan Kasus: {selected['title']} <<<{Colors.RESET}")
            pipeline.simulate(selected["doc"])
        elif choice == "4":
            custom_msg = input("Masukkan raw access log message: ").strip()
            if not custom_msg:
                print(f"{Colors.RED}Message tidak boleh kosong.{Colors.RESET}")
                continue
            custom_doc = {
                "_id": f"custom-{int(time.time())}",
                "_index": "logs-custom-raw",
                "message": custom_msg
            }
            pipeline.simulate(custom_doc)
        elif choice == "5":
            print(f"\n{Colors.CYAN}{Colors.BOLD}Pipeline Definition ID:{Colors.RESET} {pipeline.pipeline_id}")
            print(f"{Colors.CYAN}Description:{Colors.RESET} {pipeline.description}")
            print(f"\n{Colors.BOLD}Registered Processors ({len(pipeline.processors)}):{Colors.RESET}")
            for p_idx, p in enumerate(pipeline.processors, 1):
                print(f"  {p_idx}. Type: {Colors.GREEN}{p['type']}{Colors.RESET} | Config: {json.dumps(p['config'])}")
            print(f"\n{Colors.BOLD}On-Failure Handlers ({len(pipeline.on_failure)}):{Colors.RESET}")
            for of_idx, of_p in enumerate(pipeline.on_failure, 1):
                print(f"  {of_idx}. Type: {Colors.RED}{of_p['type']}{Colors.RESET} | Config: {json.dumps(of_p['config'])}")
        else:
            print(f"{Colors.RED}Pilihan tidak valid. Silakan pilih 0-5.{Colors.RESET}")


if __name__ == "__main__":
    # Jika dijalankan non-interaktif atau dengan argument test
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print(f"{Colors.GREEN}Running automatic smoke test...{Colors.RESET}")
        p = build_ecommerce_access_pipeline()
        res = p.simulate({
            "_id": "test-doc",
            "message": '202.67.40.15 - frank [06/Oct/2026:14:32:10 +0700] "POST /api/v1/checkout HTTP/1.1" 200 4820 185'
        })
        assert res["status"] == "SUCCESS", "Pipeline test failed!"
        print(f"{Colors.GREEN}Automated test passed successfully!{Colors.RESET}")
        sys.exit(0)

    run_interactive_lab()
