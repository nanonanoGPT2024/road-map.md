+---------------------------------------------------------------------------------------+
| PHASE 1: DESIGN AUTHORING & EXTRACTION                                                |
|                                                                                       |
|  +--------------------+       REST API       +-------------------------------------+  |
|  | Figma Variables    | -------------------> | Extraction Engine (Node.js/TS CLI)  |  |
|  | - Primitives       |   (Personal Access   | - Normalisasi ke DTCG Format        |  |
|  | - Modes (Dark/Light|        Token)        | - Resolve Aliases & Groups          |  |
|  +--------------------+                      +-------------------------------------+  |
+------------------------------------------------------------------|--------------------+
                                                                   | Emit Raw JSON
+------------------------------------------------------------------v--------------------+
| PHASE 2: VALIDATION, CONTRACT INTEGRITY & TOKEN COMPILATION                           |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Token Repository (Git)                                                          |  |
|  |  ├── tokens/                                                                    |  |
|  |  │    ├── primitive/color.json                                                  |  |
|  |  │    ├── semantic/light.json & semantic/dark.json                              |  |
|  |  │    └── component/button.json                                                 |  |
|  |  └── schema/token.schema.json (Zod Engine Validator)                            |  |
|  +---------------------------------------------------------------------------------+  |
|                                          |                                            |
|                                          v                                            |
|  +---------------------------------------------------------------------------------+  |
|  | Style Dictionary v4 Compilation Engine (Custom Preprocessors, Transforms)       |  |
|  +---------------------------------------------------------------------------------+  |
|         |                        |                        |                |          |
+---------|------------------------|------------------------|----------------|----------+
          |                        |                        |                |
+---------v--------+      +--------v---------+     +--------v-------+  +-----v----------+
| PHASE 3: EMIT    |      |                  |     |                |  |                |
| Web Target       |      | TypeScript       |     | Android Target |  | iOS Target     |
|                  |      |                  |     |                |  |                |
| - tokens.css     |      | - tokens.d.ts    |     | - Color.kt     |  | - Color.swift  |
|   (:root,        |      | - tokens.esm.js  |     |   (Jetpack     |  |   (SwiftUI     |
|    [data-theme]) |      |   (Frozen Object)|     |    Compose)    |  |    ShapeStyle) |
+------------------+      +------------------+     +----------------+  +----------------+
