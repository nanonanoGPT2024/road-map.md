#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Engine Next.js App Router
BAB 02: Routing Lanjutan - Parallel Routes & Intercepting Routes

Deskripsi:
Simulasi interaktif berbasis terminal (ANSI color-coded) yang mereplikasi
cara kerja Next.js App Router dalam mengelola:
1. Parallel Routes (@slot, layout slots, independent rendering, default.tsx fallback)
2. Intercepting Routes ((.)photo modal vs hard-reload standalone page)
"""

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum

# ANSI Color Codes untuk Terminal Styling
class Color:
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
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_DARK = "\033[100m"

class NavigationType(Enum):
    SOFT = "CLIENT_SIDE_TRANSITION (Soft Navigation)"
    HARD = "FULL_PAGE_RELOAD (Hard Navigation / SSR Initial Request)"

@dataclass
class SlotState:
    name: str
    active_component: str
    rendered_from_default: bool = False
    is_loading: bool = False

@dataclass
class RouterContext:
    browser_url: str = "/feed"
    active_modal: Optional[str] = None
    slots: Dict[str, SlotState] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)

class NextRoutingEngine:
    def __init__(self):
        self.context = RouterContext()
        self._init_layout_slots()

    def _init_layout_slots(self):
        """Inisialisasi layout root: children (@main), @analytics, dan @modal."""
        self.context.slots = {
            "children": SlotState(name="children (Main View)", active_component="FeedPage (app/feed/page.tsx)"),
            "@analytics": SlotState(name="@analytics", active_component="AnalyticsSummary (app/feed/@analytics/page.tsx)"),
            "@modal": SlotState(name="@modal", active_component="null (app/feed/@modal/default.tsx)", rendered_from_default=True)
        }

    def print_banner(self):
        print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} ================================================================ {Color.RESET}")
        print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD}   NEXT.JS ADVANCED ROUTING SIMULATOR (CLI LAB M01)              {Color.RESET}")
        print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD}   Parallel Routes (@slot) & Intercepting Routes ((.)photo)     {Color.RESET}")
        print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD} ================================================================ {Color.RESET}\n")

    def render_virtual_dom(self, last_action: str = ""):
        """Visualisasi status rendering komponen Next.js pada terminal."""
        ctx = self.context
        print("\033[H\033[J", end="")  # Clear screen ANSI
        self.print_banner()

        if last_action:
            print(f"{Color.YELLOW}{Color.BOLD}[EVENT LOG]{Color.RESET} {last_action}\n")

        print(f"{Color.BOLD}Browser Address Bar : {Color.GREEN}http://localhost:3000{ctx.browser_url}{Color.RESET}")
        print(f"{Color.BOLD}Active Layout Path  : {Color.CYAN}app/feed/layout.tsx{Color.RESET}")
        print(f"{Color.DIM}{'-'*64}{Color.RESET}")

        print(f"\n{Color.BOLD}{Color.MAGENTA}--- [LAYOUT VIEWPORT TREE] ---{Color.RESET}")
        for slot_key, slot in ctx.slots.items():
            fallback_badge = f"{Color.YELLOW}[default.tsx]{Color.RESET}" if slot.rendered_from_default else f"{Color.GREEN}[page.tsx]{Color.RESET}"
            print(f"  {Color.BOLD} Slot {slot_key:<12}{Color.RESET} : {Color.WHITE}{slot.active_component:<40}{Color.RESET} {fallback_badge}")

        print(f"\n{Color.BOLD}{Color.CYAN}--- [INTERCEPTOR MODAL OVERLAY] ---{Color.RESET}")
        if ctx.active_modal:
            print(f"  {Color.BG_MAGENTA}{Color.WHITE}{Color.BOLD} MODAL OPEN {Color.RESET} Rendering: {Color.YELLOW}{ctx.active_modal}{Color.RESET}")
            print(f"  {Color.DIM}Background page tetap utuh tanpa remount! (Preserved state){Color.RESET}")
        else:
            print(f"  {Color.DIM}(Tidak ada modal aktif - Slot @modal mengembalikan null dari default.tsx){Color.RESET}")

        print(f"\n{Color.DIM}{'='*64}{Color.RESET}")

    def soft_navigate_photo(self, photo_id: str):
        """Simulasi Klik Link: Intercepting Route (.)photo/[id] bekerja."""
        self.context.browser_url = f"/feed/photo/{photo_id}"
        self.context.active_modal = f"PhotoModal (app/feed/@modal/(.)photo/[id]/page.tsx?id={photo_id})"
        self.context.slots["@modal"].active_component = self.context.active_modal
        self.context.slots["@modal"].rendered_from_default = False
        action_msg = (
            f"{Color.GREEN}Link clicked <Link href='/feed/photo/{photo_id}'>{Color.RESET}\n"
            f"   -> Mode: {Color.BOLD}{NavigationType.SOFT.value}{Color.RESET}\n"
            f"   -> Interceptor: {Color.CYAN}(.)photo/[id]{Color.RESET} menangkap navigasi!\n"
            f"   -> Slot @modal menampilkan modal di atas feed tanpa re-render slot children."
        )
        self.render_virtual_dom(action_msg)

    def hard_reload(self, target_url: Optional[str] = None):
        """Simulasi Hard Refresh (F5 / Direct URL Hit)."""
        url = target_url or self.context.browser_url
        self.context.browser_url = url

        if "/photo/" in url:
            # Pada hard reload ke route foto, interceptor TIDAK aktif.
            # Next.js langsung menyajikan full standalone page.
            photo_id = url.split("/")[-1]
            self.context.active_modal = None
            self.context.slots = {
                "children": SlotState(
                    name="children (Main View)",
                    active_component=f"StandalonePhotoPage (app/photo/[id]/page.tsx?id={photo_id})"
                ),
                "@analytics": SlotState(
                    name="@analytics",
                    active_component="null (app/@analytics/default.tsx)",
                    rendered_from_default=True
                ),
                "@modal": SlotState(
                    name="@modal",
                    active_component="null (app/@modal/default.tsx)",
                    rendered_from_default=True
                )
            }
            action_msg = (
                f"{Color.RED}Browser Hard Refresh / Direct URL hit: {url}{Color.RESET}\n"
                f"   -> Mode: {Color.BOLD}{NavigationType.HARD.value}{Color.RESET}\n"
                f"   -> Intercepting route dilewati (bypassed).\n"
                f"   -> Merender halaman penuh: app/photo/[id]/page.tsx.\n"
                f"   -> Parallel slots belum memiliki kecocokan sehingga memanggil default.tsx!"
            )
        else:
            self._init_layout_slots()
            self.context.active_modal = None
            action_msg = (
                f"{Color.CYAN}Browser Hard Reload pada {url}{Color.RESET}\n"
                f"   -> Semua parallel slots dimuat ulang dari server."
            )

        self.render_virtual_dom(action_msg)

    def dismiss_modal(self):
        """Simulasi router.back() atau menutup modal dialog."""
        if not self.context.active_modal:
            self.render_virtual_dom(f"{Color.YELLOW}Peringatan: Tidak ada modal aktif untuk ditutup.{Color.RESET}")
            return

        self.context.browser_url = "/feed"
        self.context.active_modal = None
        self.context.slots["@modal"].active_component = "null (app/feed/@modal/default.tsx)"
        self.context.slots["@modal"].rendered_from_default = True

        action_msg = (
            f"{Color.MAGENTA}router.back() dipanggil (Modal ditutup){Color.RESET}\n"
            f"   -> URL kembali ke /feed.\n"
            f"   -> Slot @modal dikembalikan ke default.tsx (null)."
        )
        self.render_virtual_dom(action_msg)

    def switch_parallel_tab(self, view_name: str):
        """Simulasi navigasi independen pada satu slot tanpa mengganggu slot lain."""
        comp_name = f"AnalyticsMetricsView ({view_name})"
        self.context.slots["@analytics"].active_component = comp_name
        self.context.slots["@analytics"].rendered_from_default = False

        action_msg = (
            f"{Color.CYAN}Navigasi Independen di Slot @analytics -> {view_name}{Color.RESET}\n"
            f"   -> Slot children dan @modal TIDAK re-render atau terganggu.\n"
            f"   -> Membuktikan isolasi state pada parallel routing Next.js."
        )
        self.render_virtual_dom(action_msg)


def run_interactive_lab():
    engine = NextRoutingEngine()
    engine.render_virtual_dom("Sistem diinisialisasi. Layout feed aktif dengan 3 parallel slots.")

    while True:
        print(f"\n{Color.BOLD}PILIH AKSI SIMULASI:{Color.RESET}")
        print("1. [Soft Nav] Klik foto di Feed (Trigger Intercepting Route: (.)photo/101)")
        print("2. [Dismiss]  Tutup Modal (Trigger router.back() -> kembali ke /feed)")
        print("3. [Hard Nav] Tekan F5 / Hard Reload saat URL /feed/photo/101")
        print("4. [Parallel] Ganti tab metriks pada slot @analytics (Independent Sub-route)")
        print("5. [Reset]    Kembali ke status awal (/feed)")
        print("0. Keluar dari lab")

        try:
            choice = input(f"\n{Color.CYAN}Masukkan pilihan [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Lab dihentikan.{Color.RESET}")
            break

        if choice == "1":
            engine.soft_navigate_photo("101")
        elif choice == "2":
            engine.dismiss_modal()
        elif choice == "3":
            engine.hard_reload("/feed/photo/101")
        elif choice == "4":
            engine.switch_parallel_tab("app/feed/@analytics/metrics/page.tsx")
        elif choice == "5":
            engine.hard_reload("/feed")
        elif choice == "0":
            print(f"\n{Color.GREEN}Simulasi Next.js Parallel & Intercepting Routes selesai. Selamat belajar!{Color.RESET}\n")
            break
        else:
            engine.render_virtual_dom(f"{Color.RED}Pilihan tidak valid: {choice}. Masukkan angka 0-5.{Color.RESET}")


def run_automated_verification():
    """Mode verifikasi otomatis (CI / Headless check)."""
    print(f"{Color.BOLD}Menjalankan uji sintaks dan logika otomatis NextRoutingEngine...{Color.RESET}")
    engine = NextRoutingEngine()
    assert "@analytics" in engine.context.slots
    assert engine.context.slots["@modal"].rendered_from_default is True

    # Test soft navigation
    engine.soft_navigate_photo("999")
    assert engine.context.active_modal is not None
    assert "999" in engine.context.browser_url
    assert engine.context.slots["@modal"].rendered_from_default is False

    # Test modal dismissal
    engine.dismiss_modal()
    assert engine.context.active_modal is None
    assert engine.context.browser_url == "/feed"

    # Test hard navigation standalone bypass
    engine.hard_reload("/feed/photo/999")
    assert engine.context.active_modal is None
    assert "StandalonePhotoPage" in engine.context.slots["children"].active_component

    print(f"{Color.GREEN}Semua uji logika NextRoutingEngine berhasil 100%!{Color.RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        run_automated_verification()
    else:
        # Jika terminal non-interaktif, jalankan verifikasi agar tidak hanging
        if not sys.stdin.isatty():
            run_automated_verification()
        else:
            run_interactive_lab()
