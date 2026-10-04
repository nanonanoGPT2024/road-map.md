[ Angular Service / Feature Component ]
                   │
                   ▼  (Invokes http.get / http.post)
       ┌────────────────────────┐
       │   HttpClient Engine    │
       └────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│           FUNCTIONAL INTERCEPTORS PIPELINE             │
│                                                        │
│  [ Interceptor 1: Correlation & Tracing ID ]           │
│        │  Injects 'X-Correlation-ID'                   │
│        ▼                                               │
│  [ Interceptor 2: Authentication (Bearer Token) ]      │
│        │  Injects Authorization Header                 │
│        ▼                                               │
│  [ Interceptor 3: Resilience & Circuit Breaker ]       │
│        │  Evaluates Circuit State: OPEN / HALF / CLOSE │
│        ▼                                               │
│  [ Interceptor 4: HttpCaching (Optional Bypass) ]      │
└────────────────────────────────────────────────────────┘
                   │
                   ▼ (Forwarded via HttpBackend)
       ┌────────────────────────┐
       │  Angular HttpBackend   │ (Translates to native fetch/XHR)
       └────────────────────────┘
                   │
                   ▼
      ═════════════════════════════  [ Physical Network Boundary ]
             Remote Server
      ═════════════════════════════  [ Physical Network Boundary ]
                   │
                   ▼ (Raw HTTP Response / Error 401/500/Timeout)
       ┌────────────────────────┐
       │  Angular HttpBackend   │
       └────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│         RESPONSE PIPELINE (Unwinding Interceptors)     │
│                                                        │
│  [ Error Evaluator & Circuit Breaker State Recorder ]  │
│        │                                               │
│        ├─── (HTTP 200 OK) ──► Record Success in Breaker│
│        │                                               │
│        └─── (HTTP 401 Unauthorized)                    │
│                 │                                      │
│                 ▼                                      │
│      [ Token Refresh Mutex Lock ]                      │
│                 │                                      │
│         Is Refreshing?                                 │
│         ├── NO  ──► Launch Refresh Token Request       │
│         │           Block Subsequent 401 Requests      │
│         │           On Success: Replay Pending Reqs    │
│         │                                              │
│         └── YES ──► Queue in Waiter BehaviorSubject    │
│                     Wait for New Token & Re-issue      │
└────────────────────────────────────────────────────────┘
                   │
                   ▼
       [ Final Domain Observable ] ──► (Component Subscription)
