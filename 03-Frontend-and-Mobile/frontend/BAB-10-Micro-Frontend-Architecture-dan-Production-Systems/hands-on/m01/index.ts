+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE MFE RUNTIME TOPOLOGY                                 |
+----------------------------------------------------------------------------------------------------+
                                               |
                                     [ Client Browser Hits URL ]
                                               |
                                               v
+----------------------------------------------------------------------------------------------------+
| Edge / Cloudflare Workers / Fastly (CDN & Ingress)                                                 |
| - Inspects Request, injects Edge-Side Dynamic Config (Remote Manifest URLs based on Tenant/Region)  |
+----------------------------------------------------------------------------------------------------+
       |                                       |                                      |
       | Fetches Shell Entry                   | Fetches Manifest                     | Healthchecks
       v                                       v                                      v
+------------------+                 +--------------------+                 +--------------------+
|  Host Shell App  |                 | Dynamic Discovery  |                 | Remote Service C   |
| (Root Orchestrator|                | Service (Registry) |                 | (e.g. Checkout)    |
+------------------+                 +--------------------+                 +--------------------+
       |                                       |                                      |
       +=======================================+======================================+
                                               |
                                               v
+----------------------------------------------------------------------------------------------------+
| BROWSER RUNTIME CONTEXT (Memory Space)                                                             |
|                                                                                                    |
|  +----------------------------------------------------------------------------------------------+  |
|  | HOST SHELL CONTAINER                                                                         |  |
|  |  - MicroFrontend Orchestrator (Router, Dynamic Loader)                                        |  |
|  |  - Global Event Bus / Typed Message Broker (RxJS, EventTarget)                               |  |
|  |  - Error Boundary Root & Performance Telemetry Collector                                     |  |
|  +----------------------------------------------------------------------------------------------+  |
|             |                                                  |                                   |
|             | Loads via Module Federation                      | Loads with Sandboxing             |
|             v                                                  v                                   |
|  +-------------------------------------+            +-------------------------------------+        |
|  | REMOTE A: CATALOG DOMAIN            |            | REMOTE B: ACCOUNT DOMAIN            |        |
|  | - React 18 Engine                   |            | - Vue 3 Engine                      |        |
|  | - Shadow DOM (Scoped Styles)        |            | - Scoped Custom Element Target      |        |
|  | - Shared React/ReactDOM (Singleton)|            | - Separate Dependency Graph         |        |
|  +-------------------------------------+            +-------------------------------------+        |
|             |                                                  |                                   |
|             +-------------------------+------------------------+                                   |
|                                       | (Zero Global State Coupling)                               |
|                                       v                                                            |
|  +----------------------------------------------------------------------------------------------+  |
|  | BROWSER STORAGE & INFRASTRUCTURE                                                             |  |
|  |  - Shared Storage (IndexedDB, LocalStorage via Scoped Keys)                                  |  |
|  |  - Session Context / HTTP Only Cookies                                                       |  |
|  +----------------------------------------------------------------------------------------------+  |
+----------------------------------------------------------------------------------------------------+
