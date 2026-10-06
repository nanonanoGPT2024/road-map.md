#!/usr/bin/env python3
"""
===============================================================================
LAB EXERCISE: COMPLEX AGGREGATIONS & REAL-TIME ANALYTICS ENGINE SIMULATOR
Topic    : Elasticsearch BAB-05 - Complex Aggregations & Analytics Engine
Runtime  : Python 3.8+ (Zero External Dependencies - Standard Library Only)
===============================================================================
"""

import sys
import json
import math
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# ANSI Color Palette for High-Impact Terminal UX
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[48;5;236m"
    HEADER_ACCENT = "\033[38;5;208m"

def print_banner():
    banner = f"""
{TermColor.CYAN}{TermColor.BOLD}===============================================================================
  ELASTICSEARCH ANALYTICS ENGINE: COMPLEX AGGREGATION & PIPELINE LAB
  Architecture: Bucket -> Nested Metrics -> Pipeline Derivatives -> Slicing
==============================================================================={TermColor.RESET}"""
    print(banner)

class MockElasticsearchCluster:
    """Simulates distributed Lucene segments & Elasticsearch Aggregation Core."""

    def __init__(self, doc_count: int = 1200):
        self.doc_count = doc_count
        self.documents: List[Dict[str, Any]] = []
        self._seed_production_dataset()

    def _seed_production_dataset(self):
        services = ["auth-service", "checkout-api", "payment-gateway", "search-indexer"]
        regions = ["ap-southeast-1", "us-east-1", "eu-central-1"]
        base_time = datetime.now() - timedelta(hours=24)

        random.seed(42)  # Deterministic dataset
        for i in range(self.doc_count):
            t_offset = random.uniform(0, 86400)
            timestamp = base_time + timedelta(seconds=t_offset)
            service = random.choice(services)
            region = random.choice(regions)

            # Synthetic latency distribution: log-normal with occasional spikes
            base_latency = 45.0 if service != "search-indexer" else 120.0
            latency = random.lognormvariate(math.log(base_latency), 0.5)
            if random.random() < 0.04:  # 4% catastrophic latency tail
                latency *= random.uniform(4.0, 9.0)

            # Status codes
            status = 200
            err_roll = random.random()
            if err_roll < 0.05:
                status = 500
            elif err_roll < 0.12:
                status = 429
            elif err_roll < 0.18:
                status = 404

            # Synthetic transaction value
            tx_amount = round(random.expovariate(1 / 150.0), 2) if service == "payment-gateway" else 0.0

            self.documents.append({
                "id": f"doc-{i:05d}",
                "@timestamp": timestamp.isoformat(),
                "timestamp_epoch": timestamp.timestamp(),
                "service": service,
                "region": region,
                "response_time_ms": round(latency, 2),
                "status_code": status,
                "transaction_amount": tx_amount
            })

    def execute_dsl_aggregation(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Parses and computes aggregations similarly to Elasticsearch nodes."""
        start_time = time.perf_counter()

        filtered_docs = self.documents
        # Handle simple query match filter
        if "query" in query:
            q_bool = query["query"].get("bool", {})
            if "filter" in q_bool:
                filters = q_bool["filter"]
                for f in filters:
                    if "term" in f:
                        for k, v in f["term"].items():
                            filtered_docs = [d for d in filtered_docs if d.get(k) == v]

        aggs = query.get("aggs", {})
        results: Dict[str, Any] = {}

        for agg_name, agg_spec in aggs.items():
            if "date_histogram" in agg_spec:
                results[agg_name] = self._run_date_histogram(filtered_docs, agg_spec)
            elif "terms" in agg_spec:
                results[agg_name] = self._run_terms_aggregation(filtered_docs, agg_spec)
            elif "percentiles" in agg_spec:
                results[agg_name] = self._run_percentiles(filtered_docs, agg_spec["percentiles"]["field"])

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "took": round(elapsed_ms, 2),
            "timed_out": False,
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {"total": {"value": len(filtered_docs), "relation": "eq"}},
            "aggregations": results
        }

    def _run_terms_aggregation(self, docs: List[Dict[str, Any]], spec: Dict[str, Any]) -> Dict[str, Any]:
        field = spec["terms"]["field"]
        sub_aggs = spec.get("aggs", {})
        groups: Dict[str, List[Dict[str, Any]]] = {}

        for d in docs:
            val = str(d.get(field, "unknown"))
            groups.setdefault(val, []).append(d)

        buckets = []
        for key, bucket_docs in groups.items():
            b_item: Dict[str, Any] = {
                "key": key,
                "doc_count": len(bucket_docs)
            }
            # Process sub-aggregations (multi-level aggregation)
            for sub_name, sub_spec in sub_aggs.items():
                if "avg" in sub_spec:
                    f = sub_spec["avg"]["field"]
                    vals = [d[f] for d in bucket_docs if f in d]
                    b_item[sub_name] = {"value": round(sum(vals) / len(vals), 2) if vals else 0.0}
                elif "percentiles" in sub_spec:
                    f = sub_spec["percentiles"]["field"]
                    b_item[sub_name] = self._run_percentiles(bucket_docs, f)
            buckets.append(b_item)

        # Order by doc_count desc
        buckets.sort(key=lambda x: x["doc_count"], reverse=True)
        return {"doc_count_error_upper_bound": 0, "sum_other_doc_count": 0, "buckets": buckets}

    def _run_date_histogram(self, docs: List[Dict[str, Any]], spec: Dict[str, Any]) -> Dict[str, Any]:
        calendar_interval = spec["date_histogram"].get("fixed_interval", "4h")
        sub_aggs = spec.get("aggs", {})
        interval_secs = 14400 if calendar_interval == "4h" else 3600

        buckets_map: Dict[int, List[Dict[str, Any]]] = {}
        for d in docs:
            bucket_key = int(d["timestamp_epoch"] // interval_secs) * interval_secs
            buckets_map.setdefault(bucket_key, []).append(d)

        sorted_keys = sorted(buckets_map.keys())
        buckets = []

        cumulative_counter = 0.0
        prev_avg_latency = None

        for k in sorted_keys:
            b_docs = buckets_map[k]
            iso_key = datetime.fromtimestamp(k).strftime("%Y-%m-%d %H:%M:%S")
            b_item: Dict[str, Any] = {
                "key_as_string": iso_key,
                "key": k * 1000,
                "doc_count": len(b_docs)
            }

            # Evaluate metric sub-aggregations
            for s_name, s_spec in sub_aggs.items():
                if "avg" in s_spec:
                    f = s_spec["avg"]["field"]
                    vals = [d[f] for d in b_docs if f in d]
                    avg_val = round(sum(vals) / len(vals), 2) if vals else 0.0
                    b_item[s_name] = {"value": avg_val}
                elif "sum" in s_spec:
                    f = s_spec["sum"]["field"]
                    vals = [d[f] for d in b_docs if f in d]
                    b_item[s_name] = {"value": round(sum(vals), 2)}

            # Pipeline Aggregation Simulation: cumulative_sum & derivative
            for s_name, s_spec in sub_aggs.items():
                if "cumulative_sum" in s_spec:
                    target_metric = s_spec["cumulative_sum"]["buckets_path"]
                    val = b_item.get(target_metric, {}).get("value", b_item["doc_count"])
                    cumulative_counter += val
                    b_item[s_name] = {"value": round(cumulative_counter, 2)}

                elif "derivative" in s_spec:
                    target_metric = s_spec["derivative"]["buckets_path"]
                    curr_val = b_item.get(target_metric, {}).get("value", 0.0)
                    if prev_avg_latency is not None:
                        diff = round(curr_val - prev_avg_latency, 2)
                        b_item[s_name] = {"value": diff}
                    else:
                        b_item[s_name] = {"value": None, "note": "null_first_bucket"}
                    prev_avg_latency = curr_val

            buckets.append(b_item)

        return {"buckets": buckets}

    @staticmethod
    def _run_percentiles(docs: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
        vals = sorted([d[field] for d in docs if field in d])
        if not vals:
            return {"values": {"50.0": 0.0, "90.0": 0.0, "95.0": 0.0, "99.0": 0.0}}

        def get_p(p: float) -> float:
            k = (len(vals) - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return float(vals[int(k)])
            d0 = vals[int(f)] * (c - k)
            d1 = vals[int(c)] * (k - f)
            return round(d0 + d1, 2)

        return {
            "values": {
                "50.0": get_p(50.0),
                "90.0": get_p(90.0),
                "95.0": get_p(95.0),
                "99.0": get_p(99.0)
            }
        }


class AggregationLabCLI:
    """Terminal Command Center for complex analytics queries."""

    def __init__(self):
        self.cluster = MockElasticsearchCluster(doc_count=2500)

    def run_menu(self):
        print_banner()
        print(f"{TermColor.GREEN}[INFO]{TermColor.RESET} In-memory Elastic cluster online: {self.cluster.doc_count} logs ingested.")
        print(f"{TermColor.DIM}Index: production-telemetry-logs-2026.10 / Shards: 5 Primary{TermColor.RESET}\n")

        while True:
            print(f"{TermColor.BOLD}{TermColor.YELLOW}--- ANALYTICS LAB SCENARIOS ---{TermColor.RESET}")
            print(f" {TermColor.CYAN}1.{TermColor.RESET} Multi-Tier Terms Aggregation (Service -> Latency Stats & Percentiles)")
            print(f" {TermColor.CYAN}2.{TermColor.RESET} Date Histogram + Pipeline Derivative (SLA Degradation Velocity)")
            print(f" {TermColor.CYAN}3.{TermColor.RESET} Cumulative Sum Pipeline (Financial GMV Ingestion Curve)")
            print(f" {TermColor.CYAN}4.{TermColor.RESET} P99 Latency Anomaly Detector (Bucket Selector Filter)")
            print(f" {TermColor.CYAN}5.{TermColor.RESET} Inspect Raw Generated DSL Query & Elastic Payload")
            print(f" {TermColor.RED}0. Exit Simulator{TermColor.RESET}")

            choice = input(f"\n{TermColor.BOLD}Select Lab Scenario [0-5]: {TermColor.RESET}").strip()

            if choice == "1":
                self.scenario_multi_tier_terms()
            elif choice == "2":
                self.scenario_pipeline_derivative()
            elif choice == "3":
                self.scenario_cumulative_sum()
            elif choice == "4":
                self.scenario_p99_anomaly_detector()
            elif choice == "5":
                self.scenario_inspect_dsl()
            elif choice in ("0", "exit", "quit"):
                print(f"\n{TermColor.GREEN}Shutting down Analytics Simulator. Lab completed successfully!{TermColor.RESET}")
                sys.exit(0)
            else:
                print(f"{TermColor.RED}[ERROR] Invalid selection, try again.{TermColor.RESET}\n")

    def scenario_multi_tier_terms(self):
        print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}>>> SCENARIO 1: Multi-Tier Terms Bucket Aggregation{TermColor.RESET}")
        dsl = {
            "size": 0,
            "aggs": {
                "per_service": {
                    "terms": {"field": "service", "size": 5},
                    "aggs": {
                        "avg_latency": {"avg": {"field": "response_time_ms"}},
                        "latency_percentiles": {"percentiles": {"field": "response_time_ms"}}
                    }
                }
            }
        }
        res = self.cluster.execute_dsl_aggregation(dsl)
        print(f"{TermColor.DIM}Executed in {res['took']} ms across {res['hits']['total']['value']} documents.{TermColor.RESET}\n")

        print(f"{'SERVICE':<20} | {'DOC COUNT':<10} | {'AVG LATENCY':<12} | {'P50 (ms)':<10} | {'P95 (ms)':<10} | {'P99 (ms)':<10}")
        print("-" * 84)
        for b in res["aggregations"]["per_service"]["buckets"]:
            srv = b["key"]
            cnt = b["doc_count"]
            avg_lat = b["avg_latency"]["value"]
            p = b["latency_percentiles"]["values"]
            print(f"{TermColor.CYAN}{srv:<20}{TermColor.RESET} | {cnt:<10} | {avg_lat:<12.2f} | {p['50.0']:<10.2f} | {p['95.0']:<10.2f} | {TermColor.RED}{p['99.0']:<10.2f}{TermColor.RESET}")
        print("\n" + "="*84 + "\n")

    def scenario_pipeline_derivative(self):
        print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}>>> SCENARIO 2: Sibling Pipeline Aggregation (Derivative){TermColor.RESET}")
        print(f"{TermColor.DIM}Calculating 1st order derivative of mean latency to pinpoint degradation acceleration.{TermColor.RESET}\n")
        dsl = {
            "size": 0,
            "aggs": {
                "time_buckets": {
                    "date_histogram": {"field": "@timestamp", "fixed_interval": "4h"},
                    "aggs": {
                        "mean_latency": {"avg": {"field": "response_time_ms"}},
                        "latency_rate_of_change": {
                            "derivative": {"buckets_path": "mean_latency"}
                        }
                    }
                }
            }
        }
        res = self.cluster.execute_dsl_aggregation(dsl)
        buckets = res["aggregations"]["time_buckets"]["buckets"]

        print(f"{'TIMESTAMP BUCKET':<22} | {'DOCS':<6} | {'AVG LATENCY':<12} | {'DERIVATIVE (Δ/bucket)':<20} | {'ANOMALY ALERT'}")
        print("-" * 80)
        for b in buckets:
            ts = b["key_as_string"]
            cnt = b["doc_count"]
            avg_l = b["mean_latency"]["value"]
            deriv = b["latency_rate_of_change"]["value"]

            if deriv is None:
                deriv_str = "N/A (base bucket)"
                alert = f"{TermColor.DIM}BASELINE{TermColor.RESET}"
            else:
                sign = "+" if deriv > 0 else ""
                deriv_str = f"{sign}{deriv:.2f} ms"
                if deriv > 15.0:
                    alert = f"{TermColor.RED}{TermColor.BOLD}CRITICAL SPIKE{TermColor.RESET}"
                elif deriv < -10.0:
                    alert = f"{TermColor.GREEN}COOLING DOWN{TermColor.RESET}"
                else:
                    alert = f"{TermColor.WHITE}NOMINAL{TermColor.RESET}"

            print(f"{ts:<22} | {cnt:<6} | {avg_l:<12.2f} | {deriv_str:<20} | {alert}")
        print("\n" + "="*80 + "\n")

    def scenario_cumulative_sum(self):
        print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}>>> SCENARIO 3: Pipeline Aggregation (Cumulative Sum / Financial GMV){TermColor.RESET}")
        dsl = {
            "size": 0,
            "query": {"bool": {"filter": [{"term": {"service": "payment-gateway"}}]}},
            "aggs": {
                "interval_window": {
                    "date_histogram": {"field": "@timestamp", "fixed_interval": "4h"},
                    "aggs": {
                        "batch_gmv": {"sum": {"field": "transaction_amount"}},
                        "cumulative_gmv": {
                            "cumulative_sum": {"buckets_path": "batch_gmv"}
                        }
                    }
                }
            }
        }
        res = self.cluster.execute_dsl_aggregation(dsl)
        buckets = res["aggregations"]["interval_window"]["buckets"]

        print(f"{'WINDOW':<22} | {'TX COUNT':<10} | {'INTERVAL GMV ($)':<18} | {'RUNNING TOTAL GMV ($)':<22}")
        print("-" * 78)
        for b in buckets:
            ts = b["key_as_string"]
            cnt = b["doc_count"]
            gmv = b["batch_gmv"]["value"]
            cum = b["cumulative_gmv"]["value"]
            print(f"{ts:<22} | {cnt:<10} | ${gmv:<17.2f} | {TermColor.GREEN}${cum:<21.2f}{TermColor.RESET}")
        print("\n" + "="*78 + "\n")

    def scenario_p99_anomaly_detector(self):
        print(f"\n{TermColor.BOLD}{TermColor.MAGENTA}>>> SCENARIO 4: High-Percentile Outlier Slicing (P99 > 300ms){TermColor.RESET}")
        dsl = {
            "size": 0,
            "aggs": {
                "by_region": {
                    "terms": {"field": "region"},
                    "aggs": {
                        "lat_p": {"percentiles": {"field": "response_time_ms"}}
                    }
                }
            }
        }
        res = self.cluster.execute_dsl_aggregation(dsl)
        for b in res["aggregations"]["by_region"]["buckets"]:
            region = b["key"]
            p99 = b["lat_p"]["values"]["99.0"]
            is_breached = p99 > 300.0

            badge = f"{TermColor.RED}[SLA VIOLATION]{TermColor.RESET}" if is_breached else f"{TermColor.GREEN}[HEALTHY]{TermColor.RESET}"
            print(f"Region: {TermColor.CYAN}{region:<15}{TermColor.RESET} P99: {p99:>7.2f} ms  {badge}")
            # Render ASCII mini-gauge
            bar_len = min(40, int(p99 / 15))
            bar = "#" * bar_len
            color = TermColor.RED if is_breached else TermColor.GREEN
            print(f"Latency Gauge: {color}[{bar:<40}]{TermColor.RESET}\n")

    def scenario_inspect_dsl(self):
        print(f"\n{TermColor.BOLD}{TermColor.YELLOW}>>> Production Elasticsearch DSL Template: Complex Aggregation Query{TermColor.RESET}")
        dsl_sample = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"range": {"@timestamp": {"gte": "now-24h", "lte": "now"}}},
                        {"term": {"status_code": 500}}
                    ]
                }
            },
            "aggs": {
                "services": {
                    "terms": {
                        "field": "service.keyword",
                        "size": 10,
                        "order": {"error_density": "desc"}
                    },
                    "aggs": {
                        "error_density": {"avg": {"field": "response_time_ms"}},
                        "p99_latency": {
                            "percentiles": {
                                "field": "response_time_ms",
                                "percents": [50.0, 95.0, 99.0]
                            }
                        },
                        "sla_bucket_filter": {
                            "bucket_selector": {
                                "buckets_path": {"target_p99": "p99_latency.99"},
                                "script": "params.target_p99 > 500.0"
                            }
                        }
                    }
                }
            }
        }
        formatted_json = json.dumps(dsl_sample, indent=2)
        print(f"{TermColor.CYAN}{formatted_json}{TermColor.RESET}\n")

if __name__ == "__main__":
    app = AggregationLabCLI()
    # Check if run in automated or non-interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print_banner()
        print(f"{TermColor.YELLOW}[AUTO-RUN]{TermColor.RESET} Running end-to-end verification tests...")
        app.scenario_multi_tier_terms()
        app.scenario_pipeline_derivative()
        app.scenario_cumulative_sum()
        app.scenario_p99_anomaly_detector()
        print(f"{TermColor.GREEN}[PASSED]{TermColor.RESET} All aggregation modules verified successfully!")
    else:
        try:
            app.run_menu()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{TermColor.YELLOW}Session aborted by user. Exiting...{TermColor.RESET}")
            sys.exit(0)
