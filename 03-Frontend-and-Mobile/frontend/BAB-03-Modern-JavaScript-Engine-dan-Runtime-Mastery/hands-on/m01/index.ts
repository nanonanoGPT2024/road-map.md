+─────────────────────────────────────────────────────────────────────────────────────────+
│                                V8 JIT COMPILATION PIPELINE                              │
│                                                                                         │
│  [Source Code]                                                                          │
│         │                                                                               │
│         ▼                                                                               │
│  +──────────────+      +──────────────+                                                 │
│  │ Scanner/Lexer│ ───> │ Parser (AST) │                                                 │
│  +──────────────+      +──────────────+                                                 │
│                               │                                                         │
│                               ▼                                                         │
│                      +──────────────────+                                               │
│                      │ Ignition Compiler│ <── [Bytecode Generator]                      │
│                      +──────────────────+                                               │
│                               │                                                         │
│                     ┌─────────┴─────────┐                                               │
│                     │                   ▼                                               │
│                     │          +──────────────────+                                     │
│                     │          │ Bytecode Stream  │ ───> Executed by Interpreter        │
│                     │          +──────────────────+                                     │
│                     │                   │                                               │
│                     │                   ▼                                               │
│                     │          +──────────────────+                                     │
│                     │          │ Feedback Vector  │ (Type feedback collected)           │
│                     │          +──────────────────+                                     │
│                     ▼                   │                                               │
│            +──────────────────+         │                                               │
│            │ Sparkplug (Fast) │         ▼                                               │
│            +──────────────────+   [ Is Hot & Stable? ]                                  │
│                     │                   │                                               │
│                     │                   ├─── YES ───> +─────────────────────────+       │
│                     │                   │             │ TurboFan (Optimizing)   │       │
│                     │                   │             +─────────────────────────+       │
│                     │                   │                          │                    │
│                     │                   │                          ▼                    │
│                     │                   │             +─────────────────────────+       │
│                     │                   │             │ Optimized Machine Code  │       │
│                     ▼                   │             +─────────────────────────+       │
│            +──────────────────+         │                          │                    │
│            │ Machine Execution│ <───────┘                          │                    │
│            +──────────────────+                                    │                    │
│                     ▲                                              │                    │
│                     │ (Bailout/Deopt)                              │                    │
│                     └──────────────────────────────────────────────┘                    │
│                          (Type mismatch triggered at runtime)                           │
+─────────────────────────────────────────────────────────────────────────────────────────+

+─────────────────────────────────────────────────────────────────────────────────────────+
│                       RUNTIME EVENT LOOP & CONCURRENCY MODEL                            │
│                                                                                         │
│   +─────────────────────────────+           +────────────────────────────────────────+  │
│   │        CALL STACK           │           │             MEMORY HEAP                │  │
│   │ [frame: renderChart()     ] │           │  +──────────────────────────────────+  │  │
│   │ [frame: calculateOffsets()] │           │  │ Young Gen (Nursery & Intermediate│  │  │
│   │ [frame: anonymous()       ] │           │  +──────────────────────────────────+  │  │
│   +─────────────────────────────+           │  │ Old Gen (Mark-Sweep-Compact)     │  │  │
│                  ▲                          │  +──────────────────────────────────+  │  │
│                  │                          +────────────────────────────────────────+  │
│                  │ (Pushes execution frames)                                            │
│                  │                                                                      │
│    ┌─────────────┴─────────────┐                                                        │
│    │     EVENT LOOP ENGINE     │                                                        │
│    └─────────────┬─────────────┘                                                        │
│                  │                                                                      │
│        Phase Check Routine:                                                             │
│        1. Run Callstack until empty                                                     │
│        2. Drain ALL Microtasks until completely empty                                   │
│        3. Check Render Pipeline opportunities (RAF -> Style -> Layout -> Paint)         │
│        4. Pick ONE Macrotask, execute, return to step 1                                 │
│                  │                                                                      │
│        ┌─────────┴──────────────┬────────────────────────┬───────────────────────┐      │
│        ▼                        ▼                        ▼                       ▼      │
│  +───────────────+      +───────────────+        +───────────────+       +────────────+ │
│  │  Microtasks   │      │ Render Steps  │        │  Macrotasks   │       │ Background │ │
│  ├───────────────┤      ├───────────────┤        ├───────────────┤       ├────────────┤ │
│  │ Promise Jobs  │      │ RAF Callbacks │        │ setTimeout    │       │ Web Worker │ │
│  │ MutationObs.  │      │ Style Calc    │        │ setInterval   │       │ Worklets   │ │
│  │ queueMicrotask│      │ Layout/Paint  │        │ I/O / Events  │       │ I/O Thread │ │
│  +───────────────+      +───────────────+        +───────────────+       +────────────+ │
+─────────────────────────────────────────────────────────────────────────────────────────+
