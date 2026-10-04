#!/usr/bin/env python3
"""
Lab Exercise M01: Simulasi Interaktif Fondasi & Arsitektur Flutter
BAB-01: Fondasi dan Arsitektur Flutter

Topik Inti yang Disimulasikan:
1. Tiga Pohon Flutter (Widget Tree, Element Tree, RenderObject Tree)
2. Mekanisme "Constraints Go Down, Sizes Go Up, Parent Sets Position"
3. Pipeline Render Frame (Animate -> Build -> Layout -> Paint -> Composite)
4. Perbandingan State Immutability vs Rebuild Efficiency
"""

import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict

# ANSI Terminal Colors & Styling
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Colors.RESET}"

# ==============================================================================
# 1. KONSEP DASAR BOX CONSTRAINTS & LAYOUT MODEL
# ==============================================================================

@dataclass
class BoxConstraints:
    min_width: float
    max_width: float
    min_height: float
    max_height: float

    def constrain(self, width: float, height: float) -> Tuple[float, float]:
        clamped_w = max(self.min_width, min(width, self.max_width))
        clamped_h = max(self.min_height, min(height, self.max_height))
        return (clamped_w, clamped_h)

    def is_tight(self) -> bool:
        return self.min_width == self.max_width and self.min_height == self.max_height

    def __str__(self) -> str:
        return f"BoxConstraints(w: {self.min_width}..{self.max_width}, h: {self.min_height}..{self.max_height})"

# ==============================================================================
# 2. TIGA POHON FLUTTER: WIDGET, ELEMENT, RENDEROBJECT
# ==============================================================================

class Widget:
    """Widget: Blueprint deklaratif, immutable, lightweight."""
    def __init__(self, key: Optional[str] = None):
        self.key = key

    def create_element(self) -> 'Element':
        raise NotImplementedError()

class ContainerWidget(Widget):
    def __init__(self, width: float, height: float, child: Optional[Widget] = None, color_name: str = "Blue"):
        super().__init__()
        self.width = width
        self.height = height
        self.child = child
        self.color_name = color_name

    def create_element(self) -> 'Element':
        return ContainerElement(self)

class TextWidget(Widget):
    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def create_element(self) -> 'Element':
        return TextElement(self)

class RenderObject:
    """RenderObject: Mengelola kalkulasi ukuran (layout) dan menggambar (paint)."""
    def __init__(self, name: str):
        self.name = name
        self.size: Tuple[float, float] = (0.0, 0.0)
        self.position: Tuple[float, float] = (0.0, 0.0)
        self.children: List['RenderObject'] = []

    def perform_layout(self, constraints: BoxConstraints):
        raise NotImplementedError()

    def paint(self, offset: Tuple[float, float], depth: int = 0) -> List[str]:
        raise NotImplementedError()

class RenderBoxContainer(RenderObject):
    def __init__(self, target_w: float, target_h: float, color_name: str):
        super().__init__("RenderDecoratedBox")
        self.target_w = target_w
        self.target_h = target_h
        self.color_name = color_name

    def perform_layout(self, constraints: BoxConstraints):
        # Rule: Constraints go down, Sizes go up, Parent sets position
        # Child layout first under relaxed/adjusted constraints
        child_w, child_h = 0.0, 0.0
        if self.children:
            child_constraints = BoxConstraints(
                min_width=0,
                max_width=constraints.max_width,
                min_height=0,
                max_height=constraints.max_height
            )
            for child in self.children:
                child.perform_layout(child_constraints)
                child_w = max(child_w, child.size[0])
                child_h = max(child_h, child.size[1])
                # Parent sets child position (misal padding 8px)
                child.position = (8.0, 8.0)

        # Container tries to take requested target, clamped to constraints
        w = max(self.target_w, child_w + 16.0 if self.children else self.target_w)
        h = max(self.target_h, child_h + 16.0 if self.children else self.target_h)
        self.size = constraints.constrain(w, h)

    def paint(self, offset: Tuple[float, float], depth: int = 0) -> List[str]:
        cur_x = offset[0] + self.position[0]
        cur_y = offset[1] + self.position[1]
        lines = [
            f"{'  ' * depth}├── [Paint Canvas] Container '{self.color_name}' at ({cur_x:.1f}, {cur_y:.1f}) Size: {self.size[0]}x{self.size[1]}"
        ]
        for child in self.children:
            lines.extend(child.paint((cur_x, cur_y), depth + 1))
        return lines

