#!/usr/bin/env python3
"""
Lab Hands-on: CSS3 Foundations - Box Model, Specificity & Rendering Pipeline
Kategori : 01-Core-Foundations (frontend-beginner)
Bab      : 03 - Modul 02 Deep Dive

Script mandiri ini mensimulasikan mekanisme internal browser engine:
1. CSS Specificity Calculator (Resolusi Cascade berbasis 4-vektor: Inline, ID, Class, Element)
2. Box Model Geometry Engine (Komputasi layout content-box vs border-box)
3. Browser Rendering Pipeline (DOM + CSSOM -> Render Tree -> Layout/Reflow -> Paint)
"""

import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# Terminal Color Formatting (ANSI Escapes)
# ==============================================================================
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[31m"
CLR_GREEN   = "\033[32m"
CLR_YELLOW  = "\033[33m"
CLR_BLUE    = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN    = "\033[36m"
CLR_BG_DARK = "\033[48;5;236m"


# ==============================================================================
# BAGIAN 1: CSS Specificity Engine
# ==============================================================================
@dataclass(order=True)
class Specificity:
    """
    Representasi 4-tuple Specificity CSS: (Inline, ID, Class/Attr/Pseudo-Class, Element/Pseudo-Element).
    Tuple orderable secara natural: (a, b, c, d) > (w, x, y, z).
    """
    inline: int = 0
    ids: int = 0
    classes: int = 0
    elements: int = 0

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.inline, self.ids, self.classes, self.elements)

    def __str__(self) -> str:
        return f"({self.inline}, {self.ids}, {self.classes}, {self.elements})"


def calculate_specificity(selector: str, is_inline: bool = False) -> Specificity:
    """
    Menganalisis string selector CSS menggunakan RegEx untuk mengekstrak bobot specificity.
    Mengabaikan universal selector '*' dan combinator (+, >, ~, spasi).
    """
    if is_inline:
        return Specificity(inline=1, ids=0, classes=0, elements=0)

    # Bersihkan whitespace berlebih & pseudo-element double colon normalization
    clean_sel = selector.strip()

    # 1. Hitung IDs (#example)
    id_matches = re.findall(r'#[a-zA-Z0-9_-]+', clean_sel)
    ids_count = len(id_matches)
    clean_sel = re.sub(r'#[a-zA-Z0-9_-]+', ' ', clean_sel)

    # 2. Hitung Classes (.class), Attributes ([type="text"]), dan Pseudo-classes (:hover)
    # Catatan: Pseudo-element (:before, ::before) harus dibedakan.
    pseudo_elements = re.findall(r'::[a-zA-Z0-9_-]+|:(?:before|after|first-line|first-letter)', clean_sel)
    clean_sel = re.sub(r'::[a-zA-Z0-9_-]+|:(?:before|after|first-line|first-letter)', ' ', clean_sel)

    classes_matches = re.findall(r'\.[a-zA-Z0-9_-]+', clean_sel)
    attrs_matches = re.findall(r'\[[^\]]+\]', clean_sel)
    pseudo_classes_matches = re.findall(r':[a-zA-Z0-9_-]+', clean_sel)
    classes_count = len(classes_matches) + len(attrs_matches) + len(pseudo_classes_matches)

    clean_sel = re.sub(r'\.[a-zA-Z0-9_-]+', ' ', clean_sel)
    clean_sel = re.sub(r'\[[^\]]+\]', ' ', clean_sel)
    clean_sel = re.sub(r':[a-zA-Z0-9_-]+', ' ', clean_sel)

    # 3. Hitung Elements dan Pseudo-elements
    elements_matches = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', clean_sel)
    elements_count = len(elements_matches) + len(pseudo_elements)

    return Specificity(inline=0, ids=ids_count, classes=classes_count, elements=elements_count)


# ==============================================================================
# BAGIAN 2: Box Model Geometry Simulator
# ==============================================================================
class BoxSizing(Enum):
    CONTENT_BOX = "content-box"  # Standar W3C Default
    BORDER_BOX  = "border-box"   # Standar Modern Responsive Layout


