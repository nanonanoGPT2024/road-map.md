#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Pipeline Modern Tidyverse (dplyr & tidyr) di R
BAB-03: Data Wrangling & Manipulation dengan Modern Tidyverse

Skrip ini mensimulasikan semantik grammar data manipulation Tidyverse di R:
- Tibble representation & printing
- Pipe operator (|>/%>%) chaining
- Verbs inti: select(), filter(), mutate(), arrange(), group_by(), summarize()
- Reshaping: pivot_longer()
"""

import sys
import copy
from typing import List, Dict, Any, Callable


class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    BG_BLUE = "\033[44m"


class Tibble:
    """Simulasi R Tibble (data frame modern dengan pretty printing)"""

    def __init__(self, data: List[Dict[str, Any]], groups: List[str] = None):
        self.data = copy.deepcopy(data)
        self.groups = groups or []

    @property
    def colnames(self) -> List[str]:
        if not self.data:
            return []
        return list(self.data[0].keys())

    def __repr__(self) -> str:
        if not self.data:
            return f"{ANSI.DIM}# A tibble: 0 × 0{ANSI.RESET}"

        nrow = len(self.data)
        ncol = len(self.colnames)
        out = [f"{ANSI.BOLD}{ANSI.CYAN}# A tibble: {nrow} × {ncol}{ANSI.RESET}"]

        if self.groups:
            grp_str = ", ".join(self.groups)
            out.append(f"{ANSI.MAGENTA}# Groups:   {grp_str}{ANSI.RESET}")

        headers = self.colnames
        col_widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in self.data)) for c in headers}

        header_line = "  " + "  ".join(f"{ANSI.BOLD}{c:<{col_widths[c]}}{ANSI.RESET}" for c in headers)
        types_line = "  " + "  ".join(
            f"{ANSI.DIM}<{self._infer_type(self.data[0].get(c)):<{col_widths[c]-2}}>{ANSI.RESET}"
            for c in headers
        )
        out.append(header_line)
        out.append(types_line)

        # Print max 8 rows
        for row in self.data[:8]:
            row_str = "  " + "  ".join(f"{str(row.get(c, '')):<{col_widths[c]}}" for c in headers)
            out.append(row_str)

        if nrow > 8:
            out.append(f"{ANSI.DIM}# ... with {nrow - 8} more rows{ANSI.RESET}")

        return "\n".join(out)

    def _infer_type(self, val: Any) -> str:
        if isinstance(val, int):
            return "int"
        elif isinstance(val, float):
            return "dbl"
        elif isinstance(val, bool):
            return "lgl"
        return "chr"

    # Pipe chaining operator `>>` as simulation of `|>` or `%>%`
    def __rshift__(self, func_call):
        return func_call(self)


# ==========================================
# Implementasi dplyr Verbs
# ==========================================

def select(*cols: str):
    """dplyr::select() - Memilih atau membuang kolom spesifik"""
    def _apply(tbl: Tibble) -> Tibble:
        new_data = []
        for row in tbl.data:
            new_row = {k: row[k] for k in cols if k in row}
            new_data.append(new_row)
        return Tibble(new_data, tbl.groups)
    return _apply


def filter_rows(predicate: Callable[[Dict[str, Any]], bool]):
    """dplyr::filter() - Menyaring baris berdasarkan kondisi logis"""
    def _apply(tbl: Tibble) -> Tibble:
        new_data = [row for row in tbl.data if predicate(row)]
        return Tibble(new_data, tbl.groups)
    return _apply


def mutate(**expressions: Callable[[Dict[str, Any]], Any]):
    """dplyr::mutate() - Menambahkan kolom baru atau modifikasi kolom ada"""
    def _apply(tbl: Tibble) -> Tibble:
        new_data = []
        for row in tbl.data:
            r_copy = dict(row)
            for col_name, expr in expressions.items():
                r_copy[col_name] = expr(r_copy)
            new_data.append(r_copy)
        return Tibble(new_data, tbl.groups)
    return _apply


def arrange(col: str, descending: bool = False):
    """dplyr::arrange() - Mengurutkan baris data"""
    def _apply(tbl: Tibble) -> Tibble:
        sorted_data = sorted(tbl.data, key=lambda x: x.get(col, 0), reverse=descending)
        return Tibble(sorted_data, tbl.groups)
    return _apply


def group_by(*cols: str):
    """dplyr::group_by() - Menentukan metadata grouping untuk agregasi"""
    def _apply(tbl: Tibble) -> Tibble:
        return Tibble(tbl.data, list(cols))
    return _apply


def summarize(**aggs: Callable[[List[Dict[str, Any]]], Any]):
    """dplyr::summarize() - Agregasi data (grouped / ungrouped)"""
    def _apply(tbl: Tibble) -> Tibble:
        if not tbl.groups:
            summary_row = {}
            for k, fn in aggs.items():
                summary_row[k] = fn(tbl.data)
            return Tibble([summary_row], [])

        # Group data
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for row in tbl.data:
            key = tuple(row[g] for g in tbl.groups)
            grouped.setdefault(key, []).append(row)

        results = []
        for key, rows in grouped.items():
            res_row = {g: val for g, val in zip(tbl.groups, key)}
            for k, fn in aggs.items():
                res_row[k] = fn(rows)
            results.append(res_row)

        # Drop last grouping level (standard dplyr behaviour)
        new_groups = tbl.groups[:-1]
        return Tibble(results, new_groups)
    return _apply


def pivot_longer(cols: List[str], names_to: str, values_to: str):
    """tidyr::pivot_longer() - Mengubah data wide format menjadi long format"""
    def _apply(tbl: Tibble) -> Tibble:
        new_data = []
        for row in tbl.data:
            base_row = {k: v for k, v in row.items() if k not in cols}
            for c in cols:
                entry = dict(base_row)
                entry[names_to] = c
                entry[values_to] = row.get(c)
                new_data.append(entry)
        return Tibble(new_data, tbl.groups)
    return _apply


# ==========================================
# Data Sample (Simulasi Dataset Starwars/E-Commerce)
# ==========================================

raw_ecommerce_data = [
    {"trans_id": 101, "customer": "Siti", "region": "Jakarta", "category": "Elektronik", "q1_sales": 250, "q2_sales": 310, "discount": 0.10},
    {"trans_id": 102, "customer": "Budi", "region": "Bandung", "category": "Pakaian",    "q1_sales": 80,  "q2_sales": 95,  "discount": 0.05},
    {"trans_id": 103, "customer": "Andi", "region": "Jakarta", "category": "Elektronik", "q1_sales": 400, "q2_sales": 450, "discount": 0.15},
    {"trans_id": 104, "customer": "Dewi", "region": "Surabaya","category": "Makanan",    "q1_sales": 45,  "q2_sales": 50,  "discount": 0.00},
    {"trans_id": 105, "customer": "Reza", "region": "Bandung", "category": "Elektronik", "q1_sales": 180, "q2_sales": 210, "discount": 0.10},
    {"trans_id": 106, "customer": "Rina", "region": "Jakarta", "category": "Pakaian",    "q1_sales": 120, "q2_sales": 130, "discount": 0.05},
    {"trans_id": 107, "customer": "Fajar","region": "Surabaya","category": "Elektronik", "q1_sales": 520, "q2_sales": 600, "discount": 0.20},
]


def print_banner():
    print(f"{ANSI.CYAN}{'='*70}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{ANSI.YELLOW}   LAB SIMULASI: R TIDYVERSE (dplyr & tidyr) PIPELINE RUNNER{ANSI.RESET}")
    print(f"{ANSI.CYAN}   BAB-03: Data Wrangling & Manipulation dengan Modern Tidyverse{ANSI.RESET}")
    print(f"{ANSI.CYAN}{'='*70}{ANSI.RESET}\n")


def demo_pipeline():
    print(f"{ANSI.BOLD}{ANSI.GREEN}>>> SKENARIO 1: Chained Data Pipeline Menggunakan Native Pipe (|>) {ANSI.RESET}")
    print(f"{ANSI.DIM}Representasi sintaks R Tidyverse:{ANSI.RESET}")
    print(f"""{ANSI.YELLOW}ecommerce_tbl |>
  filter(category == 'Elektronik') |>
  mutate(total_sales = q1_sales + q2_sales,
         net_sales = total_sales * (1 - discount)) |>
  group_by(region) |>
  summarize(
    total_revenue = sum(net_sales),
    avg_revenue = mean(net_sales),
    n_transactions = n()
  ) |>
  arrange(desc(total_revenue)){ANSI.RESET}\n""")

    init_tbl = Tibble(raw_ecommerce_data)
    print(f"{ANSI.BOLD}[1] Dataframe Awal (Raw Tibble):{ANSI.RESET}")
    print(init_tbl)
    print()

    # Eksekusi pipeline
    res_tbl = (
        init_tbl
        >> filter_rows(lambda r: r["category"] == "Elektronik")
        >> mutate(
            total_sales=lambda r: r["q1_sales"] + r["q2_sales"],
            net_sales=lambda r: (r["q1_sales"] + r["q2_sales"]) * (1.0 - r["discount"])
        )
        >> group_by("region")
        >> summarize(
            total_revenue=lambda rows: round(sum(r["net_sales"] for r in rows), 2),
            avg_revenue=lambda rows: round(sum(r["net_sales"] for r in rows) / len(rows), 2),
            n_trans=lambda rows: len(rows)
        )
        >> arrange("total_revenue", descending=True)
    )

    print(f"{ANSI.BOLD}{ANSI.GREEN}[2] Hasil Eksekusi Pipeline (dplyr Aggregation):{ANSI.RESET}")
    print(res_tbl)
    print()


def demo_pivoting():
    print(f"{ANSI.BOLD}{ANSI.GREEN}>>> SKENARIO 2: Reshaping Tidy Data dengan tidyr::pivot_longer() {ANSI.RESET}")
    print(f"{ANSI.DIM}Mengubah format Wide (q1_sales, q2_sales) menjadi Long (quarter, sales_value):{ANSI.RESET}")
    print(f"""{ANSI.YELLOW}ecommerce_tbl |>
  select(customer, category, q1_sales, q2_sales) |>
  pivot_longer(
    cols = c(q1_sales, q2_sales),
    names_to = 'quarter',
    values_to = 'sales_value'
  ){ANSI.RESET}\n""")

    init_tbl = Tibble(raw_ecommerce_data)
    long_tbl = (
        init_tbl
        >> select("customer", "category", "q1_sales", "q2_sales")
        >> pivot_longer(cols=["q1_sales", "q2_sales"], names_to="quarter", values_to="sales_value")
    )
    print(f"{ANSI.BOLD}[Hasil Tidy Table (Narrow / Long Format)]:{ANSI.RESET}")
    print(long_tbl)
    print()


def interactive_quiz():
    print(f"{ANSI.BOLD}{ANSI.MAGENTA}>>> INTERACTIVE DRILL: Tebak Fungsi Tidyverse{ANSI.RESET}")
    questions = [
        {
            "q": "Fungsi apa yang digunakan di dplyr untuk membuat kolom baru atau memodifikasi kolom lama?",
            "choices": ["A. select()", "B. mutate()", "C. transmute()", "D. arrange()"],
            "ans": "B",
            "expl": "mutate() menambahkan kolom baru tanpa membuang kolom yang sudah ada."
        },
        {
            "q": "Operator pipe native R yang diperkenalkan secara resmi sejak R versi 4.1.0 adalah:",
            "choices": ["A. %>%", "B. ->", "C. |>", "D. ~"],
            "ans": "C",
            "expl": "|> adalah native pipe operator bawaan base R; %>% berasal dari package magrittr."
        },
        {
            "q": "Untuk mengubah data dari format wide (banyak kolom kuartal) ke long (satu kolom nama, satu kolom nilai), fungsi tidyr modern yang digunakan adalah:",
            "choices": ["A. spread()", "B. gather()", "C. pivot_wider()", "D. pivot_longer()"],
            "ans": "D",
            "expl": "pivot_longer() menggantikan gather() sebagai standar modern tidyverse."
        }
    ]

    score = 0
    for idx, item in enumerate(questions, 1):
        print(f"\n{ANSI.BOLD}Soal {idx}: {item['q']}{ANSI.RESET}")
        for c in item["choices"]:
            print(f"  {c}")
        ans = input(f"{ANSI.CYAN}Pilihan Anda (A/B/C/D) [default: {item['ans']}]: {ANSI.RESET}").strip().upper()
        if not ans:
            ans = item["ans"]

        if ans == item["ans"]:
            print(f"{ANSI.GREEN}✓ Benar! {item['expl']}{ANSI.RESET}")
            score += 1
        else:
            print(f"{ANSI.RED}✗ Salah. Jawaban benar: {item['ans']}. {item['expl']}{ANSI.RESET}")

    print(f"\n{ANSI.BOLD}{ANSI.YELLOW}Skor Latihan Mandiri: {score}/{len(questions)}{ANSI.RESET}")


def main():
    print_banner()
    demo_pipeline()
    demo_pivoting()
    interactive_quiz()
    print(f"\n{ANSI.BOLD}{ANSI.GREEN}✔ Sesi Lab Selesai! Kode siap dipraktikkan langsung pada sesi R Studio / VS Code R Interactive.{ANSI.RESET}\n")


if __name__ == "__main__":
    main()