class RenderBoxText(RenderObject):
    def __init__(self, text: str):
        super().__init__("RenderParagraph")
        self.text = text

    def perform_layout(self, constraints: BoxConstraints):
        # Menghitung estimasi ukuran text (7px per karakter, tinggi 16px)
        est_w = len(self.text) * 7.5
        est_h = 16.0
        self.size = constraints.constrain(est_w, est_h)

    def paint(self, offset: Tuple[float, float], depth: int = 0) -> List[str]:
        cur_x = offset[0] + self.position[0]
        cur_y = offset[1] + self.position[1]
        return [
            f"{'  ' * depth}└── [Paint Glyph] Text \"{self.text}\" at ({cur_x:.1f}, {cur_y:.1f}) Bounds: {self.size[0]}x{self.size[1]}"
        ]

class Element:
    """Element: Bridge penahan lifecycle yang menghubungkan Widget ke RenderObject."""
    def __init__(self, widget: Widget):
        self.widget = widget
        self.child: Optional['Element'] = None
        self.render_object: Optional[RenderObject] = None

    def mount(self, parent: Optional['Element']):
        raise NotImplementedError()

    def update(self, new_widget: Widget):
        self.widget = new_widget

class ContainerElement(Element):
    def mount(self, parent: Optional['Element']):
        container_w = self.widget  # type: ContainerWidget
        self.render_object = RenderBoxContainer(container_w.width, container_w.height, container_w.color_name)
        if container_w.child:
            self.child = container_w.child.create_element()
            self.child.mount(self)
            if self.child.render_object:
                self.render_object.children.append(self.child.render_object)

class TextElement(Element):
    def mount(self, parent: Optional['Element']):
        text_w = self.widget  # type: TextWidget
        self.render_object = RenderBoxText(text_w.text)

# ==============================================================================
# 3. ENGINE FRAME PIPELINE SIMULATION
# ==============================================================================

class FlutterEnginePipeline:
    def __init__(self, screen_w: float = 360.0, screen_h: float = 640.0):
        self.screen_constraints = BoxConstraints(screen_w, screen_w, screen_h, screen_h)
        self.root_element: Optional[Element] = None

    def run_frame(self, root_widget: Widget):
        print(colorize("\n" + "=" * 65, Colors.HEADER))
        print(colorize("▶ EKSEKUSI RENDER PIPELINE SATU FRAME (VSYNC TRIGGER)", Colors.BOLD + Colors.CYAN))
        print(colorize("=" * 65, Colors.HEADER))

        # Phase 1: Animate
        print(colorize("[Phase 1: Animate]", Colors.YELLOW) + " Evaluasi Ticker, Tween, & Physics Controllers...")
        time.sleep(0.05)

        # Phase 2: Build
        print(colorize("[Phase 2: Build]", Colors.GREEN) + " Mengonversi Widget Tree menjadi Element Tree...")
        if self.root_element is None:
            self.root_element = root_widget.create_element()
            self.root_element.mount(None)
            print("  └─ Mount root Element & instansiasi RenderObject Tree (Clean Mount)")
        else:
            self.root_element.update(root_widget)
            print("  └─ Diffing widget blueprint & perbarui referensi element yang relevan")
        time.sleep(0.05)

        # Phase 3: Layout
        print(colorize("[Phase 3: Layout]", Colors.BLUE) + " Menjalankan 'Constraints Down, Sizes Up'...")
        root_render = self.root_element.render_object
        if root_render:
            root_render.perform_layout(self.screen_constraints)
            print(f"  └─ Screen Tight Constraints: {self.screen_constraints}")
            print(f"  └─ Root RenderObject Resolved Size: {root_render.size[0]} x {root_render.size[1]} pt")
        time.sleep(0.05)

        # Phase 4: Paint
        print(colorize("[Phase 4: Paint]", Colors.CYAN) + " Merekam DisplayList Command untuk Skia/Impeller...")
        if root_render:
            commands = root_render.paint((0.0, 0.0), depth=1)
            for cmd in commands:
                print(cmd)
        time.sleep(0.05)

        # Phase 5: Composite
        print(colorize("[Phase 5: Composite]", Colors.HEADER) + " Mengirim Scene Layer Tree ke GPU Rasterizer via Impeller...")
        print("  └─ Pipeline Complete! Frame berhasil dirender ke layar (0.00ms jank).")
        print(colorize("=" * 65 + "\n", Colors.HEADER))

# ==============================================================================
# 4. INTERACTIVE SIMULATION MENU & VISUAL INSPECTOR
# ==============================================================================

