#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Engine Manipulasi DOM Lanjutan & Event-Driven Architecture
Topik: BAB 07 - Manipulasi DOM Lanjutan dan Event-Driven (Frontend Beginner)

Simulasi Python 3 murni (stand-alone) yang mereplikasi:
1. Struktur Pohon DOM Hierarkis (Parent, Children, Attributes, Dataset).
2. Mekanisme Event Propagation 3-Fase:
   - Phase 1: CAPTURING_PHASE (Window/Document -> Target)
   - Phase 2: AT_TARGET (Target node listener)
   - Phase 3: BUBBLING_PHASE (Target -> Document/Window)
3. Event Delegation Pattern (Menangani event elemen dinamis di parent).
4. Custom Events & Event Cancellation (stopPropagation & preventDefault).
5. Output visual interaktif dengan formatting ANSI Escape Codes.
"""

from __future__ import annotations
import sys
import time
from typing import Callable, Dict, List, Optional, Any

# ANSI Color Palette untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"
CLR_GRAY = "\033[90m"


class EventPhase:
    NONE = 0
    CAPTURING = 1
    AT_TARGET = 2
    BUBBLING = 3

    @classmethod
    def to_string(cls, phase: int) -> str:
        mapping = {
            cls.NONE: "NONE",
            cls.CAPTURING: f"{CLR_BLUE}CAPTURING (Fase 1: Turun){CLR_RESET}",
            cls.AT_TARGET: f"{CLR_MAGENTA}AT_TARGET (Fase 2: Target){CLR_RESET}",
            cls.BUBBLING: f"{CLR_YELLOW}BUBBLING (Fase 3: Naik){CLR_RESET}",
        }
        return mapping.get(phase, "UNKNOWN")


class DOMEvent:
    """Representasi Event W3C DOM standar."""
    def __init__(self, event_type: str, bubbles: bool = True, cancelable: bool = True, detail: Any = None):
        self.type: str = event_type
        self.bubbles: bool = bubbles
        self.cancelable: bool = cancelable
        self.detail: Any = detail
        
        self.target: Optional[DOMNode] = None
        self.current_target: Optional[DOMNode] = None
        self.event_phase: int = EventPhase.NONE
        
        self._propagation_stopped: bool = False
        self._default_prevented: bool = False
        self.timestamp: float = time.time()

    def stop_propagation(self) -> None:
        """Menghentikan perambatan event ke ancestor/descendant berikutnya."""
        self._propagation_stopped = True
        print(f"      {CLR_RED}⚡ [stopPropagation() terpanggil] Propagasi event diputus!{CLR_RESET}")

    def prevent_default(self) -> None:
        """Mencegah aksi bawaan browser jika event cancelable."""
        if self.cancelable:
            self._default_prevented = True
            print(f"      {CLR_YELLOW}⚠️ [preventDefault() terpanggil] Aksi default dibatalkan!{CLR_RESET}")
        else:
            print(f"      {CLR_GRAY}ℹ️ [preventDefault()] Event tidak dapat dibatalkan (cancelable=False).{CLR_RESET}")

    @property
    def is_propagation_stopped(self) -> bool:
        return self._propagation_stopped

    @property
    def is_default_prevented(self) -> bool:
        return self._default_prevented


class DOMNode:
    """Representasi Node dalam hirarki Virtual DOM."""
    def __init__(self, tag_name: str, node_id: str = "", classes: Optional[List[str]] = None):
        self.tag_name: str = tag_name.upper()
        self.id: str = node_id
        self.classes: List[str] = classes or []
        self.attributes: Dict[str, str] = {}
        self.dataset: Dict[str, str] = {}
        self.text_content: str = ""
        
        self.parent: Optional[DOMNode] = None
        self.children: List[DOMNode] = []
        
        # Format listeners: { event_type: [ {"callback": fn, "use_capture": bool} ] }
        self._listeners: Dict[str, List[Dict[str, Any]]] = {}

    def append_child(self, child: DOMNode) -> DOMNode:
        """Menambahkan elemen anak ke dalam node ini."""
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: DOMNode) -> Optional[DOMNode]:
        """Menghapus elemen anak."""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return child
        return None

    def add_event_listener(self, event_type: str, callback: Callable[[DOMEvent], None], use_capture: bool = False) -> None:
        """Mendaftarkan listener event (Capture atau Bubble)."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append({
            "callback": callback,
            "use_capture": use_capture
        })

    def get_listeners(self, event_type: str, capture_phase: bool) -> List[Callable[[DOMEvent], None]]:
        """Mengambil listener yang cocok dengan fase eksekusi."""
        matched = []
        for item in self._listeners.get(event_type, []):
            if item["use_capture"] == capture_phase:
                matched.append(item["callback"])
        return matched

    def dispatch_event(self, event: DOMEvent) -> bool:
        """
        Menjalankan 3 siklus propagasi event:
        1. Capturing Phase
        2. Target Phase
        3. Bubbling Phase
        """
        event.target = self
        
        # Bentuk rantai hierarki dari root document hingga target parent
        path: List[DOMNode] = []
        curr: Optional[DOMNode] = self.parent
        while curr is not None:
            path.append(curr)
            curr = curr.parent
        capture_path = list(reversed(path))  # Root -> Parent
        bubble_path = path                  # Parent -> Root

        print(f"\n{CLR_CYAN}{'=' * 65}{CLR_RESET}")
        print(f"{CLR_BOLD}DISPATCH EVENT: '{event.type}' pada <{self.identifier()}>{CLR_RESET}")
        print(f"{CLR_CYAN}{'=' * 65}{CLR_RESET}")

        # ---------------- FASE 1: CAPTURING ----------------
        event.event_phase = EventPhase.CAPTURING
        print(f"\n{CLR_BOLD}--- [1] FASE CAPTURING (Top-Down) ---{CLR_RESET}")
        if not capture_path:
            print(f"  {CLR_GRAY}(Tidak ada ancestor untuk fase capturing){CLR_RESET}")
        for ancestor in capture_path:
            if event.is_propagation_stopped:
                break
            event.current_target = ancestor
            listeners = ancestor.get_listeners(event.type, capture_phase=True)
            print(f"  🔻 Memeriksa Ancestor: <{ancestor.identifier()}> | Capture Listeners: {len(listeners)}")
            for cb in listeners:
                cb(event)
                if event.is_propagation_stopped:
                    break

        # ---------------- FASE 2: AT TARGET ----------------
        if not event.is_propagation_stopped:
            event.event_phase = EventPhase.AT_TARGET
            event.current_target = self
            print(f"\n{CLR_BOLD}--- [2] FASE AT_TARGET (Eksekusi Target) ---{CLR_RESET}")
            # Target mengeksekusi capture listener lalu bubble listener
            all_target_listeners = self._listeners.get(event.type, [])
            print(f"  🎯 Node Target: <{self.identifier()}> | Total Listeners: {len(all_target_listeners)}")
            for item in all_target_listeners:
                item["callback"](event)
                if event.is_propagation_stopped:
                    break

        # ---------------- FASE 3: BUBBLING ----------------
        if not event.is_propagation_stopped and event.bubbles:
            event.event_phase = EventPhase.BUBBLING
            print(f"\n{CLR_BOLD}--- [3] FASE BUBBLING (Bottom-Up) ---{CLR_RESET}")
            if not bubble_path:
                print(f"  {CLR_GRAY}(Tidak ada ancestor untuk fase bubbling){CLR_RESET}")
            for ancestor in bubble_path:
                if event.is_propagation_stopped:
                    break
                event.current_target = ancestor
                listeners = ancestor.get_listeners(event.type, capture_phase=False)
                print(f"  🔺 Gelembung ke Ancestor: <{ancestor.identifier()}> | Bubble Listeners: {len(listeners)}")
                for cb in listeners:
                    cb(event)
                    if event.is_propagation_stopped:
                        break
        elif not event.bubbles:
            print(f"\n{CLR_GRAY}ℹ️ Event tidak memiliki kemampuan bubbling (bubbles=False). Selesai di target.{CLR_RESET}")

        print(f"\n{CLR_GREEN}✓ Siklus Dispatch Selesai! (Default Prevented: {event.is_default_prevented}){CLR_RESET}\n")
        return not event.is_default_prevented

    def matches(self, selector: str) -> bool:
        """Pemeriksaan selector sederhana (#id, .class, tag)."""
        if selector.startswith("#"):
            return self.id == selector[1:]
        elif selector.startswith("."):
            return selector[1:] in self.classes
        else:
            return self.tag_name.lower() == selector.lower()

    def query_selector(self, selector: str) -> Optional[DOMNode]:
        """Pencarian node anak berdasarkan selector."""
        for child in self.children:
            if child.matches(selector):
                return child
            res = child.query_selector(selector)
            if res:
                return res
        return None

    def identifier(self) -> str:
        """String ringkas representasi node."""
        parts = [self.tag_name.lower()]
        if self.id:
            parts.append(f"#{self.id}")
        if self.classes:
            parts.append("." + ".".join(self.classes))
        return "".join(parts)

    def print_tree(self, indent: int = 0) -> None:
        """Visualisasi pohon DOM ke terminal."""
        prefix = "  " * indent + "└─ " if indent > 0 else ""
        attr_str = ""
        if self.dataset:
            attr_str = f" {CLR_GRAY}[data: {self.dataset}]{CLR_RESET}"
        text_str = f' "{self.text_content}"' if self.text_content else ""
        
        print(f"{prefix}{CLR_BOLD}{CLR_CYAN}<{self.identifier()}>{CLR_RESET}{text_str}{attr_str}")
        for child in self.children:
            child.print_tree(indent + 1)


