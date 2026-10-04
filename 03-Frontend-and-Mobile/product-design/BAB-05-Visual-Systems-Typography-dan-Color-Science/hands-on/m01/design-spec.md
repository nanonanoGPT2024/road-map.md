+---------------------------------------------------------------------------------------+
|                                PRIMITIVE TOKENS LAYER                                 |
|                                                                                       |
|   [ CIE XYZ D65 ] ---> [ Oklab Transform ] ---> [ Polar Form: Oklch Engine ]          |
|   L: 0.0 - 1.0          a: -0.4 - +0.4          Lightness (0-100%)                    |
|                         b: -0.4 - +0.4          Chroma    (0-0.37+)                   |
|                                                 Hue       (0-360deg)                  |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                SEMANTIC MAPPING LAYER                                 |
|                                                                                       |
|   Light Context (Base L=0.98)                  Dark Context (Base L=0.15)             |
|   APCA Contrast Target: Lc >= 75              APCA Contrast Target: Lc >= -75         |
|                                                                                       |
|   --sys-color-surface: oklch(0.98 0.01 240)   --sys-color-surface: oklch(0.15 0.02 240)
|   --sys-color-primary: oklch(0.55 0.22 260)   --sys-color-primary: oklch(0.75 0.18 260)
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                TYPOGRAPHY ENGINE LAYER                                |
|                                                                                       |
|   Modular Scale: r = 1.25 (Major Third)       Fluid Calculus:                         |
|   Base Type: 1rem (16px)                      clamp(min, preferred, max)              |
|   Variable Font Engine: Optical Axis Adjust   Metric Overrides (ascent, descent, gap) |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                               COMPONENT CONSUMPTION                                   |
|                                                                                       |
|   .c-card {                                                                           |
|     background-color: var(--sys-color-surface);                                       |
|     font-size: var(--sys-typescale-body-fluid);                                       |
|     color: var(--sys-color-on-surface);                                               |
|   }                                                                                   |
+---------------------------------------------------------------------------------------+
