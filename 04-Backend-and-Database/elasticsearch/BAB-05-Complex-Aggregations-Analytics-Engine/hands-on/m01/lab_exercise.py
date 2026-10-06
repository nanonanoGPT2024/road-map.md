#!/usr/bin/env python3
"""
Lab Exercise M01: Elasticsearch Complex Aggregations & Analytics Engine Simulation
BAB-05: Complex Aggregations & Analytics Engine

Simulasi mandiri agregasi Elasticsearch:
1. Bucket Aggregations (Terms, Date Histogram, Range)
2. Metric Aggregations (Stats, Extended Stats, Percentiles, Cardinality)
3. Pipeline Aggregations (Derivative, Cumulative Sum, Bucket Script)
"""

import sys
import math
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

# ANSI Colors for Terminal Output
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

# Sample In-Memory Index (E-Commerce Transactions)
MOCK_INDEX: List[Dict[str, Any]] = [
    {"id": "tx101", "timestamp": "2026-10-01T08:15:00", "category": "electronics", "price": 450.0, "quantity": 1, "fee": 15.0, "user_id": "usr_A", "status": "COMPLETED"},
    {"id": "tx102", "timestamp": "2026-10-01T09:30:00", "category": "books",       "price": 35.0,  "quantity": 2, "fee": 2.5,  "user_id": "usr_B", "status": "COMPLETED"},
    {"id": "tx103", "timestamp": "2026-10-01T14:45:00", "category": "electronics", "price": 1200.0,"quantity": 1, "fee": 40.0, "user_id": "usr_C", "status": "COMPLETED"},
    {"id": "tx104", "timestamp": "2026-10-02T10:00:00", "category": "clothing",    "price": 85.0,  "quantity": 3, "fee": 5.0,  "user_id": "usr_A", "status": "COMPLETED"},
    {"id": "tx105", "timestamp": "2026-10-02T11:15:00", "category": "electronics", "price": 300.0, "quantity": 2, "fee": 12.0, "user_id": "usr_D", "status": "CANCELLED"},
    {"id": "tx106", "timestamp": "2026-10-02T16:20:00", "category": "books",       "price": 120.0, "quantity": 4, "fee": 6.0,  "user_id": "usr_B", "status": "COMPLETED"},
    {"id": "tx107", "timestamp": "2026-10-03T09:10:00", "category": "electronics", "price": 950.0, "quantity": 1, "fee": 30.0, "user_id": "usr_E", "status": "COMPLETED"},
    {"id": "tx108", "timestamp": "2026-10-03T13:40:00", "category": "clothing",    "price": 210.0, "quantity": 2, "fee": 10.0, "user_id": "usr_F", "status": "COMPLETED"},
    {"id": "tx109", "timestamp": "2026-10-03T18:05:00", "category": "books",       "price": 45.0,  "quantity": 1, "fee": 3.0,  "user_id": "usr_A", "status": "COMPLETED"},
    {"id": "tx110", "timestamp": "2026-10-04T10:30:00", "category": "electronics", "price": 150.0, "quantity": 2, "fee": 8.0,  "user_id": "usr_C", "status": "COMPLETED"},
    {"id": "tx111", "timestamp": "2026-10-04T15:00:00", "category": "clothing",    "price": 340.0, "quantity": 1, "fee": 14.0, "user_id": "usr_G", "status": "COMPLETED"},
    {"id": "tx112", "timestamp": "2026-10-04T19:25:00", "category": "books",       "price": 60.0,  "quantity": 2, "fee": 4.0,  "user_id": "usr_B", "status": "COMPLETED"}
]

