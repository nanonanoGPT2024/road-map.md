#!/usr/bin/env python3
"""
Lab Hands-on: Advanced Data Visualization & Graphic Communication (ggplot2)
Topic: R Language Grammar of Graphics Engine Simulation in Python
Author: Lead Systems Programmer

This script simulates the layered architecture of Hadley Wickham's 'ggplot2':
1. Data Ingestion & Aesthetic Mapping (aes: x, y, color, size)
2. Statistical Transformations & Scaling (linear mapping, color scales)
3. Geometric Layers (geom_point, geom_line, geom_smooth)
4. Coordinates & Rasterization (ANSI terminal canvas rendering engine)
5. Faceting & Theming (Legend, Axes, and Gridlines)
"""

import sys
import math
from typing import List, Dict, Any, Optional, Tuple

# Terminal ANSI Color Palette
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"
RED = "\033[31m"

COLOR_PALETTE = [
    "\033[38;5;196m",  # Red
    "\033[38;5;46m",   # Green
    "\033[38;5;33m",   # Dodger Blue
    "\033[38;5;226m",  # Yellow
    "\033[38;5;201m",  # Magenta
    "\033[38;5;51m",   # Cyan
]


class AestheticMapping:
    """Represents the aesthetic mapping aes(x, y, color, ...) in ggplot2."""
    def __init__(self, x: str, y: str, color: Optional[str] = None):
        self.x = x
        self.y = y
        self.color = color


class ScaleLinear:
    """Continuous linear scale for data normalization into canvas coordinates."""
    def __init__(self, data_min: float, data_max: float, screen_range: int):
        self.d_min = data_min
        self.d_max = data_max if data_max != data_min else data_min + 1.0
        self.screen_range = screen_range

    def transform(self, val: float) -> int:
        ratio = (val - self.d_min) / (self.d_max - self.d_min)
        pos = int(round(ratio * (self.screen_range - 1)))
        return max(0, min(self.screen_range - 1, pos))