@dataclass
class BoxDimensions:
    width: float
    height: float
    padding_top: float = 0.0
    padding_right: float = 0.0
    padding_bottom: float = 0.0
    padding_left: float = 0.0
    border_top: float = 0.0
    border_right: float = 0.0
    border_bottom: float = 0.0
    border_left: float = 0.0
    margin_top: float = 0.0
    margin_right: float = 0.0
    margin_bottom: float = 0.0
    margin_left: float = 0.0
    box_sizing: BoxSizing = BoxSizing.CONTENT_BOX

    def compute_layout(self) -> Dict[str, float]:
        """
        Menghitung geometri bounding box berdasarkan box-sizing model.
        Menghasilkan dimensi absolut konten, padding box, border box, dan total space.
        """
        h_padding = self.padding_left + self.padding_right
        v_padding = self.padding_top + self.padding_bottom
        h_border = self.border_left + self.border_right
        v_border = self.border_top + self.border_bottom
        h_margin = self.margin_left + self.margin_right
        v_margin = self.margin_top + self.margin_bottom

        if self.box_sizing == BoxSizing.CONTENT_BOX:
            # CSS width/height murni menentukan konten
            content_w = self.width
            content_h = self.height
            rendered_w = content_w + h_padding + h_border
            rendered_h = content_h + v_padding + v_border
        else:
            # BORDER_BOX: CSS width/height mencakup content + padding + border
            rendered_w = self.width
            rendered_h = self.height
            content_w = max(0.0, self.width - h_padding - h_border)
            content_h = max(0.0, self.height - v_padding - v_border)

        total_footprint_w = rendered_w + h_margin
        total_footprint_h = rendered_h + v_margin

        return {
            "content_w": content_w,
            "content_h": content_h,
            "rendered_w": rendered_w,
            "rendered_h": rendered_h,
            "total_footprint_w": total_footprint_w,
            "total_footprint_h": total_footprint_h,
        }


# ==============================================================================
# BAGIAN 3: Browser Rendering Pipeline Simulator
# ==============================================================================
@dataclass
class DOMNode:
    tag: str
    id_attr: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    style_attr: Dict[str, str] = field(default_factory=dict)
    children: List['DOMNode'] = field(default_factory=list)


@dataclass
class CSSRule:
    selector: str
    properties: Dict[str, str]
    specificity: Specificity = field(init=False)

    def __post_init__(self):
        self.specificity = calculate_specificity(self.selector)


@dataclass
class RenderObject:
    node: DOMNode
    computed_styles: Dict[str, str]
    bounding_box: Optional[Dict[str, float]] = None