class AggregationEngine:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data

    def calculate_percentiles(self, values: List[float], percents: List[float]) -> Dict[str, float]:
        """Menghitung aproksimasi persentil (mirip algoritma T-Digest di Elasticsearch)."""
        if not values:
            return {f"{p}": 0.0 for p in percents}
        sorted_vals = sorted(values)
        results = {}
        for p in percents:
            rank = (p / 100.0) * (len(sorted_vals) - 1)
            lower = int(math.floor(rank))
            upper = int(math.ceil(rank))
            weight = rank - lower
            val = sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight
            results[f"{p}"] = round(val, 2)
        return results

    def run_terms_with_sub_aggs(self) -> Dict[str, Any]:
        """
        Simulasi: Terms Aggregation pada 'category'
        Sub-aggs:
          - stats: agregasi nilai 'price' (min, max, avg, sum, count)
          - unique_users: cardinality pada 'user_id'
          - percentiles: p50, p90, p99 pada 'price'
        """
        buckets_map: Dict[str, List[Dict[str, Any]]] = {}
        for doc in self.data:
            cat = doc["category"]
            buckets_map.setdefault(cat, []).append(doc)

        result_buckets = []
        for cat, docs in sorted(buckets_map.items(), key=lambda item: len(item[1]), reverse=True):
            prices = [d["price"] for d in docs]
            users = set(d["user_id"] for d in docs)
            stats = {
                "count": len(prices),
                "min": min(prices),
                "max": max(prices),
                "avg": round(sum(prices) / len(prices), 2),
                "sum": round(sum(prices), 2)
            }
            percentiles = self.calculate_percentiles(prices, [50.0, 90.0, 99.0])

            result_buckets.append({
                "key": cat,
                "doc_count": len(docs),
                "price_stats": stats,
                "unique_buyers": {"value": len(users)},
                "price_percentiles": {"values": percentiles}
            })

        return {"by_category": {"doc_count_error_upper_bound": 0, "buckets": result_buckets}}

    def run_date_histogram_with_pipeline(self) -> Dict[str, Any]:
        """
        Simulasi: Date Histogram (interval: 1d) pada 'timestamp'
        Sub-agg:
          - total_revenue: sum('price')
        Pipeline Aggregations:
          - revenue_derivative: menghitung selisih revenue vs hari sebelumnya (Derivative)
          - cumulative_revenue: akumulasi pendapatan harian (Cumulative Sum)
        """
        daily_map: Dict[str, List[Dict[str, Any]]] = {}
        for doc in self.data:
            dt = datetime.fromisoformat(doc["timestamp"])
            day_key = dt.strftime("%Y-%m-%d")
            daily_map.setdefault(day_key, []).append(doc)

        sorted_days = sorted(daily_map.keys())
        buckets = []
        cum_sum = 0.0
        prev_revenue = None

        for day in sorted_days:
            docs = daily_map[day]
            rev = sum(d["price"] for d in docs)
            cum_sum += rev

            bucket = {
                "key_as_string": f"{day}T00:00:00.000Z",
                "doc_count": len(docs),
                "total_revenue": {"value": round(rev, 2)},
                "cumulative_revenue": {"value": round(cum_sum, 2)}
            }

            if prev_revenue is not None:
                diff = rev - prev_revenue
                bucket["revenue_derivative"] = {"value": round(diff, 2)}
            else:
                bucket["revenue_derivative"] = {"value": None, "note": "null_first_bucket"}

            prev_revenue = rev
            buckets.append(bucket)

        return {"sales_over_time": {"buckets": buckets}}

    def run_bucket_script_margin(self) -> Dict[str, Any]:
        """
        Simulasi Pipeline: Bucket Script Aggregation
        Formula: ((revenue - fee) / revenue) * 100 -> profit_margin_percent
        """
        cat_buckets = {}
        for doc in self.data:
            cat = doc["category"]
            cat_buckets.setdefault(cat, []).append(doc)

        results = []
        for cat, docs in cat_buckets.items():
            tot_revenue = sum(d["price"] for d in docs)
            tot_fee = sum(d["fee"] for d in docs)
            net_profit = tot_revenue - tot_fee
            margin_pct = (net_profit / tot_revenue * 100.0) if tot_revenue > 0 else 0.0

            results.append({
                "key": cat,
                "doc_count": len(docs),
                "gross_revenue": round(tot_revenue, 2),
                "total_fees": round(tot_fee, 2),
                "profit_margin_pct": round(margin_pct, 2)
            })

        return {"category_margin_analysis": {"buckets": sorted(results, key=lambda x: x["profit_margin_pct"], reverse=True)}}

def print_header(title: str):
    print(f"\n{Color.CYAN}{'='*70}{Color.RESET}")
    print(f"{Color.BOLD}{Color.YELLOW} ⚡ {title.upper()} ⚡ {Color.RESET}")
    print(f"{Color.CYAN}{'='*70}{Color.RESET}")

def render_terms_demo(engine: AggregationEngine):
    print_header("1. Multi-Bucket Aggregation + Metric Sub-Aggs (Terms + Stats + Percentiles)")
    res = engine.run_terms_with_sub_aggs()
    buckets = res["by_category"]["buckets"]

    print(f"{Color.GRAY}Executing query: 'category' terms -> sub_aggs: [stats(price), cardinality(user_id), percentiles(price)]{Color.RESET}\n")
    for b in buckets:
        print(f"{Color.GREEN}► Category: {Color.BOLD}{b['key'].upper()}{Color.RESET} (Docs: {b['doc_count']})")
        st = b["price_stats"]
        print(f"   ├─ {Color.BLUE}Stats{Color.RESET}        : Min=${st['min']} | Max=${st['max']} | Avg=${st['avg']} | Sum=${st['sum']}")
        print(f"   ├─ {Color.MAGENTA}Unique Buyers{Color.RESET}: {b['unique_buyers']['value']} active distinct users")
        pct = b["price_percentiles"]["values"]
        print(f"   └─ {Color.YELLOW}Percentiles{Color.RESET}  : P50=${pct['50.0']} | P90=${pct['90.0']} | P99=${pct['99.0']}")
        print()