# =====================================================================
# LABORATORIUM PRAKTIK INTERAKTIF
# =====================================================================

def build_sample_dom() -> DOMNode:
    """
    Membangun struktur DOM realistis untuk toko online:
    <div#app.container>
        <header#header>
            <h1#title> "Toko Gadget Modern"
        <main#main-content>
            <ul#product-list.list-group>
                <li.product-item data-id="101">
                    <span.name> "Laptop Ultrabook"
                    <button.btn-buy data-action="buy"> "Beli Sekarang"
                <li.product-item data-id="102">
                    <span.name> "Wireless Mouse"
                    <button.btn-buy data-action="buy"> "Beli Sekarang"
        <footer#footer>
            <a#link-help href="/help"> "Pusat Bantuan"
    """
    root = DOMNode("div", node_id="app", classes=["container"])
    
    # Header
    header = DOMNode("header", node_id="header")
    title = DOMNode("h1", node_id="title")
    title.text_content = "Toko Gadget Modern"
    header.append_child(title)
    root.append_child(header)
    
    # Main Product List
    main = DOMNode("main", node_id="main-content")
    ul = DOMNode("ul", node_id="product-list", classes=["list-group"])
    
    # Item 1
    li1 = DOMNode("li", classes=["product-item"])
    li1.dataset = {"id": "101", "name": "Laptop Ultrabook", "price": "15000000"}
    span1 = DOMNode("span", classes=["name"])
    span1.text_content = "Laptop Ultrabook"
    btn1 = DOMNode("button", classes=["btn-buy"])
    btn1.dataset = {"action": "buy"}
    btn1.text_content = "Beli Sekarang"
    li1.append_child(span1)
    li1.append_child(btn1)
    ul.append_child(li1)
    
    # Item 2
    li2 = DOMNode("li", classes=["product-item"])
    li2.dataset = {"id": "102", "name": "Wireless Mouse", "price": "250000"}
    span2 = DOMNode("span", classes=["name"])
    span2.text_content = "Wireless Mouse"
    btn2 = DOMNode("button", classes=["btn-buy"])
    btn2.dataset = {"action": "buy"}
    btn2.text_content = "Beli Sekarang"
    li2.append_child(span2)
    li2.append_child(btn2)
    ul.append_child(li2)
    
    main.append_child(ul)
    root.append_child(main)
    
    # Footer
    footer = DOMNode("footer", node_id="footer")
    link = DOMNode("a", node_id="link-help")
    link.attributes["href"] = "/help"
    link.text_content = "Pusat Bantuan"
    footer.append_child(link)
    root.append_child(footer)
    
    return root


