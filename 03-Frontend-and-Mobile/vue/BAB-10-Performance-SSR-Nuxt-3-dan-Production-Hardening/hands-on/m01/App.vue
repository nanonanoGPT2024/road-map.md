[ BROWSER CLIENT ]                                            [ NITRO ENGINE / SERVER ]
       |                                                                 |
       | 1. HTTP GET /products/sku-992                                    |
       |---------------------------------------------------------------->|
       |                                                                 | 2. Route Rules Check
       |                                                                 |    (SWR, ISR, SSR, Proxy)
       |                                                                 | 3. H3 EventContext Init
       |                                                                 |    (AsyncLocalStorage)
       |                                                                 | 4. Vue SSR App Creation
       |                                                                 |    (createSSRApp per request)
       |                                                                 | 5. Router & Middleware
       |                                                                 | 6. Setup Scripts Execution
       |                                                                 |    - useAsyncData / $fetch
       |                                                                 |    - Upstream API Calling
       |                                                                 | 7. SSR Render to String
       |                                                                 |    (renderToString(app))
       |                                                                 | 8. State Serialization
       |                                                                 |    (devalue -> <script id="__NUXT_DATA__">)
       |                                                                 | 9. Security Headers Injected
       |                                                                 |    (CSP Nonce, HSTS, CORS)
       | 10. HTTP 200 OK (Stream HTML + Inlined Critical CSS + Payload)  |
       |<----------------------------------------------------------------|
       |                                                                 
[ BROWSER DOM ENGINE ]                                                   
       |                                                                 
  11. First Contentful Paint (FCP) - Browser parse HTML & CSS            
  12. Parse Inlined State Payload (__NUXT_DATA__)                        
  13. Parallel Fetch: Asynchronous JS Chunks (Vite Entrypoint)           
  14. Execute Client App Initializer                                     
  15. Vue Hydration Algorithm:                                           
      +-------------------------------------------------------+          
      | VNode Client Tree matched against Real DOM Node Tree  |          
      | Event Listeners attached (v-on:click, inputs)         |          
      | Reactive Effects Triggered                            |          
      +-------------------------------------------------------+          
  16. Time to Interactive (TTI) / Core Web Vitals Ready
