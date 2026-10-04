[ Vue Single File Component (.vue Template) ]
                     |
                     v
+-------------------------------------------------------+
| COMPILER PHASE (@vue/compiler-core & compiler-dom)    |
|                                                       |
|  1. Lexer & Tokenizer                                 |
|     -> Parsing template string ke stream of tokens    |
|                                                       |
|  2. Parser AST (Abstract Syntax Tree Generation)      |
|     -> Konstruksi node hirarki (ElementNode, Root)    |
|                                                       |
|  3. Transform Engine (Static Analysis)                |
|     -> Hoisting node murni statis                     |
|     -> Bitwise Patch Flags assignment                 |
|     -> Block Tree structural boundary marking         |
|                                                       |
|  4. Code Generator                                    |
|     -> Menghasilkan JavaScript Render Function AST    |
|     -> Output: function render(_ctx, _cache) { ... }  |
+-------------------------------------------------------+
                     |
                     v
+-------------------------------------------------------+
| RUNTIME INITIALIZATION (@vue/runtime-core)            |
|                                                       |
|  1. Inisialisasi Reactive State via Proxy             |
|  2. Eksekusi Render Function di dalam Reactive Effect |
|  3. Output: Virtual DOM Tree (VNode Trees)            |
|     - Blok root menyimpan array `dynamicChildren`     |
+-------------------------------------------------------+
                     |
                     v
+-------------------------------------------------------+
| RENDERER MOUNT PHASE (@vue/runtime-dom)               |
|                                                       |
|  1. hostCreateElement() -> Native DOM nodes           |
|  2. Directive Hook Trigger: `created`, `beforeMount`  |
|  3. hostInsert() -> Menancapkan elemen ke DOM Tree    |
|  4. Directive Hook Trigger: `mounted`                 |
+-------------------------------------------------------+
                     |
           Reaktif State Berubah (Proxy Setter)
                     |
                     v
+-------------------------------------------------------+
| RUNTIME PATCH / DIFF PHASE (Optimized Diffing)        |
|                                                       |
|  1. Reactive Effect trigger rerender                  |
|  2. Runtime membaca array `dynamicChildren` (Block)   |
|  3. Skip structural diff untuk node statis            |
|  4. Evaluasi bitwise Patch Flags:                     |
|     - TEXT: Mutasi textContent saja                   |
|     - CLASS: Mutasi className saja                    |
|     - PROPS: Mutasi atribut spesifik via fast path    |
|  5. Directive Hook Trigger: `beforeUpdate`, `updated` |
|  6. Minimal browser repaint/reflow layout calculation |
+-------------------------------------------------------+