def print_banner():
    banner = f"""
{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗
║    FLUTTER ARCHITECTURE & FOUNDATION LAB SIMULATOR (M01)       ║
║     Memahami 3-Tree Architecture, Layout Rule & Engine Loop    ║
╚════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)

def demo_three_trees():
    print(colorize("--- 1. INSPEKSI TIGA POHON FLUTTER ---", Colors.BOLD + Colors.YELLOW))
    print("Membangun hirarki UI:\nContainer(w=200, h=80, child: Text('Halo Dunia!'))\n")
    
    widget = ContainerWidget(width=200, height=80, color_name="IndigoAccent", child=TextWidget("Halo Dunia!"))
    element = widget.create_element()
    element.mount(None)
    render_obj = element.render_object

    # Print Visual Perbandingan
    print(colorize("[1] WIDGET TREE (Blueprint Deklaratif)", Colors.GREEN))
    print("    ContainerWidget (width=200, height=80, color='IndigoAccent')")
    print("      └── TextWidget (text='Halo Dunia!')")
    print(colorize("    * Karakteristik: Immutable, murah dibuang dan dibuat ulang setiap frame.", Colors.DIM))

    print(colorize("\n[2] ELEMENT TREE (Manajer Siklus Hidup & State)", Colors.BLUE))
    print("    ContainerElement (Stateful/Stateless context, memegang referensi RenderObject)")
    print("      └── TextElement (Menghubungkan TextWidget ke RenderParagraph)")
    print(colorize("    * Karakteristik: Persisten, hanya di-relink/update saat widget berganti tipe/key.", Colors.DIM))

    print(colorize("\n[3] RENDEROBJECT TREE (Geometri, Hit Testing & GPU Paint)", Colors.CYAN))
    print("    RenderDecoratedBox (Layout calculations, bounds, color drawing)")
    print("      └── RenderParagraph (Text metrics layout, glyph drawing)")
    print(colorize("    * Karakteristik: Mahal, mengelola perhitungan dimensi fisik layar secara langsung.", Colors.DIM))

def demo_layout_rule():
    print(colorize("--- 2. ATURAN EMAS: CONSTRAINTS DOWN, SIZES UP ---", Colors.BOLD + Colors.YELLOW))
    print("Simulasi interaktif bagaimana Parent membatasi Child:\n")

    screen_w = 320.0
    screen_h = 480.0
    parent_constraints = BoxConstraints(min_width=0, max_width=screen_w, min_height=0, max_height=screen_h)

    print(f"Parent memberikan Constraints ke Container: {colorize(str(parent_constraints), Colors.GREEN)}")
    
    desired_w = 400.0  # Melebihi layar!
    desired_h = 100.0
    print(f"Container meminta ukuran: {desired_w} x {desired_h} pt")
    
    resolved_w, resolved_h = parent_constraints.constrain(desired_w, desired_h)
    print(colorize(f"-> Ukuran akhir yang diizinkan (Clamped): {resolved_w} x {resolved_h} pt", Colors.BOLD + Colors.CYAN))
    print(colorize("Catatan Arsitektur: Widget anak TIDAK BISA memaksakan ukuran di luar batas Constraints parent.", Colors.DIM))

def run_interactive_engine():
    engine = FlutterEnginePipeline()
    sample_text = "Flutter Impeller Ready"
    widget = ContainerWidget(width=300, height=120, color_name="MaterialEmerald", child=TextWidget(sample_text))
    
    print(colorize("Menjalankan Frame Render Engine Pertama Kali...", Colors.BOLD + Colors.GREEN))
    engine.run_frame(widget)

    print(colorize("Simulasi State Rebuild (misal: Text berubah melalui setState())...", Colors.BOLD + Colors.YELLOW))
    updated_widget = ContainerWidget(width=300, height=120, color_name="MaterialEmerald", child=TextWidget("Status: Rebuilt via setState()"))
    engine.run_frame(updated_widget)

def main():
    print_banner()
    while True:
        print(colorize("Pilih menu pengujian:", Colors.BOLD))
        print("  1. Inspeksi Tiga Pohon Flutter (Widget, Element, RenderObject)")
        print("  2. Uji Aturan Layout (Constraints Down, Sizes Up, Parent Sets Position)")
        print("  3. Jalankan Engine Frame Pipeline (Animate -> Build -> Layout -> Paint -> Composite)")
        print("  4. Jalankan Semua Simulasi Sekaligus")
        print("  5. Keluar")
        
        choice = input(colorize("\nMasukkan pilihan (1-5): ", Colors.CYAN)).strip()
        print()
        
        if choice == '1':
            demo_three_trees()
        elif choice == '2':
            demo_layout_rule()
        elif choice == '3':
            run_interactive_engine()
        elif choice == '4':
            demo_three_trees()
            print("\n" + "-"*50 + "\n")
            demo_layout_rule()
            print("\n" + "-"*50 + "\n")
            run_interactive_engine()
        elif choice in ('5', 'q', 'exit'):
            print(colorize("Terima kasih telah menggunakan Flutter Architecture Simulator!", Colors.GREEN))
            break
        else:
            print(colorize("Pilihan tidak valid, silakan coba lagi.", Colors.RED))
        
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colorize("\n\nSimulasi dihentikan oleh pengguna.", Colors.YELLOW))
        sys.exit(0)
