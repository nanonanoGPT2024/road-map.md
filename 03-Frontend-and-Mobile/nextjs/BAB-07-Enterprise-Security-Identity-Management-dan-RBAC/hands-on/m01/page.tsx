+----------------------------------------------------------------------------------------------------+
|                                      NEXT.JS RUNTIME TOPOLOGY                                      |
+----------------------------------------------------------------------------------------------------+
 [BROWSER]                                                                                            
     │                                                                                                
     │ 1. Request with Encrypted Session Cookie (__Host-auth-token)                                   
     ▼                                                                                                
 ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐ 
 │ 2. EDGE MIDDLEWARE (middleware.ts)                                                               │ 
 │    ├── A. Web Crypto API: Decrypt & Verify JWE/JWS Signature via In-Memory JWKS Cache            │ 
 │    ├── B. Parse Claims: { sub, tenantId, roles: ['AUDITOR'] }                                    │ 
 │    ├── C. URL Path Inspection: Matches '/admin/*' against claims.roles                          │ 
 │    │       └── DENIED: Rewrite to /403 or Redirect to /login                                     │ 
 │    └── D. PASSED: Inject Identity Headers (x-user-id, x-tenant-id) via request mutation         │ 
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘ 
     │                                                                                                
     │ 3. Forward to Target Server Boundary (Upstream Internal Transfer)                             
     ▼                                                                                                
 ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐ 
 │ 4. SERVER RUNTIME (RSC / SERVER ACTIONS / ROUTE HANDLERS)                                        │ 
 │    ├── A. Layer 1: Cryptographic Validation Check                                               │ 
 │    │       └── Do NOT trust 'x-user-id' from headers blindly (Prevent Header Spoofing via        │ 
 │    │           direct client requests). Read and decrypt cookies directly on the server.         │ 
 │    ├── B. Layer 2: Domain Context Hydration                                                      │ 
 │    │       └── React 'cache()' memoizes getSession() per request execution graph                 │ 
 │    ├── C. Layer 3: Enterprise RBAC/ABAC Policy Engine Execution                                  │ 
 │    │       └── Evaluate: PolicyEngine.can(user, 'read:financial_records', targetResource)       │ 
 │    └── D. Layer 4: Data Layer Execution                                                          │ 
 │            └── Query Database via Multi-Tenant Row-Level Security (RLS) Parameter                │ 
 └──────────────────────────────────────────────────────────────────────────────────────────────────┘ 
     │                                                                                                
     │ 5. Render Secure RSC Payload / Return JSON Action Response                                    
     ▼                                                                                                
 [BROWSER UI]
