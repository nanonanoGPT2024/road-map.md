#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Inti Arsitektur Komponen Tingkat Lanjut & Komposisi UI Angular
BAB-03: Arsitektur Komponen Tingkat Lanjut dan Komposisi UI
"""

import sys
import time
from typing import Dict, List, Any, Optional, Callable

# ANSI Color Codes untuk visualisasi terminal interaktif
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class TemplateRef:
    """Simulasi TemplateRef: Referensi template deklaratif (<ng-template>) dengan context binding."""
    def __init__(self, template_id: str, render_fn: Callable[[Dict[str, Any]], str]):
        self.template_id = template_id
        self.render_fn = render_fn

    def instantiate(self, context: Dict[str, Any]) -> str:
        return self.render_fn(context)


class EmbeddedViewRef:
    """Simulasi EmbeddedViewRef: View instansiasi yang dihasilkan dari TemplateRef."""
    def __init__(self, template_ref: TemplateRef, context: Dict[str, Any]):
        self.template_ref = template_ref
        self.context = context
        self.rendered_output = template_ref.instantiate(context)


class ViewContainerRef:
    """Simulasi ViewContainerRef (VCR): Kontainer dinamis untuk createEmbeddedView / createComponent."""
    def __init__(self, anchor_name: str):
        self.anchor_name = anchor_name
        self._views: List[EmbeddedViewRef] = []

    def create_embedded_view(self, template_ref: TemplateRef, context: Optional[Dict[str, Any]] = None) -> EmbeddedViewRef:
        ctx = context or {}
        view = EmbeddedViewRef(template_ref, ctx)
        self._views.append(view)
        return view

    def clear(self) -> None:
        self._views.clear()

    def render(self) -> str:
        if not self._views:
            return f"{Colors.DIM}<!-- empty ViewContainerRef: {self.anchor_name} -->{Colors.RESET}"
        return "\n".join([f"    [View #{i+1}] {v.rendered_output}" for i, v in enumerate(self._views)])


class ContentSlot:
    """Slot proyeksi konten untuk simulasi <ng-content select="...">"""
    def __init__(self, selector: Optional[str] = None):
        self.selector = selector  # None = fallback / default slot
        self.projected_items: List[str] = []

    def matches(self, slot_tag: str) -> bool:
        if self.selector is None:
            return True
        return self.selector.lower() == slot_tag.lower()


class AngularComponentNode:
    """Simulasi Komponen Angular dengan Multi-slot Content Projection, VCR, dan Lifecycle Hooks."""
    def __init__(self, selector: str):
        self.selector = selector
        self.slots: Dict[str, ContentSlot] = {
            "card-header": ContentSlot("header"),
            "card-body": ContentSlot("body"),
            "card-footer": ContentSlot("footer"),
            "default": ContentSlot(None)
        }
        self.vcr = ViewContainerRef(anchor_name=f"{selector}-dynamic-vcr")
        self.lifecycle_log: List[str] = []

    def project_content(self, slot_name: str, content: str) -> None:
        matched = False
        for name, slot in self.slots.items():
            if slot.selector and slot.matches(slot_name):
                slot.projected_items.append(content)
                matched = True
                break
        if not matched:
            self.slots["default"].projected_items.append(content)

    def trigger_lifecycle(self) -> None:
        """Simulasi eksekusi terurut lifecycle hooks komponen."""
        steps = [
            ("ngOnInit", "Inisialisasi input properties & dependensi"),
            ("ngAfterContentInit", "Semua ContentChild / ng-content selesai diproyeksikan"),
            ("ngAfterContentChecked", "Pemeriksaan perubahan pada projected content"),
            ("ngAfterViewInit", "Template view, ViewChild, dan ViewContainerRef siap diakses"),
            ("ngAfterViewChecked", "Pemeriksaan perubahan pada view template lokal")
        ]
        self.lifecycle_log.clear()
        for hook, desc in steps:
            self.lifecycle_log.append(f"{Colors.GREEN}✔ [{hook}]{Colors.RESET} -> {desc}")

    def render_dom(self) -> str:
        border = f"{Colors.CYAN}{'='*65}{Colors.RESET}"
        output = [
            border,
            f"{Colors.BOLD}{Colors.HEADER}<{self.selector}>{Colors.RESET}",
            f"{Colors.BOLD}--- [1. Multi-Slot Content Projection (<ng-content>)] ---{Colors.RESET}"
        ]

        # Render Header Slot
        headers = self.slots["card-header"].projected_items or ["(Tidak ada header diproyeksikan)"]
        output.append(f"  {Colors.CYAN}<ng-content select=\"[header]\">{Colors.RESET}")
        for h in headers:
            output.append(f"    • {h}")

        # Render Body Slot
        bodies = self.slots["card-body"].projected_items or ["(Body kosong)"]
        output.append(f"  {Colors.CYAN}<ng-content select=\"[body]\">{Colors.RESET}")
        for b in bodies:
            output.append(f"    • {b}")

        # Render Footer Slot
        footers = self.slots["card-footer"].projected_items or ["(Footer kosong)"]
        output.append(f"  {Colors.CYAN}<ng-content select=\"[footer]\">{Colors.RESET}")
        for f in footers:
            output.append(f"    • {f}")

        # Render Default Slot
        defaults = self.slots["default"].projected_items
        if defaults:
            output.append(f"  {Colors.CYAN}<ng-content (default slot)>{Colors.RESET}")
            for d in defaults:
                output.append(f"    • {d}")

        # Dynamic ViewContainerRef
        output.append(f"\n{Colors.BOLD}--- [2. Dynamic View Container (<ng-container #vcr>)] ---{Colors.RESET}")
        output.append(self.vcr.render())

        output.append(f"{Colors.BOLD}{Colors.HEADER}</{self.selector}>{Colors.RESET}")
        output.append(border)
        return "\n".join(output)


def print_banner():
    banner = f"""
{Colors.CYAN}╔═══════════════════════════════════════════════════════════════════╗
║         ANGULAR ADVANCED COMPONENT ARCHITECTURE LAB              ║
║       Multi-Slot Projection, ViewContainerRef & Lifecycle         ║
╚═══════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def interactive_simulation():
    print_banner()
    comp = AngularComponentNode(selector="app-smart-card")

    # Inisialisasi template deklaratif untuk simulasi TemplateRef
    admin_tpl = TemplateRef("adminTemplate", lambda ctx: f"{Colors.WARNING}[ADMIN BADGE]{Colors.RESET} User: {ctx.get('user', 'Guest')} | Role: {ctx.get('role', 'Viewer')}")
    metrics_tpl = TemplateRef("metricsTemplate", lambda ctx: f"{Colors.GREEN}[METRICS WIDGET]{Colors.RESET} Active Sessions: {ctx.get('sessions', 0)} | Latency: {ctx.get('latency', '0ms')}")

    # Seed initial projected content
    comp.project_content("header", f"{Colors.BOLD}Dashboard Analitik Enterprise{Colors.RESET}")
    comp.project_content("body", "Komponen utama dengan arsitektur modular.")
    comp.project_content("footer", f"{Colors.DIM}Terakhir diperbarui: 2026-10-06{Colors.RESET}")

    while True:
        print(f"\n{Colors.BOLD}PILIH MENU SIMULASI:{Colors.RESET}")
        print("1. Tampilkan Visualisasi DOM Komponen & Status VCR")
        print("2. Proyeksikan Konten Baru ke Slot (<ng-content>)")
        print("3. Muat Template Dinamis via ViewContainerRef (createEmbeddedView)")
        print("4. Bersihkan Dynamic Views (vcr.clear())")
        print("5. Trigger Lifecycle Hooks Audit (ngOnInit -> ngAfterViewInit)")
        print("6. Keluar")

        choice = input(f"\n{Colors.BOLD}{Colors.CYAN}Masukkan pilihan (1-6): {Colors.RESET}").strip()

        if choice == "1":
            print("\n" + comp.render_dom())

        elif choice == "2":
            print(f"\n{Colors.BOLD}Pilih Slot Tujuan:{Colors.RESET}")
            print("  a. header ([header])")
            print("  b. body ([body])")
            print("  c. footer ([footer])")
            print("  d. default (fallback slot)")
            slot_map = {"a": "header", "b": "body", "c": "footer", "d": "default"}
            s_choice = input(f"{Colors.CYAN}Pilihan slot (a/b/c/d): {Colors.RESET}").strip().lower()
            target_slot = slot_map.get(s_choice, "default")
            content_text = input(f"{Colors.CYAN}Teks konten yang diproyeksikan: {Colors.RESET}").strip()
            if not content_text:
                content_text = "Proyeksi konten otomatis (sample)"
            comp.project_content(target_slot, content_text)
            print(f"{Colors.GREEN}✔ Konten berhasil diproyeksikan ke slot '{target_slot}'.{Colors.RESET}")

        elif choice == "3":
            print(f"\n{Colors.BOLD}Pilih TemplateRef untuk diinstansiasi:{Colors.RESET}")
            print("  1. Admin Badge Template (Context: user & role)")
            print("  2. Performance Metrics Template (Context: sessions & latency)")
            t_choice = input(f"{Colors.CYAN}Pilihan template (1/2): {Colors.RESET}").strip()
            if t_choice == "1":
                user = input(f"{Colors.CYAN}Nama User [AdminOps]: {Colors.RESET}").strip() or "AdminOps"
                role = input(f"{Colors.CYAN}Role [Superuser]: {Colors.RESET}").strip() or "Superuser"
                comp.vcr.create_embedded_view(admin_tpl, {"user": user, "role": role})
                print(f"{Colors.GREEN}✔ EmbeddedViewRef berhasil dibuat dan disisipkan ke VCR!{Colors.RESET}")
            elif t_choice == "2":
                sessions = input(f"{Colors.CYAN}Active Sessions [1420]: {Colors.RESET}").strip() or "1420"
                latency = input(f"{Colors.CYAN}Latency [12ms]: {Colors.RESET}").strip() or "12ms"
                comp.vcr.create_embedded_view(metrics_tpl, {"sessions": sessions, "latency": latency})
                print(f"{Colors.GREEN}✔ Metrics EmbeddedViewRef berhasil di-mount ke VCR!{Colors.RESET}")
            else:
                print(f"{Colors.FAIL}Pilihan template tidak valid.{Colors.RESET}")

        elif choice == "4":
            comp.vcr.clear()
            print(f"{Colors.WARNING}✔ ViewContainerRef telah dikosongkan (vcr.clear()).{Colors.RESET}")

        elif choice == "5":
            print(f"\n{Colors.HEADER}=== Simulasi Eksekusi Lifecycle Hook Angular ==={Colors.RESET}")
            comp.trigger_lifecycle()
            for step in comp.lifecycle_log:
                time.sleep(0.15)
                print(f"  {step}")
            print(f"{Colors.CYAN}Status: Siklus deteksi dan komposisi komponen selesai.{Colors.RESET}")

        elif choice == "6":
            print(f"\n{Colors.GREEN}Keluar dari lab exercise. Selamat belajar arsitektur Angular!{Colors.RESET}\n")
            sys.exit(0)

        else:
            print(f"{Colors.FAIL}Pilihan tidak dikenal. Silakan masukkan angka 1-6.{Colors.RESET}")


if __name__ == "__main__":
    try:
        interactive_simulation()
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Proses dihentikan oleh pengguna.{Colors.RESET}")
        sys.exit(0)
