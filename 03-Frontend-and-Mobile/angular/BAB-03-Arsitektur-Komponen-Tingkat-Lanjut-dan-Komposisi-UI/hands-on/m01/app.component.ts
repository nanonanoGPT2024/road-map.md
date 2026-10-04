+---------------------------------------------------------------------------------------+
| FASE 1: TEMPLATE DECLARATION & PROJECTION RESOLUTION                                  |
|                                                                                       |
|  Parent Template                                                                      |
|  +---------------------------------------------------------------------------------+  |
|  | <app-modal>                                                                     |  |
|  |   <!-- Transcluded via CSS Selector Slot -->                                    |  |
|  |   <div modal-header>Header Content</div>                                        |  |
|  |                                                                                 |  |
|  |   <!-- Transcluded via ngProjectAs Dynamic Mapping -->                          |  |
|  |   <ng-container ngProjectAs="modal-body">                                       |  |
|  |     <ng-template #dynamicTpl let-data="item">                                   |  |
|  |        <span>Item Value: {{ data.name }}</span>                                 |  |
|  |     </ng-template>                                                              |  |
|  |   </ng-container>                                                               |  |
|  | </app-modal>                                                                    |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 2: INTERNAL RUNTIME EVALUATION (Ivy Engine)                                     |
|                                                                                       |
|   AppModalComponent (TView / LView Structure)                                         |
|   +-------------------------------------------------------------------------------+   |
|   | Host Node: <app-modal>                                                        |   |
|   |                                                                               |   |
|   | 1. Evaluasi Slots:                                                            |   |
|   |    <header><ng-content select="[modal-header]"></ng-content></header>         |   |
|   |                                                                               |   |
|   | 2. Deteksi Signal Queries:                                                    |   |
|   |    tplSignal = contentChild.required<TemplateRef<any>>('dynamicTpl');         |   |
|   |    containerSignal = viewChild.required('targetAnchor', {read: ViewContainerRef});|
|   |                                                                               |   |
|   | 3. Directive Composition Assembly (hostDirectives):                           |   |
|   |    HostBindings -> CdkTrapFocus -> AriaDescribedByDirective                  |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| FASE 3: DYNAMIC EMBEDDING & INSTANTIATION                                             |
|                                                                                       |
|  +----------------------------------+        Instantiate Embedded View                |
|  | TemplateRef<ModalContext<T>>     | -------------------------------------+          |
|  +----------------------------------+                                      |          |
|                                                                            v          |
|  +----------------------------------+   Insert View    +----------------------------+ |
|  | ViewContainerRef                 | <--------------- | EmbeddedViewRef<T>         | |
|  | (Structural Insertion Anchor)    |                  | LView Data Array:          | |
|  +----------------------------------+                  | - Context: { item: data }  | |
|                                                        | - Root Nodes: [span, text] | |
|                                                        +----------------------------+ |
|                                                                                       |
|  Angular Change Detection Pipeline Triggered via Microtask Queue                      |
|  DOM di-update tanpa bypass Change Detection Root                                     |
+---------------------------------------------------------------------------------------+