class BrowserRenderingEngine:
    """
    Simulasi sekuensial engine browser:
    DOM Tree + CSSOM Rules -> Render Tree (Match & Resolve Specificity) -> Reflow (Layout) -> Paint.
    """
    def __init__(self, css_rules: List[CSSRule]):
        self.css_rules = css_rules
        self.metrics = {"reflow_count": 0, "paint_count": 0, "duration_ms": 0.0}

    def _matches_selector(self, node: DOMNode, selector: str) -> bool:
        """Evaluator kecocokan selector sederhana (ID, class, tag)."""
        sel = selector.strip()
        if sel.startswith('#'):
            return node.id_attr == sel[1:]
        elif sel.startswith('.'):
            return sel[1:] in node.classes
        elif sel == node.tag:
            return True
        return False

    def build_render_tree(self, root: DOMNode) -> List[RenderObject]:
        """
        Tahap 1: Pembentukan Render Tree.
        Mengabaikan node 'display: none', menggabungkan style berdasarkan specificity cascade.
        """
        render_tree: List[RenderObject] = []

        def traverse(node: DOMNode):
            matched_declarations: List[Tuple[Specificity, Dict[str, str]]] = []

            # 1. Evaluasi dari CSSOM
            for rule in self.css_rules:
                if self._matches_selector(node, rule.selector):
                    matched_declarations.append((rule.specificity, rule.properties))

            # 2. Urutkan berdasarkan Specificity terendah ke tertinggi
            matched_declarations.sort(key=lambda x: x[0])

            # 3. Cascade styles
            computed: Dict[str, str] = {}
            for _, props in matched_declarations:
                computed.update(props)

            # 4. Inline style selalu override (Specificity inline: 1, 0, 0, 0)
            if node.style_attr:
                computed.update(node.style_attr)

            # Node dengan display: none dieliminasi dari Render Tree
            if computed.get("display") != "none":
                render_tree.append(RenderObject(node=node, computed_styles=computed))

            for child in node.children:
                traverse(child)

        traverse(root)
        return render_tree

    def layout_reflow(self, render_tree: List[RenderObject]):
        """
        Tahap 2: Layout / Reflow.
        Menghitung geometri piksel sebenarnya untuk setiap node visual.
        """
        t0 = time.perf_counter()
        for ro in render_tree:
            sizing_mode = (
                BoxSizing.BORDER_BOX
                if ro.computed_styles.get("box-sizing") == "border-box"
                else BoxSizing.CONTENT_BOX
            )

            # Ekstrak besaran numerik piksel (fallback default bila tidak diset)
            def parse_px(val: Optional[str], default: float = 0.0) -> float:
                if not val:
                    return default
                match = re.search(r'([\d.]+)', val)
                return float(match.group(1)) if match else default

            w = parse_px(ro.computed_styles.get("width"), 100.0)
            h = parse_px(ro.computed_styles.get("height"), 50.0)
            p = parse_px(ro.computed_styles.get("padding"), 0.0)
            b = parse_px(ro.computed_styles.get("border"), 0.0)
            m = parse_px(ro.computed_styles.get("margin"), 0.0)

            box = BoxDimensions(
                width=w, height=h,
                padding_top=p, padding_right=p, padding_bottom=p, padding_left=p,
                border_top=b, border_right=b, border_bottom=b, border_left=b,
                margin_top=m, margin_right=m, margin_bottom=m, margin_left=m,
                box_sizing=sizing_mode
            )
            ro.bounding_box = box.compute_layout()
            self.metrics["reflow_count"] += 1

        self.metrics["duration_ms"] += (time.perf_counter() - t0) * 1000

    def paint(self, render_tree: List[RenderObject]):
        """
        Tahap 3: Paint.
        Mengonversi koordinat geometri dan computed styles menjadi instruksi visual terminal.
        """
        t0 = time.perf_counter()
        print(f"\n{CLR_BOLD}{CLR_CYAN}=== RENDER PIPELINE: PAINT STAGE ==={CLR_RESET}")
        for ro in render_tree:
            node_name = ro.node.tag
            if ro.node.id_attr:
                node_name += f"#{ro.node.id_attr}"
            if ro.node.classes:
                node_name += f".{'.'.join(ro.node.classes)}"

            color = ro.computed_styles.get("color", "white")
            bg = ro.computed_styles.get("background", "default")
            geom = ro.bounding_box

            print(f"  {CLR_GREEN}↳ RASTERIZE{CLR_RESET} [Node: {CLR_BOLD}{node_name:<20}{CLR_RESET}] "
                  f"Rendered: {CLR_YELLOW}{geom['rendered_w']:.0f}x{geom['rendered_h']:.0f}px{CLR_RESET} | "
                  f"Content: {geom['content_w']:.0f}x{geom['content_h']:.0f}px | "
                  f"Colors: (fg={color}, bg={bg})")
            self.metrics["paint_count"] += 1

        self.metrics["duration_ms"] += (time.perf_counter() - t0) * 1000


# ==============================================================================
# CLI Orchestrator & Demonstrator
# ==============================================================================
def print_header(title: str):
    print(f"\n{CLR_BOLD}{CLR_MAGENTA}{'=' * 75}")
    print(f"  {title}")
    print(f"{'=' * 75}{CLR_RESET}")


def run_specificity_lab():
    print_header("LAB 1: Resolusi Konflik CSS Specificity")
    selectors = [
        "nav ul li.active a:hover",
        "header #main-nav div.link",
        "a::before",
        "body #app .content p.lead",
        "#nav",
        "p",
        "div > div > p",
    ]

    print(f"{'Selector':<35} | {'Inline':<6} | {'IDs':<4} | {'Classes':<7} | {'Elements':<8} | {'Total Score'}")
    print("-" * 75)
    for sel in selectors:
        spec = calculate_specificity(sel)
        print(f"{CLR_CYAN}{sel:<35}{CLR_RESET} | "
              f"{spec.inline:<6} | {spec.ids:<4} | {spec.classes:<7} | {spec.elements:<8} | "
              f"{CLR_BOLD}{spec}{CLR_RESET}")