def demo_event_flow(root: DOMNode) -> None:
    """Eksperimen 1: Mendemonstrasikan 3 Fase Event Flow Lengkap."""
    print(f"\n{CLR_YELLOW}=== EKSPERIMEN 1: Alur Propagasi Event W3C (Capture -> Target -> Bubble) ==={CLR_RESET}")
    print("Mendaftarkan event listener pada: #app (Capture & Bubble), #main-content (Bubble), dan .btn-buy (Target)\n")

    main_content = root.query_selector("#main-content")
    btn_buy = root.query_selector(".btn-buy")

    # 1. Capture Listener di Root
    def on_app_capture(e: DOMEvent) -> None:
        print(f"      👉 [LOG #app CAPTURE] Fase: {EventPhase.to_string(e.event_phase)} | currentTarget: <{e.current_target.identifier()}>")
    root.add_event_listener("click", on_app_capture, use_capture=True)

    # 2. Bubble Listener di Root
    def on_app_bubble(e: DOMEvent) -> None:
        print(f"      👉 [LOG #app BUBBLE] Fase: {EventPhase.to_string(e.event_phase)} | currentTarget: <{e.current_target.identifier()}>")
    root.add_event_listener("click", on_app_bubble, use_capture=False)

    # 3. Bubble Listener di Main
    def on_main_bubble(e: DOMEvent) -> None:
        print(f"      👉 [LOG #main-content BUBBLE] Fase: {EventPhase.to_string(e.event_phase)} | currentTarget: <{e.current_target.identifier()}>")
    if main_content:
        main_content.add_event_listener("click", on_main_bubble, use_capture=False)

    # 4. Listener Target pada Tombol Beli
    def on_button_click(e: DOMEvent) -> None:
        print(f"      🎯 [LOG .btn-buy TARGET] Tombol diklik! Detail item: {e.target.parent.dataset}")
    if btn_buy:
        btn_buy.add_event_listener("click", on_button_click, use_capture=False)
        # Trigger simulasi klik
        click_event = DOMEvent("click", bubbles=True, cancelable=True)
        btn_buy.dispatch_event(click_event)


