+---------------------------------------------------------------------------------------+
|                                    APPLICATION ROOT                                   |
|   +-------------------------------------------------------------------------------+   |
|   |                          Root Auth & Session State                             |   |
|   |   (SignalStore / Signal Service: providedIn: 'root', Persisted across routes)  |   |
|   +---------------------------------------+---------------------------------------+   |
+-------------------------------------------|-------------------------------------------+
                                            | (Read-Only Signal Propagation)
                                            v
+---------------------------------------------------------------------------------------+
|                    ROUTE INJECTOR: /orders (Lazy-Loaded Feature)                      |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                            OrderDomainFacadeStore                             |   |
|   |   - Lifecycle: Instantiated at Route Activation, GC'd at Route Exit           |   |
|   |   - State: activeOrders[], filterCriteria, loadingState, pagination           |   |
|   |   - Extensions: withEntities(), withMethods(), withHooks()                     |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|             +-----------------------------+-----------------------------+             |
|             | (Provides Isolated Context)                               |             |
|             v                                                           v             |
|   +------------------------------------+      +------------------------------------+  |
|   | COMPONENT TREE: OrderTableComponent|      | COMPONENT TREE: OrderFilterDrawer  |  |
|   | (Node Injector Provider)           |      | (Node Injector Provider)           |  |
|   |                                    |      |                                    |  |
|   | +--------------------------------+ |      | +--------------------------------+ |  |
|   | | TableTransientStore            | |      | | DrawerTransientStore           | |  |
|   | | - selectedRowIds: Set<string>  | |      | | - formDraftState               | |  |
|   | | - columnWidths: Map<string,num>| |      | | - isDirty: boolean             | |  |
|   | +--------------------------------+ |      | +--------------------------------+ |  |
|   | Automatically GC'd on ngOnDestroy  |      | Automatically GC'd on close/exit   |  |
|   +------------------------------------+      +------------------------------------+  |
+---------------------------------------------------------------------------------------+
