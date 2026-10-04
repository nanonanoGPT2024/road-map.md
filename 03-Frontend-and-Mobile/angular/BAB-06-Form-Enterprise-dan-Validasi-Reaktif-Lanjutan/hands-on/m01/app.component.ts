+---------------------------------------------------------------------------------------------------+
| USER INTERACTION LAYER (DOM / Component Template)                                                |
|   User types: "ID-9921-X" -> triggers (input) event                                               |
+---------------------------------------------------------------------------------------------------+
                                            |
                                            v (View-to-Model sync)
+---------------------------------------------------------------------------------------------------+
| CONTROL VALUE ACCESSOR (CVA BRIDGE)                                                               |
|   1. Captures native event -> calls registered 'onChange(value)' callback                        |
|   2. Updates internal component rendering state                                                  |
+---------------------------------------------------------------------------------------------------+
                                            |
                                            v (Pushes value to FormControl)
+---------------------------------------------------------------------------------------------------+
| FORMCONTROL ABSTRACT NODE                                                                         |
|   1. Sets 'dirty = true', 'touched = true' (if blur)                                              |
|   2. Updates 'rawValue' & emits valueChanges stream                                               |
|   3. Status transition: STATUS = 'PENDING'                                                        |
+---------------------------------------------------------------------------------------------------+
                                            |
                                            +---------------------------------------+
                                            |                                       |
                                            v (Step A: Synchronous)                 v (Step B: Asynchronous)
+-----------------------------------------------+   +-----------------------------------------------+
| SYNCHRONOUS VALIDATORS                        |   | ASYNCHRONOUS VALIDATORS PIPELINE              |
| - RequiredValidator                           |   | - Debounce Input (e.g., 300ms)                |
| - RegexPatternValidator                       |   | - DistinctUntilChanged Filter                 |
| - Custom Cross-field Sync Check               |   | - switchMap to Backend API / gRPC-Web Client  |
+-----------------------------------------------+   +-----------------------------------------------+
      |                                                   |
      | Pass: null                                        | Returns: Observable<{ asyncError: true } | null>
      | Fail: { invalidFormat: true }                     | (Cancels previous pending HTTP via switchMap)
      |                                                   |
      +---------------------+-----------------------------+
                            |
                            v
+---------------------------------------------------------------------------------------------------+
| STATUS RESOLUTION ENGINE                                                                          |
|   If any Sync fails    -> STATUS = 'INVALID' (Short-circuit async validation)                     |
|   If Sync passes       -> Wait for Async stream resolution                                        |
|   If Async completes   -> STATUS = 'VALID' OR 'INVALID'                                           |
|   Emits statusChanges stream                                                                      |
+---------------------------------------------------------------------------------------------------+
                            |
                            v
+---------------------------------------------------------------------------------------------------+
| ROOT FORM NOTIFICATION & BUBBLING                                                                 |
|   Parent FormGroups & FormArrays recalculate validity based on leaf-node updates                  |
|   Triggers Angular OnPush Change Detection via Signal / MarkForCheck                             |
+---------------------------------------------------------------------------------------------------+