class Canvas:
    """Virtual 2D terminal rasterizer supporting character and ANSI color buffer."""
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.char_buf = [[" " for _ in range(width)] for _ in range(height)]
        self.color_buf = [["" for _ in range(width)] for _ in range(height)]

    def draw_pixel(self, x: int, y: int, char: str, color: str = ""):
        # Invert y because canvas (0,0) is top-left, while Cartesian is bottom-left
        inv_y = self.height - 1 - y
        if 0 <= x < self.width and 0 <= inv_y < self.height:
            self.char_buf[inv_y][x] = char
            self.color_buf[inv_y][x] = color

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, char: str, color: str = ""):
        """Bresenham's Line Algorithm for rasterizing geom_line and geom_smooth."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            self.draw_pixel(x0, y0, char, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy


class Geom:
    """Base class for geometric representations."""
    def render(self, canvas: Canvas, data: List[Dict[str, Any]], aes: AestheticMapping,
               scale_x: ScaleLinear, scale_y: ScaleLinear, color_map: Dict[Any, str]):
        raise NotImplementedError


class GeomPoint(Geom):
    """Corresponds to ggplot2::geom_point(). Renders discrete markers."""
    def __init__(self, shape: str = "●"):
        self.shape = shape

    def render(self, canvas: Canvas, data: List[Dict[str, Any]], aes: AestheticMapping,
               scale_x: ScaleLinear, scale_y: ScaleLinear, color_map: Dict[Any, str]):
        for row in data:
            px = scale_x.transform(float(row[aes.x]))
            py = scale_y.transform(float(row[aes.y]))
            color = color_map.get(row.get(aes.color), WHITE) if aes.color else CYAN
            canvas.draw_pixel(px, py, self.shape, color)


class GeomSmooth(Geom):
    """Corresponds to ggplot2::geom_smooth(method='lm'). Computes Ordinary Least Squares."""
    def __init__(self, color: str = YELLOW):
        self.color = color

    def render(self, canvas: Canvas, data: List[Dict[str, Any]], aes: AestheticMapping,
               scale_x: ScaleLinear, scale_y: ScaleLinear, color_map: Dict[Any, str]):
        xs = [float(row[aes.x]) for row in data]
        ys = [float(row[aes.y]) for row in data]
        n = len(xs)
        if n < 2:
            return

        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        numerator = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
        denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0.0
        intercept = mean_y - slope * mean_x

        min_x = min(xs)
        max_x = max(xs)
        p1_x = scale_x.transform(min_x)
        p1_y = scale_y.transform(slope * min_x + intercept)
        p2_x = scale_x.transform(max_x)
        p2_y = scale_y.transform(slope * max_x + intercept)

        canvas.draw_line(p1_x, p1_y, p2_x, p2_y, "─", self.color)


class GGPlot:
    """The central composition engine mirroring ggplot(data, aes()) + layers."""
    def __init__(self, data: List[Dict[str, Any]], aes: AestheticMapping, title: str = ""):
        self.data = data
        self.aes = aes
        self.title = title
        self.layers: List[Geom] = []

    def __add__(self, layer: Geom):
        self.layers.append(layer)
        return self

    def _setup_color_mapping(self) -> Dict[Any, str]:
        color_map = {}
        if self.aes.color:
            unique_vals = sorted(list({row[self.aes.color] for row in self.data}))
            for i, val in enumerate(unique_vals):
                color_map[val] = COLOR_PALETTE[i % len(COLOR_PALETTE)]
        return color_map

    def render(self, width: int = 55, height: int = 15):
        # Calculate domain scales
        xs = [float(r[self.aes.x]) for r in self.data]
        ys = [float(r[self.aes.y]) for r in self.data]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        scale_x = ScaleLinear(min_x, max_x, width)
        scale_y = ScaleLinear(min_y, max_y, height)
        color_map = self._setup_color_mapping()

        # Canvas rasterization
        canvas = Canvas(width, height)

        # Draw light grid lines
        for y_idx in range(0, height, max(1, height // 4)):
            for x_idx in range(width):
                canvas.draw_pixel(x_idx, y_idx, "·", DIM + "\033[38;5;238m")

        # Execute render pipelining for each geom
        for geom in self.layers:
            geom.render(canvas, self.data, self.aes, scale_x, scale_y, color_map)

        # Output title
        print(f"\n{BOLD}{CYAN}# ggplot2 Graphics Engine Render Output{RESET}")
        print(f"{BOLD}Title: {self.title}{RESET}")
        print(f"{DIM}Layer stack: {[g.__class__.__name__ for g in self.layers]}{RESET}\n")

        # Draw Canvas Frame with Y Axis
        for row_i in range(height):
            # Y ticks every quarter
            cartesian_y = height - 1 - row_i
            if cartesian_y == 0:
                y_label = f"{min_y:5.1f} ┤"
            elif cartesian_y == height - 1:
                y_label = f"{max_y:5.1f} ┤"
            elif cartesian_y == height // 2:
                mid_val = (min_y + max_y) / 2
                y_label = f"{mid_val:5.1f} ┤"
            else:
                y_label = "      │"

            line_str = "".join(
                (canvas.color_buf[row_i][col_i] + canvas.char_buf[row_i][col_i] + RESET)
                for col_i in range(width)
            )
            print(f"{WHITE}{y_label}{RESET}{line_str}")

        # Draw X Axis line
        axis_line = "      └" + ("─" * width)
        print(f"{WHITE}{axis_line}{RESET}")

        # Draw X Axis labels
        x_min_str = f"{min_x:.1f}"
        x_max_str = f"{max_x:.1f}"
        spacing = width - len(x_min_str) - len(x_max_str)
        print("       " + x_min_str + (" " * max(0, spacing)) + x_max_str)
        print(f"       {DIM}X: {self.aes.x} (wt)  →{RESET}")

        # Render Legend if color aesthetic mapped
        if color_map:
            print(f"\n{BOLD}Legend ({self.aes.color}):{RESET}", end=" ")
            for key, col in color_map.items():
                print(f"{col}● {key}{RESET}  ", end="")
            print()


def generate_mtcars_mock() -> List[Dict[str, Any]]:
    """Simulates R's classic 'mtcars' dataset (wt, mpg, cyl, hp)."""
    return [
        {"model": "Mazda RX4",         "wt": 2.62, "mpg": 21.0, "cyl": 6, "hp": 110},
        {"model": "Mazda RX4 Wag",     "wt": 2.87, "mpg": 21.0, "cyl": 6, "hp": 110},
        {"model": "Datsun 710",        "wt": 2.32, "mpg": 22.8, "cyl": 4, "hp": 93},
        {"model": "Hornet 4 Drive",    "wt": 3.21, "mpg": 21.4, "cyl": 6, "hp": 110},
        {"model": "Hornet Sportabout", "wt": 3.44, "mpg": 18.7, "cyl": 8, "hp": 175},
        {"model": "Valiant",           "wt": 3.46, "mpg": 18.1, "cyl": 6, "hp": 105},
        {"model": "Duster 360",        "wt": 3.57, "mpg": 14.3, "cyl": 8, "hp": 245},
        {"model": "Merc 240D",         "wt": 3.19, "mpg": 24.4, "cyl": 4, "hp": 62},
        {"model": "Merc 230",          "wt": 3.15, "mpg": 22.8, "cyl": 4, "hp": 95},
        {"model": "Merc 280",          "wt": 3.44, "mpg": 19.2, "cyl": 6, "hp": 123},
        {"model": "Merc 450SE",        "wt": 4.07, "mpg": 16.4, "cyl": 8, "hp": 180},
        {"model": "Cadillac Fleetwood", "wt": 5.25, "mpg": 10.4, "cyl": 8, "hp": 205},
        {"model": "Lincoln Continental","wt": 5.42, "mpg": 10.4, "cyl": 8, "hp": 215},
        {"model": "Chrysler Imperial", "wt": 5.34, "mpg": 14.7, "cyl": 8, "hp": 230},
        {"model": "Fiat 128",          "wt": 2.20, "mpg": 32.4, "cyl": 4, "hp": 66},
        {"model": "Honda Civic",       "wt": 1.61, "mpg": 30.4, "cyl": 4, "hp": 52},
        {"model": "Toyota Corolla",    "wt": 1.83, "mpg": 33.9, "cyl": 4, "hp": 65},
        {"model": "Porsche 914-2",     "wt": 2.14, "mpg": 26.0, "cyl": 4, "hp": 91},
        {"model": "Lotus Europa",      "wt": 1.51, "mpg": 30.4, "cyl": 4, "hp": 113},
        {"model": "Ford Pantera L",    "wt": 3.17, "mpg": 15.8, "cyl": 8, "hp": 264},
        {"model": "Ferrari Dino",      "wt": 2.77, "mpg": 19.7, "cyl": 6, "hp": 175},
        {"model": "Volvo 142E",        "wt": 2.78, "mpg": 21.4, "cyl": 4, "hp": 109},
    ]


