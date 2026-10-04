#!/usr/bin/env python3
"""
Lab Hands-on: Data Wrangling & Manipulation dengan Modern Tidyverse (R-Programming Engine Simulation)
Modul: Deep Dive Verbs (dplyr) & Reshaping (tidyr)
Deskripsi:
  Mengimplementasikan pipeline engine berarsitektur fungsional yang mereplikasi
  perilaku 'tibble', pipe operator ('|>' / '%>%'), grouped mutations, selective summaries,
  serta pivoting (tidyr::pivot_longer) dengan pure Python 3 Standard Library.
"""

from collections import defaultdict
from copy import deepcopy
import sys
from typing import Callable, Any, List, Dict, Tuple


# ==============================================================================
# Terminal Color Palette (ANSI)
# ==============================================================================
class TermColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    RED = "\033[91m"
    GRAY = "\033[90m"


def format_type(val: Any) -> str:
    """Mendeteksi representasi tipe ala R S3 vector: <int>, <dbl>, <chr>, <lgl>."""
    if isinstance(val, bool):
        return "<lgl>"
    elif isinstance(val, int):
        return "<int>"
    elif isinstance(val, float):
        return "<dbl>"
    elif isinstance(val, str):
        return "<chr>"
    return "<obj>"


# ==============================================================================
# Core Engine: Tibble & Grouped Data Structures
# ==============================================================================
class Tibble:
    """
    Representasi struktur data modern dataframe R (Tidyverse 'tibble').
    Mengedepankan immutable transitions dan column-type awareness.
    """

    def __init__(self, data: List[Dict[str, Any]]):
        self._data: List[Dict[str, Any]] = [dict(row) for row in data]

    def __len__(self) -> int:
        return len(self._data)

    @property
    def colnames(self) -> List[str]:
        return list(self._data[0].keys()) if self._data else []

    def clone(self) -> "Tibble":
        return Tibble(deepcopy(self._data))

    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> "Tibble":
        """Implementasi dplyr::filter() - Menyaring baris berdasarkan ekspresi logis."""
        filtered = [row for row in self._data if predicate(row)]
        return Tibble(filtered)

    def select(self, *cols: str) -> "Tibble":
        """Implementasi dplyr::select() - Mengisolasi kolom tertentu."""
        projected = [{c: row[c] for c in cols if c in row} for row in self._data]
        return Tibble(projected)

    def mutate(self, **kwargs: Callable[[Dict[str, Any]], Any]) -> "Tibble":
        """
        Implementasi dplyr::mutate() - Menambahkan kolom baru atau mentransformasikan
        kolom yang ada menggunakan ekspresi fungsional per-observasi.
        """
        new_data = []
        for row in self._data:
            row_copy = dict(row)
            for col_name, func in kwargs.items():
                row_copy[col_name] = func(row_copy)
            new_data.append(row_copy)
        return Tibble(new_data)

    def arrange(self, col: str, descending: bool = False) -> "Tibble":
        """Implementasi dplyr::arrange() - Mengurutkan baris dataset."""
        sorted_data = sorted(
            self._data, key=lambda row: row.get(col), reverse=descending
        )
        return Tibble(sorted_data)

    def group_by(self, *group_cols: str) -> "GroupedTibble":
        """Implementasi dplyr::group_by() - Memecah dataset ke dalam indeks grup agregasi."""
        return GroupedTibble(self, list(group_cols))

    def pivot_longer(
        self, cols: List[str], names_to: str = "name", values_to: str = "value"
    ) -> "Tibble":
        """
        Implementasi tidyr::pivot_longer() - Mengubah dataset wide menjadi tidy long format.
        """
        long_data = []
        id_cols = [c for c in self.colnames if c not in cols]

        for row in self._data:
            for c in cols:
                if c in row:
                    new_row = {id_c: row[id_c] for id_c in id_cols}
                    new_row[names_to] = c
                    new_row[values_to] = row[c]
                    long_data.append(new_row)
        return Tibble(long_data)

    def print_tibble(self, title: str = "Tibble", max_rows: int = 6) -> None:
        """Visualisasi formatted tibble ala R interactive console."""
        cols = self.colnames
        n_rows = len(self._data)
        n_cols = len(cols)

        print(
            f"\n{TermColor.BOLD}{TermColor.CYAN}# A tibble: {n_rows} × {n_cols}{TermColor.RESET} "
            f"{TermColor.GRAY}[{title}]{TermColor.RESET}"
        )

        if n_rows == 0:
            print(f"{TermColor.DIM}# (empty tibble){TermColor.RESET}")
            return

        # Ambil tipe data dari baris pertama
        col_types = {c: format_type(self._data[0].get(c)) for c in cols}

        # Hitung padding lebar kolom
        widths = {}
        for c in cols:
            max_val_len = max(
                (len(str(r[c])) for r in self._data[:max_rows] if c in r), default=0
            )
            widths[c] = max(len(c), len(col_types[c]), max_val_len)

        # Header baris 1: Nama Kolom
        header_names = " ".join(
            f"{TermColor.BOLD}{c:<{widths[c]}}{TermColor.RESET}" for c in cols
        )
        # Header baris 2: Tipe Kolom
        header_types = " ".join(
            f"{TermColor.YELLOW}{col_types[c]:<{widths[c]}}{TermColor.RESET}"
            for c in cols
        )

        print(f" {header_names}")
        print(f" {header_types}")
        print(f" {TermColor.GRAY}{'-' * (sum(widths.values()) + len(cols) - 1)}{TermColor.RESET}")

        for i, row in enumerate(self._data[:max_rows]):
            row_str = " ".join(
                f"{str(row.get(c, 'NA')):<{widths[c]}}" for c in cols
            )
            print(f" {row_str}")

        if n_rows > max_rows:
            print(
                f"{TermColor.DIM}# ℹ with {n_rows - max_rows} more rows...{TermColor.RESET}"
            )


