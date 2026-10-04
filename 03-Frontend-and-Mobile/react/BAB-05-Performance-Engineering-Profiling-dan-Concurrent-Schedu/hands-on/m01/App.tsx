+--------------------------------------------------------------------------------------------------+
|                                    EVENT LOOP & USER INTERACTION                                 |
+--------------------------------------------------------------------------------------------------+
          | (User Type: Urgent)                                   | (Data Filter: Transition)
          v                                                       v
  [ Discrete Event ]                                     [ Transition Event ]
  (SyncLane: Priority 1)                             (TransitionLane: Priority 64-1024)
          |                                                       |
          +---------------------------+---------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------------------------+
|                                   REACT SCHEDULER ENGINE                                         |
|  - Min-Heap Priority Queue (taskQueue vs timerQueue)                                             |
|  - Cooperative Time-Slicing via MessageChannel (5ms default slice budget)                        |
+--------------------------------------------------------------------------------------------------+
                                      |
                           Work Request Scheduled
                                      v
+--------------------------------------------------------------------------------------------------+
|                            RENDER PHASE (Interruptible / Non-Blocking)                           |
|                                                                                                  |
|   Current Fiber Tree                        Work-in-Progress (WIP) Fiber Tree                    |
|   +------------------+                      +------------------+                                 |
|   | Fiber (Root)     |                      | Fiber (Root-WIP) |                                 |
|   +------------------+                      +------------------+                                 |
|            |                                         |                                           |
|            v                                         v                                           |
|   +------------------+   Alternate Pointer  +------------------+                                 |
|   | Fiber (Parent)   |<====================>| Fiber (Parent-WIP|                                 |
|   +------------------+                      +------------------+                                 |
|            |                                         | (Yield if frame budget expired > 5ms)     |
|            v                                         v                                           |
|   +------------------+                      +------------------+                                 |
|   | Fiber (Child)    |                      | Fiber (Child-WIP)|                                 |
|   +------------------+                      +------------------+                                 |
|                                                                                                  |
|   [Scheduler Interrupt Detection]:                                                               |
|   if (navigator.scheduling.isInputPending() || performance.now() >= deadline)                   |
|       => Yield control back to Host Browser Main Thread via MessageChannel postMessage           |
+--------------------------------------------------------------------------------------------------+
                                      |
                               Work Complete
                                      v
+--------------------------------------------------------------------------------------------------+
|                              COMMIT PHASE (Strictly Synchronous)                                 |
|                                                                                                  |
|   1. Before Mutation: Mengambil snapshot DOM (getSnapshotBeforeUpdate)                           |
|   2. Mutation: Swap root pointer (current = workInProgress), Mutasi DOM Host nyata               |
|   3. Layout: Eksekusi useLayoutEffect synchronous (DOM up-to-date, paint belum terjadi)          |
+--------------------------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------------------------+
|                                  BROWSER RENDER PIPELINE                                         |
|            Recalculate Style ---> Layout / Reflow ---> Paint ---> Composite Layers               |
+--------------------------------------------------------------------------------------------------+
                                      |
                                      v
+--------------------------------------------------------------------------------------------------+
|                                     POST-PAINT PHASE                                             |
|                     Passive Effects Executed (useEffect asynchronous batch)                      |
+--------------------------------------------------------------------------------------------------+