def demo_event_delegation(root: DOMNode) -> None:
    """Eksperimen 2: Pola Event Delegation untuk Kinerja Tinggi."""
    print(f"\n{CLR_YELLOW}=== EKSPERIMEN 2: Pola Event Delegation pada Parent Elemen ==={CLR_RESET}")
    print("Daripada memasang listener ke 1000 item li/button, kita pasang 1 listener di #product-list.")
    print("Listener memeriksa `e.target` untuk aksi tertentu (data-action='buy').\n")

    ul_list = root.query_selector("#product-list")
    if not ul_list:
        return

    def delegation_handler(e: DOMEvent) -> None:
        print(f"   📥 [Delegation Handler pada <{e.current_target.identifier()}>]")
        target = e.target
        if not target:
            return
        
        # Mengecek apakah elemen yang diklik adalah tombol beli
        if target.matches(".btn-buy") and target.dataset.get("action") == "buy":
            parent_li = target.parent
            item_name = parent_li.dataset.get("name", "Unknown") if parent_li else "Unknown"
            item_price = parent_li.dataset.get("price", "0") if parent_li else "0"
            print(f"      {CLR_GREEN}🛒 SUKSES DIDELEGASIKAN: Membeli '{item_name}' seharga Rp {int(item_price):,}{CLR_RESET}")
        else:
            print(f"      {CLR_GRAY}ℹ️ Elemen <{target.identifier()}> diklik tetapi bukan tombol aksi.{CLR_RESET}")

    ul_list.add_event_listener("click", delegation_handler, use_capture=False)

    # Simulasi 1: Klik tombol beli pada item 2
    item2 = ul_list.children[1]
    btn_item2 = item2.query_selector(".btn-buy")
    print(f"{CLR_BOLD}Skenario A: User mengeklik tombol beli item kedua...{CLR_RESET}")
    if btn_item2:
        btn_item2.dispatch_event(DOMEvent("click", bubbles=True))

    # Simulasi 2: Menambahkan item baru secara dinamis (tanpa re-binding event listener!)
    print(f"\n{CLR_BOLD}Skenario B: Menambahkan elemen baru secara dinamis ke DOM (Runtime)...{CLR_RESET}")
    new_li = DOMNode("li", classes=["product-item"])
    new_li.dataset = {"id": "103", "name": "Mechanical Keyboard RGB", "price": "850000"}
    new_btn = DOMNode("button", classes=["btn-buy"])
    new_btn.dataset = {"action": "buy"}
    new_btn.text_content = "Beli Sekarang"
    new_li.append_child(new_btn)
    ul_list.append_child(new_li)
    print(f"   {CLR_GREEN}+ Elemen baru ditambahkan: <li.product-item [id: 103]>{CLR_RESET}")

    print(f"\n{CLR_BOLD}Skenario C: Mengeklik tombol pada elemen dinamis baru...{CLR_RESET}")
    new_btn.dispatch_event(DOMEvent("click", bubbles=True))
    print(f"   {CLR_CYAN}💡 Terbukti: Elemen baru otomatis didukung tanpa attach listener tambahan!{CLR_RESET}")