class GroupedTibble:
    """Representasi dataset yang terbagi ke dalam partisi grup diskrit."""

    def __init__(self, parent: Tibble, group_cols: List[str]):
        self.parent = parent
        self.group_cols = group_cols

    def summarise(self, **kwargs: Callable[[List[Dict[str, Any]]], Any]) -> Tibble:
        """
        Implementasi dplyr::summarise() / summarize()
        Mereduksi setiap grup menjadi 1 baris agregat terhitung.
        """
        groups: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
        for row in self.parent._data:
            key = tuple(row[gc] for gc in self.group_cols)
            groups[key].append(row)

        summary_rows = []
        for key, row_bucket in groups.items():
            out_row = {
                self.group_cols[idx]: key[idx]
                for idx in range(len(self.group_cols))
            }
            for sum_col_name, aggregate_fn in kwargs.items():
                out_row[sum_col_name] = aggregate_fn(row_bucket)
            summary_rows.append(out_row)

        return Tibble(summary_rows)


# ==============================================================================
# Lab Scenario: Production Telemetry & SLA Cost Wrangling
# ==============================================================================
def run_lab():
    print(f"{TermColor.BOLD}{TermColor.MAGENTA}" + "=" * 70)
    print("   LAB: TIDYVERSE WORKFLOW SIMULATOR (DPLYR & TIDYR)")
    print("=" * 70 + f"{TermColor.RESET}")

    # Dataset: Log server fleet multi-region
    raw_telemetry = [
        {"cluster": "alpha-1", "region": "ap-southeast-1", "nodes": 8,  "hourly_rate": 0.45, "q1_up": 99.98, "q2_up": 99.90, "errors": 12},
        {"cluster": "alpha-2", "region": "ap-southeast-1", "nodes": 16, "hourly_rate": 0.45, "q1_up": 99.95, "q2_up": 99.92, "errors": 45},
        {"cluster": "beta-1",  "region": "us-east-1",      "nodes": 32, "hourly_rate": 0.38, "q1_up": 99.90, "q2_up": 99.85, "errors": 110},
        {"cluster": "beta-2",  "region": "us-east-1",      "nodes": 64, "hourly_rate": 0.38, "q1_up": 99.99, "q2_up": 99.95, "errors": 8},
        {"cluster": "gamma-1", "region": "eu-central-1",   "nodes": 4,  "hourly_rate": 0.52, "q1_up": 99.80, "q2_up": 99.70, "errors": 230},
        {"cluster": "gamma-2", "region": "eu-central-1",   "nodes": 12, "hourly_rate": 0.52, "q1_up": 99.99, "q2_up": 99.98, "errors": 3},
        {"cluster": "delta-1", "region": "us-west-2",      "nodes": 24, "hourly_rate": 0.40, "q1_up": 99.92, "q2_up": 99.88, "errors": 78},
    ]

    telemetry_tbl = Tibble(raw_telemetry)
    telemetry_tbl.print_tibble(title="Raw Infrastructure Telemetry")

    # Pipeline Step 1: Mutate (Derived Metrics)
    print(f"\n{TermColor.GREEN}[Step 1] Memanggil dplyr::mutate() & dplyr::filter(){TermColor.RESET}")
    print(f"{TermColor.GRAY}  |> Menghitung total burn-rate harian (nodes * hourly_rate * 24)")
    print(f"  |> Menyaring kluster dengan insiden/error > 10{TermColor.RESET}")

    transformed_tbl = (
        telemetry_tbl.mutate(
            daily_cost=lambda r: round(r["nodes"] * r["hourly_rate"] * 24.0, 2),
            sla_risk=lambda r: "HIGH" if r["errors"] > 50 else "STABLE"
        )
        .filter(lambda r: r["errors"] > 10)
    )
    transformed_tbl.print_tibble(title="Mutated & Filtered Telemetry")

    # Pipeline Step 2: Group By & Summarise
    print(f"\n{TermColor.GREEN}[Step 2] Agregasi Relasional: group_by() |> summarise(){TermColor.RESET}")
    print(f"{TermColor.GRAY}  |> Mengelompokkan berdasarkan 'region'")
    print(f"  |> Menghitung total_nodes, mean_daily_cost, total_errors{TermColor.RESET}")

    summary_tbl = (
        transformed_tbl.group_by("region")
        .summarise(
            cluster_count=lambda bucket: len(bucket),
            total_nodes=lambda bucket: sum(r["nodes"] for r in bucket),
            mean_daily_cost=lambda bucket: round(sum(r["daily_cost"] for r in bucket) / len(bucket), 2),
            total_errors=lambda bucket: sum(r["errors"] for r in bucket)
        )
        .arrange("total_errors", descending=True)
    )
    summary_tbl.print_tibble(title="Regional SLA Breakdown")

    # Pipeline Step 3: Reshaping Tidyverse (tidyr::pivot_longer)
    print(f"\n{TermColor.GREEN}[Step 3] Reshaping Data: tidyr::pivot_longer(){TermColor.RESET}")
    print(f"{TermColor.GRAY}  |> Mengubah format uptime wide ['q1_up', 'q2_up'] menjadi tidy long rows{TermColor.RESET}")

    tidy_long_tbl = (
        telemetry_tbl.select("cluster", "region", "q1_up", "q2_up")
        .pivot_longer(
            cols=["q1_up", "q2_up"],
            names_to="quarter",
            values_to="uptime_pct"
        )
        .arrange("cluster")
    )
    tidy_long_tbl.print_tibble(title="Tidy Long Format Uptime", max_rows=10)

    # Verifikasi Integritas Pipeline
    print(f"\n{TermColor.BOLD}{TermColor.CYAN}--- PENGUJIAN INVARIAN AKHIR ---{TermColor.RESET}")
    assert len(summary_tbl) > 0, "Summary tibble tidak boleh kosong."
    assert len(tidy_long_tbl) == len(telemetry_tbl) * 2, "Pivot longer harus menggandakan observasi kuartal."
    print(f"Status: {TermColor.GREEN}SEMUA VERB TIDYVERSE TERVERIFIKASI SEMPURNA.{TermColor.RESET}\n")


if __name__ == "__main__":
    run_lab()