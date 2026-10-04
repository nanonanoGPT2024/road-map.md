+-----------------------------------------------------------------------------------------+
|                                    COMPONENT INSTANCE                                   |
|                                                                                         |
|  setup() Execution Phase                                                                |
|  +-----------------------------------------------------------------------------------+  |
|  | currentInstance = this;                                                           |  |
|  | activeEffectScope = this.scope;                                                   |  |
|  |                                                                                   |  |
|  |  +-----------------------------------------------------------------------------+  |  |
|  |  | useFeatureComposable(paramSource)                                           |  |  |
|  |  |                                                                             |  |  |
|  |  |   1. Resolution: toValue(paramSource) -> Raw / Reactive Extraction         |  |  |
|  |  |                                                                             |  |  |
|  |  |   2. Instantiation:                                                         |  |  |
|  |  |      ref() / shallowRef() ───────► Target Memory Allocated                 |  |  |
|  |  |                                                                             |  |  |
|  |  |   3. Dependency Subscription:                                               |  |  |
|  |  |      watchEffect()                                                          |  |  |
|  |  |        │                                                                    |  |  |
|  |  |        ▼                                                                    |  |  |
|  |  |      track() Phase ──────────────► Add Dep to activeEffect (ReactiveEffect) |  |  |
|  |  |                                                                             |  |  |
|  |  |   4. Lifecycle Injection:                                                   |  |  |
|  |  |      onMounted() / onUnmounted() ──► Append to Component Hook Buffer        |  |  |
|  |  |                                                                             |  |  |
|  |  |   5. Scope Binding:                                                         |  |  |
|  |  |      Collect cleanups/effects ───► Component Scope Registry                |  |  |
|  |  +-----------------------------------------------------------------------------+  |  |
|  |                                                                                   |  |
|  | currentInstance = null;                                                           |  |
|  +-----------------------------------------------------------------------------------+  |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
                                           │
                                           │ Component Destroyed / Unmounted
                                           ▼
+-----------------------------------------------------------------------------------------+
|  EFFECT SCOPE DISPOSAL                                                                  |
|  instance.scope.stop()                                                                  |
|  ├── Stops all child ReactiveEffects (no more dirty triggers)                           |
|  ├── Executes all onScopeDispose() callbacks                                            |
|  └── Releases references to DOM listeners / Network sockets (GC Friendly)               |
+-----------------------------------------------------------------------------------------+