def render_histogram_demo(engine: AggregationEngine):
    print_header("2. Date Histogram + Pipeline Aggregations (Derivative & Cumulative Sum)")
    res = engine.run_date_histogram_with_pipeline()
    buckets = res["sales_over_time"]["buckets"]

    print(f"{Color.GRAY}Interval: 1d (Daily) -> Pipeline: Derivative & Cumulative Sum{Color.RESET}\n")
    print(f"{'Date':<15} {'Docs':<8} {'Revenue':<14} {'Cumulative':<16} {'Derivative (Δ)':<15}")
    print(f"{'-'*70}")
    for b in buckets:
        dt_str = b["key_as_string"].split("T")[0]
        rev = f"${b['total_revenue']['value']:,.2f}"
        cum = f"${b['cumulative_revenue']['value']:,.2f}"
        deriv_val = b["revenue_derivative"]["value"]
        if deriv_val is None:
            deriv = f"{Color.GRAY}N/A (Base){Color.RESET}"
        elif deriv_val >= 0:
            deriv = f"{Color.GREEN}+${deriv_val:,.2f} ▲{Color.RESET}"
        else:
            deriv = f"{Color.RED}-${abs(deriv_val):,.2f} ▼{Color.RESET}"

        print(f"{Color.WHITE}{dt_str:<15}{Color.RESET} {b['doc_count']:<8} {Color.CYAN}{rev:<14}{Color.RESET} {Color.MAGENTA}{cum:<16}{Color.RESET} {deriv:<15}")

def render_bucket_script_demo(engine: AggregationEngine):
    print_header("3. Pipeline Bucket Script (Custom Formula: Net Margin %)")
    res = engine.run_bucket_script_margin()
    buckets = res["category_margin_analysis"]["buckets"]

    print(f"{Color.GRAY}Formula: params.margin = ((params.revenue - params.fee) / params.revenue) * 100{Color.RESET}\n")
    for b in buckets:
        margin = b["profit_margin_pct"]
        bar_len = int(margin / 2.5)
        bar = f"{Color.GREEN}{'█' * bar_len}{Color.RESET}"
        print(f"{Color.BOLD}{b['key']:<15}{Color.RESET} Gross: ${b['gross_revenue']:<8} Fee: ${b['total_fees']:<6} | Margin: {Color.YELLOW}{margin:>6.2f}%{Color.RESET} {bar}")

def print_dsl_spec():
    print_header("Elasticsearch Query DSL Architecture Equivalent")
    dsl_sample = {
        "size": 0,
        "aggs": {
            "sales_per_day": {
                "date_histogram": {"field": "timestamp", "calendar_interval": "day"},
                "aggs": {
                    "daily_rev": {"sum": {"field": "price"}},
                    "rev_diff": {
                        "derivative": {"buckets_path": "daily_rev"}
                    },
                    "cumulative_rev": {
                        "cumulative_sum": {"buckets_path": "daily_rev"}
                    }
                }
            }
        }
    }
    print(f"{Color.CYAN}{json.dumps(dsl_sample, indent=2)}{Color.RESET}")

def interactive_menu(engine: AggregationEngine):
    while True:
        print(f"\n{Color.BOLD}{Color.WHITE}=== ELASTICSEARCH COMPLEX AGGREGATIONS LAB (BAB-05) ==={Color.RESET}")
        print(f"{Color.CYAN}1.{Color.RESET} Multi-Bucket & Metric Aggregations (Terms, Stats, Percentiles)")
        print(f"{Color.CYAN}2.{Color.RESET} Date Histogram & Pipeline Aggs (Derivative, Cumulative Sum)")
        print(f"{Color.CYAN}3.{Color.RESET} Bucket Script Aggregations (Profit Margin Calculation)")
        print(f"{Color.CYAN}4.{Color.RESET} Show Equivalent ES Query DSL")
        print(f"{Color.CYAN}5.{Color.RESET} Run All Analytics Suite")
        print(f"{Color.RED}6.{Color.RESET} Exit Lab")
        print(f"{Color.GRAY}{'-'*55}{Color.RESET}")

        if not sys.stdin.isatty():
            print(f"{Color.YELLOW}Non-interactive terminal detected. Running full analytics suite directly...{Color.RESET}")
            render_terms_demo(engine)
            render_histogram_demo(engine)
            render_bucket_script_demo(engine)
            print_dsl_spec()
            break

        choice = input(f"{Color.BOLD}Select simulation [1-6]: {Color.RESET}").strip()
        if choice == "1":
            render_terms_demo(engine)
        elif choice == "2":
            render_histogram_demo(engine)
        elif choice == "3":
            render_bucket_script_demo(engine)
        elif choice == "4":
            print_dsl_spec()
        elif choice == "5":
            render_terms_demo(engine)
            render_histogram_demo(engine)
            render_bucket_script_demo(engine)
            print_dsl_spec()
        elif choice == "6" or choice.lower() in ("q", "exit"):
            print(f"\n{Color.GREEN}✓ Lab session ended successfully.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Invalid selection. Please choose 1-6.{Color.RESET}")

def main():
    engine = AggregationEngine(MOCK_INDEX)
    interactive_menu(engine)

if __name__ == "__main__":
    main()