def run_box_model_lab():
    print_header("LAB 2: Box Model Metrics: Content-Box vs Border-Box")
    params = {
        "width": 300.0, "height": 100.0,
        "padding_top": 20.0, "padding_right": 20.0, "padding_bottom": 20.0, "padding_left": 20.0,
        "border_top": 5.0, "border_right": 5.0, "border_bottom": 5.0, "border_left": 5.0,
        "margin_top": 15.0, "margin_right": 15.0, "margin_bottom": 15.0, "margin_left": 15.0,
    }

    # Hitung Content-Box
    cb = BoxDimensions(**params, box_sizing=BoxSizing.CONTENT_BOX).compute_layout()
    # Hitung Border-Box
    bb = BoxDimensions(**params, box_sizing=BoxSizing.BORDER_BOX).compute_layout()

    print(f"{'Parameter Geometri':<28} | {'content-box (W3C Legacy)':<25} | {'border-box (Modern Standard)'}")
    print("-" * 80)
    print(f"CSS Specified (W x H)        | {300}px x {100}px                 | {300}px x {100}px")
    print(f"Content Area Box             | {CLR_RED}{cb['content_w']:.0f}px x {cb['content_h']:.0f}px{CLR_RESET}{'':<15} | {CLR_GREEN}{bb['content_w']:.0f}px x {bb['content_h']:.0f}px{CLR_RESET}")
    print(f"Rendered Visual Box (W x H)  | {CLR_RED}{cb['rendered_w']:.0f}px x {cb['rendered_h']:.0f}px [EXPANDED]{CLR_RESET}      | {CLR_GREEN}{bb['rendered_w']:.0f}px x {bb['rendered_h']:.0f}px [EXACT]{CLR_RESET}")
    print(f"Total Layout Footprint       | {cb['total_footprint_w']:.0f}px x {cb['total_footprint_h']:.0f}px                 | {bb['total_footprint_w']:.0f}px x {bb['total_footprint_h']:.0f}px")


def run_pipeline_lab():
    print_header("LAB 3: End-to-End Rendering Pipeline Simulation")

    # 1. Definisi Aturan CSS (CSSOM)
    css_rules = [
        CSSRule(selector="button", properties={"width": "120px", "height": "40px", "background": "gray", "color": "white"}),
        CSSRule(selector=".btn-primary", properties={"background": "blue", "border": "2px", "padding": "8px"}),
        CSSRule(selector="#submit-btn", properties={"background": "green", "box-sizing": "border-box"}),
        CSSRule(selector=".hidden-element", properties={"display": "none"}),
    ]

    # 2. Definisi Struktur DOM
    dom_tree = DOMNode(
        tag="div",
        id_attr="wrapper",
        children=[
            DOMNode(tag="p", classes=["lead"], style_attr={"color": "darkgray", "width": "500px", "height": "60px"}),
            DOMNode(tag="button", id_attr="submit-btn", classes=["btn-primary"]),
            DOMNode(tag="button", classes=["btn-primary"]),
            DOMNode(tag="div", classes=["hidden-element"], style_attr={"width": "100px", "height": "100px"})
        ]
    )

    print(f"{CLR_YELLOW}[1/4] Membangun CSSOM & Parsing Tree... Selesai.{CLR_RESET}")
    engine = BrowserRenderingEngine(css_rules)

    print(f"{CLR_YELLOW}[2/4] Menghitung Resolusi Cascade & Memfilter Node Tersembunyi (Render Tree)...{CLR_RESET}")
    render_tree = engine.build_render_tree(dom_tree)
    print(f"      -> Total Elemen DOM: 5 | Lolos ke Render Tree: {len(render_tree)} (1 dieliminasi: 'display: none')")

    print(f"{CLR_YELLOW}[3/4] Eksekusi Layout Stage (Reflow)...{CLR_RESET}")
    engine.layout_reflow(render_tree)

    print(f"{CLR_YELLOW}[4/4] Eksekusi Paint Stage (Rasterization)...{CLR_RESET}")
    engine.paint(render_tree)

    print(f"\n{CLR_BOLD}Pipeline Telemetry Summary:{CLR_RESET}")
    print(f"  Reflow Operations : {CLR_CYAN}{engine.metrics['reflow_count']}{CLR_RESET}")
    print(f"  Paint Operations  : {CLR_CYAN}{engine.metrics['paint_count']}{CLR_RESET}")
    print(f"  Execution Time    : {CLR_GREEN}{engine.metrics['duration_ms']:.4f} ms{CLR_RESET}")


def main():
    try:
        run_specificity_lab()
        run_box_model_lab()
        run_pipeline_lab()
        print(f"\n{CLR_BOLD}{CLR_GREEN}✓ Seluruh modul demonstrasi fondasi CSS3 berhasil dieksekusi.{CLR_RESET}\n")
    except KeyboardInterrupt:
        print(f"\n{CLR_RED}Eksekusi dibatalkan oleh user.{CLR_RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()