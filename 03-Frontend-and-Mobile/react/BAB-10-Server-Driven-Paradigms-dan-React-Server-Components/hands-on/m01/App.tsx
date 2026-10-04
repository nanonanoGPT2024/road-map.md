+-------------------------------------------------------------------------------------------------------+
|                                  BROWSER / RUNTIME ENVIRONMENT                                        |
+-------------------------------------------------------------------------------------------------------+
    |                                                                                               ^
    | 1. HTTP Request (Navigation / Action)                                                         |
    v                                                                                               |
+---------------------------------------------------------------------------------------------------|---+
|                                 EDGE / NODE.JS RUNTIME ENGINE                                     |   |
|                                                                                                   |   |
|  +---------------------------------------------------------------------------------------------+  |   |
|  | REACT COMPONENT GRAPH EXECUTION PIPELINE                                                    |  |   |
|  |                                                                                             |  |   |
|  |  [Root Layout (Server)]                                                                     |  |   |
|  |         |                                                                                   |  |   |
|  |         +---> Direct DB Access (e.g. pg / Prisma) ===> Await I/O Query                      |  |   |
|  |         |                                                                                   |  |   |
|  |         v                                                                                   |  |   |
|  |  [ProductDetail (Server)]                                                                   |  |   |
|  |         |                                                                                   |  |   |
|  |         +---> <Suspense fallback={<Skeleton />}>                                            |  |   |
|  |                    |                                                                        |  |   |
|  |                    +---> [Reviews (Async Server)] ===> Slow I/O Streaming Wait              |  |   |
|  |                    |                                                                        |  |   |
|  |                    v                                                                        |  |   |
|  |         +--- [AddToCartButton ('use client')]                                               |  |   |
|  +---------|-----------------------------------------------------------------------------------+  |   |
|            |                                                                                      |   |
|            v                                                                                      |   |
|  +---------------------------+       +------------------------------------+                       |   |
|  | Server Serializer Engine  |       | Client Component Bundler Manifest  |                       |   |
|  | (react-server-dom-webpack)|       | (Webpack / Turbopack Metadata)     |                       |   |
|  +---------------------------+       +------------------------------------+                       |   |
|            |                                           |                                          |   |
|            | 2. Serialize Server Tree to Stream        | Resolusi Module ID & File URL            |   |
|            |    Replace Client Comp with $L markers    |                                          |   |
|            v                                           v                                          |   |
|  +------------------------------------------------------------------------+                       |   |
|  | RSC STREAMING PAYLOAD ENCODER (Chunked HTTP Output)                    |                       |   |
|  | Format:                                                                |                       |   |
|  | 0:{"$@":["$L1"]}                                                       |                       |   |
|  | 1:I{"id":"./src/Button.client.tsx","chunks":["client1"],"name":"default"} |                   |   |
|  | 0:{"title":"GPU NVidia","action":"$L1"}                               |                       |   |
|  +------------------------------------------------------------------------+                       |   |
+---------------------------------------------------------------------------------------------------|---+
    |                                                                                               |
    | 3. Progressive HTTP Stream (Chunks transmitted over wire)                                     |
    v                                                                                               |
+---------------------------------------------------------------------------------------------------|---+
|                                  BROWSER RUNTIME PARSER & RECONCILER                              |   |
|                                                                                                   |   |
|  +-------------------------------------+      +------------------------------------------------+  |   |
|  | RSC Stream Reader / Deserializer    | ===> | React Fiber Reconciler                         |  |   |
|  | Parser reads payload chunks on-fly  |      | Dynamic reconciliation without destroying state|  |   |
|  +-------------------------------------+      +------------------------------------------------+  |   |
|                   |                                                  |                            |   |
|                   | Perlu Client Asset?                              v                            |   |
|                   +-------------------------> [ Fetch JS Chunks ] -> Hydrate Interactive Leaf Node|
+-------------------------------------------------------------------------------------------------------+