def demo_stop_propagation(root: DOMNode) -> None:
    """Eksperimen 3: Menghentikan Bubbling dengan stopPropagation."""
    print(f"\n{CLR_YELLOW}=== EKSPERIMEN 3: Mengisolasi Event dengan stopPropagation() ==={CLR_RESET}")
    print("Contoh Kasus: Modal Popup atau Dropdown di mana klik di dalam konten tidak boleh menutup modal.")

    # Membuat modal container dan konten
    modal_overlay = DOMNode("div", node_id="modal-overlay")
    modal_content = DOMNode("div", node_id="modal-box")
    modal_button = DOMNode("button", node_id="modal-action")
    modal_button.text_content = "Konfirmasi"
    
    modal_content.append_child(modal_button)
    modal_overlay.append_child(modal_content)
    root.append_child(modal_overlay)

    # Handler Overlay: menutup modal jika overlay diklik
    def close_modal(e: DOMEvent) -> None:
        print(f"      {CLR_RED}🚪 [Overlay Clicked] Modal Ditutup!{CLR_RESET}")
    modal_overlay.add_event_listener("click", close_modal, use_capture=False)

    # Handler Box Konten: menghentikan event agar tidak tembus ke overlay
    def handle_box_click(e: DOMEvent) -> None:
        print(f"      📦 [Box Konten Diklik] Memproses interaksi dalam box...")
        e.stop_propagation()
    modal_content.add_event_listener("click", handle_box_click, use_capture=False)

    print(f"\n{CLR_BOLD}A. Klik langsung pada Kotak Konten (Diharapkan modal TIDAK tertutup):{CLR_RESET}")
    modal_button.dispatch_event(DOMEvent("click", bubbles=True))

    print(f"\n{CLR_BOLD}B. Klik langsung pada Area Overlay luar (Diharapkan modal tertutup):{CLR_RESET}")
    modal_overlay.dispatch_event(DOMEvent("click", bubbles=True))


def interactive_menu() -> None:
    """Tampilan menu interaktif CLI terminal."""
    dom_tree = build_sample_dom()
    
    while True:
        print(f"\n{CLR_BOLD}{CLR_BLUE}╔═══════════════════════════════════════════════════════════════════╗{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}║        LAB MANIPULASI DOM LANJUTAN & EVENT-DRIVEN (BAB 07)        ║{CLR_RESET}")
        print(f"{CLR_BOLD}{CLR_BLUE}╚═══════════════════════════════════════════════════════════════════╝{CLR_RESET}")
        print(f" {CLR_CYAN}1.{CLR_RESET} Tampilkan Struktur Virtual DOM Tree")
        print(f" {CLR_CYAN}2.{CLR_RESET} Jalankan Eksperimen 1: 3-Fase W3C Event Flow (Capture/Target/Bubble)")
        print(f" {CLR_CYAN}3.{CLR_RESET} Jalankan Eksperimen 2: Event Delegation & Dynamic Elements")
        print(f" {CLR_CYAN}4.{CLR_RESET} Jalankan Eksperimen 3: Event Interception & stopPropagation()")
        print(f" {CLR_CYAN}5.{CLR_RESET} Jalankan SEMUA Eksperimen Sekaligus")
        print(f" {CLR_CYAN}0.{CLR_RESET} Keluar")
        print(f"{CLR_BLUE}───────────────────────────────────────────────────────────────────{CLR_RESET}")
        
        try:
            choice = input(f"{CLR_BOLD}Pilih opsi [0-5]: {CLR_RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nProgram dihentikan.")
            break

        if choice == "1":
            print(f"\n{CLR_BOLD}=== STRUKTUR VIRTUAL DOM TREE ==={CLR_RESET}\n")
            dom_tree.print_tree()
        elif choice == "2":
            demo_event_flow(dom_tree)
        elif choice == "3":
            demo_event_delegation(dom_tree)
        elif choice == "4":
            demo_stop_propagation(dom_tree)
        elif choice == "5":
            print(f"\n{CLR_BOLD}=== STRUKTUR VIRTUAL DOM TREE ==={CLR_RESET}\n")
            dom_tree.print_tree()
            demo_event_flow(dom_tree)
            demo_event_delegation(dom_tree)
            demo_stop_propagation(dom_tree)
        elif choice == "0":
            print(f"\n{CLR_GREEN}Terima kasih telah bereksperimen dengan Event Engine! Sampai jumpa.{CLR_RESET}\n")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid. Silakan masukkan angka 0 sampai 5.{CLR_RESET}")


if __name__ == "__main__":
    # Jika dijalankan dengan parameter '--auto' atau non-interaktif, jalankan demo lengkap
    if len(sys.argv) > 1 and sys.argv[1] in ("--auto", "--test", "-y"):
        tree = build_sample_dom()
        tree.print_tree()
        demo_event_flow(tree)
        demo_event_delegation(tree)
        demo_stop_propagation(tree)
        sys.exit(0)
    
    # Mode default interaktif
    interactive_menu()
