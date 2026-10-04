[Design Source (Figma Tokens / JSON W3C Spec)]
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                 TOKEN TRANSFORMATION PIPELINE               │
│                   (Style Dictionary Engine)                 │
│                                                             │
│   Layer 1: Global Primitives (core.json)                    │
│   Layer 2: Semantic Intent (semantic-light.json, dark.json) │
│   Layer 3: Component Token Mapping                          │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
    [Format: CSS Variables]       [Format: TypeScript AST]
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│  CSS Custom Properties File   │ │ Strict Typings & Theme    │
│  :root { --color-bg: ... }    │ │ type ColorTokens = '...'  │
└───────────────┬───────────────┘ └───────────┬───────────────┘
                │                             │
                └──────────────┬──────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               ZERO-RUNTIME / COMPILE-TIME ENGINE            │
│               (Vanilla Extract / CSS Modules)               │
│                                                             │
│  * Type-checking nama variabel vs nilai token               │
│  * Hashing selektor deterministik                           │
│  * Pengelompokan ke dalam @layer cascade                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
               [Vite / Webpack / Rollup Plugin]
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼
┌───────────────────────────┐             ┌───────────────────┐
│     Critical CSS Chunk    │             │ Defer CSS Chunks  │
│     (Injected into HTML)  │             │ (Loaded on demand)│
└─────────┬─────────────────┘             └─────────┬─────────┘
          │                                         │
          └────────────────────┬────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                       BROWSER PIPELINE                      │
│                                                             │
│ 1. Parse HTML ───► DOM Tree                                 │
│ 2. Parse CSS  ───► CSSOM Tree (Constructed Stylesheet)      │
│ 3. Match Specificity via @layer resolution                 │
│ 4. Compute Dynamic Values (resolve var(--...))              │
│ 5. Tree Synthesis ───► Render Tree                          │
│ 6. Layout (Reflow) ──► Paint ──► Composite                  │
└─────────────────────────────────────────────────────────────┘
