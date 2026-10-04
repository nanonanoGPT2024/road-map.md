ANGULAR SSR & HYDRATION PIPELINE
                                      
  USER / BOT                                 EDGE / NODE.JS (SERVER)                      CLIENT BROWSER (V8)
      │                                                │                                           │
  1.  │─── HTTP GET /products/42 ─────────────────────>│                                           │
      │                                                │                                           │
      │                                    ┌───────────────────────┐                               │
      │                                    │ Express Engine Entry  │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │  Angular CommonEngine │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │  Execute AppServer    │                               │
      │                                    │  Bootstrap Tree       │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │ HTTP Client Intercept │                               │
      │                                    │ & Fetch Product Data  │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │ TransferState Store   │                               │
      │                                    │ Serialized in Script  │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
      │                                    ┌───────────▼───────────┐                               │
      │                                    │ Render to Static HTML │                               │
      │                                    └───────────┬───────────┘                               │
      │                                                │                                           │
  2.  │<── Fully Rendered HTML + Inlined TransferState ┼──────────────────────────────────────────>│ (Cache/Read)
      │    (First Contentful Paint Achieved Here!)     │                                           │
      │                                                                                            │
  3.  │─── Browser parses HTML & paints UI immediately ───────────────────────────────────────────>│ (Paint UI)
      │                                                                                            │
  4.  │─── Browser requests JS Bundles (main.js, chunk.js) ────────────────────────────────────────>│ (Load JS)
      │                                                                                            │
      │                                                                                ┌───────────▼───────────┐
      │                                                                                │ Angular Bootstrap     │
      │                                                                                │ (Client Application)  │
      │                                                                                └───────────┬───────────┘
      │                                                                                            │
      │                                                                                ┌───────────▼───────────┐
      │                                                                                │ Non-Destructive       │
      │                                                                                │ Hydration Protocol    │
      │                                                                                └───────────┬───────────┘
      │                                                                                            │
      │                                                                                ┌───────────▼───────────┐
      │                                                                                │ Claim existing DOM;   │
      │                                                                                │ Consume TransferState;│
      │                                                                                │ Attach event listeners│
      │                                                                                └───────────┬───────────┘
      │                                                                                            │
  5.  │<── Application fully interactive (INP / TTI optimized) ────────────────────────────────────┘