def main():
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")
    print(f"{BOLD}{WHITE} R LANG DEEP DIVE: MODUL 05 - GRAMMAR OF GRAPHICS (ggplot2 ARCHITECTURE) {RESET}")
    print(f"{BOLD}{MAGENTA}======================================================================{RESET}")

    # Step 1: Load Dataset
    data = generate_mtcars_mock()
    print(f"\n{GREEN}[✓] Data Loaded:{RESET} mtcars subset ({len(data)} observations)")

    # Step 2: Assemble ggplot declarative object pipeline
    # Equivalent to R:
    # ggplot(mtcars, aes(x = wt, y = mpg, color = factor(cyl))) +
    #   geom_point() +
    #   geom_smooth(method = "lm")
    p = GGPlot(
        data=data,
        aes=AestheticMapping(x="wt", y="mpg", color="cyl"),
        title="Fuel Economy vs Vehicle Weight by Engine Cylinders"
    )

    print(f"{GREEN}[✓] Constructing Grammar Layers:{RESET}")
    print(f"    • aes(x='wt', y='mpg', color='cyl')")
    print(f"    • + geom_point(shape='●')")
    print(f"    • + geom_smooth(method='linear_ols')")

    p = p + GeomPoint(shape="●")
    p = p + GeomSmooth(color=YELLOW)

    # Step 3: Render to ANSI terminal Canvas
    p.render(width=60, height=14)

    print(f"\n{BOLD}{GREEN}Pipeline Execution Completed Successfully.{RESET}\n")


if __name__ == "__main__":
    main()