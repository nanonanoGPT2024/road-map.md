+---------------------------------------------------------------------------------------+
|                                    APPLICATION LAYER                                  |
|                                                                                       |
|  [ WorkRequest ] -----> [ WorkManager.getInstance() ]                                 |
|   (Constraints, Data)              |                                                  |
+------------------------------------|--------------------------------------------------+
                                     | enqueue()
                                     v
+---------------------------------------------------------------------------------------+
|                                  WORKMANAGER CORE                                     |
|                                                                                       |
|  +--------------------+       Write Transaction        +---------------------------+  |
|  | WorkContinuation / | -----------------------------> | WorkDatabase (Room/SQLite)|  |
|  | Schedulers Engine  |                                | Stores: State, Worker,    |  |
|  +--------------------+                                | InputData, Constraints    |  |
|           |                                            +---------------------------+  |
|           | Evaluate Device API Level & State                        |                |
|           v                                                          v                |
+-----------|----------------------------------------------------------|----------------+
            |                                                          | Read Specs
            v                                                          v
+---------------------------------------------------------------------------------------+
|                              OS SCHEDULING SUBSYSTEM                                  |
|                                                                                       |
|   API >= 23:                                                                          |
|   +-------------------------------------------------------------------------------+   |
|   | JobScheduler.schedule()  --> System JobService Proxy                          |   |
|   +-------------------------------------------------------------------------------+   |
|                                                                                       |
|   API < 23 (Fallback Lifecycle):                                                      |
|   +-------------------------------------------------------------------------------+   |
|   | AlarmManager + BroadcastReceiver (Reschedule via System Alarm)                |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
                                     |
                                     | Trigger based on Constraints
                                     v
+---------------------------------------------------------------------------------------+
|                            EXECUTION LAYER (Runtime)                                  |
|                                                                                       |
|  [ System Job/Intent ] ---> [ androidx.work.impl.background.systemjob.SystemJobService]
|                                    |                                                  |
|                                    v                                                  |
|                      [ androidx.work.impl.Processor ]                                 |
|                                    |                                                  |
|                 +------------------+------------------+                               |
|                 | (Assisted Injection / WorkerFactory)|                               |
|                 v                                     v                               |
|       [ Custom Worker Thread ]             [ CoroutineWorker Scope ]                  |
|                 |                                     |                               |
|                 v                                     v                               |
|          doWork(): Result                      doWork(): Result                       |
|                 \                                     /                               |
|                  +-----------------+-----------------+                                |
|                                    |                                                  |
|                                    v                                                  |
|           Persist SUCCESS / RETRY / FAILURE ke WorkDatabase                           |
+---------------------------------------------------------------------------------------+
