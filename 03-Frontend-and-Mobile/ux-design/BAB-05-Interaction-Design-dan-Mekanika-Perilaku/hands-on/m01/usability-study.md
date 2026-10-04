+-------------------------------------------------------------------------------------------------------+
|                                ARSITEKTUR RUNTIME INTERACTION DESIGN                                  |
+-------------------------------------------------------------------------------------------------------+
|                                                                                                       |
|  [ USER INPUT ] ---> (Pointer / Keyboard / Screen Reader)                                             |
|        |                                                                                              |
|        v                                                                                              |
|  +-------------------+        +--------------------------------------------------------------------+  |
|  | TRIGGER DETECTION |        | DAN SAFFER INTERACTION LIFECYCLE                                    |  |
|  +-------------------+        |                                                                    |  |
|        | (Event E)            |  [Trigger]                                                         |  |
|        v                      |     |                                                              |  |
|  +-------------------+        |     v                                                              |  |
|  | FINITE STATE      |------->|  [Rules Execution] <----+                                          |  |
|  | MACHINE (FSM)     |        |     |                   |                                          |  |
|  +-------------------+        |     v                   | Loops / Dynamic Modes                    |  |
|        | (Next State)         |  [Feedback Generation]  |                                          |  |
|        |                      |     |                   |                                          |  |
|        |                      |     v                   |                                          |  |
|        |                      |  [Loops / Modes] -------+                                          |  |
|        v                      +--------------------------------------------------------------------+  |
|  +-----------------------------------+                                                                |
|  | KINEMATIC RUNTIME / SPRING ENGINE | (requestAnimationFrame Loop)                                    |
|  +-----------------------------------+                                                                |
|        |                                                                                              |
|        +-----------------------------------+                                                          |
|        | (Transforms: translate3d, scale)  | (A11y Mutation / Live Region)                            |
|        v                                   v                                                          |
|  +-----------------------------+     +-------------------------------+                                |
|  | COMPOSITOR THREAD (GPU)     |     | ACCESSIBILITY TREE (AXTree)   |                                |
|  | - Direct Mutation           |     | - ARIA Live Announcements     |                                |
|  | - 60/120 FPS Guaranteed     |     | - Focus Management            |                                |
|  +-----------------------------+     +-------------------------------+                                |
|                                                                                                       |
+-------------------------------------------------------------------------------------------------------+
