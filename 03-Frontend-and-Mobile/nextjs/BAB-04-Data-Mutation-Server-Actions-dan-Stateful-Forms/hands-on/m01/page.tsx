+---------------------------------------------------------------------------------------------------+
| CLIENT BROWSER (Hydrated / Non-Hydrated DOM)                                                      |
+---------------------------------------------------------------------------------------------------+
  |
  | 1. User Menekan Submit (Event Dispatch / Native Submit)
  v
+---------------------------------------------------------------------------------------------------+
| React Runtime (useActionState & useOptimistic)                                                   |
| - Optimistic State dirender seketika ke UI (Rollback ready)                                       |
| - Pending State aktif via useFormStatus()                                                         |
+---------------------------------------------------------------------------------------------------+
  |
  | 2. HTTP POST Request
  |    Headers: 
  |      - Next-Action: <ACTION_ID_HASH>
  |      - Content-Type: multipart/form-data OR application/json
  |      - Accept: text/x-component (React Flight Stream)
  v
+===================================================================================================+
| NETWORK BOUNDARY                                                                                  |
+===================================================================================================+
  |
  | 3. Middleware Pipeline (Rate Limiting, Session Token Check)
  v
+---------------------------------------------------------------------------------------------------+
| NEXT.JS SERVER HOST (App Router Core)                                                            |
|                                                                                                   |
|  [Action Router Registry]                                                                         |
|         | Resolve Hash: <ACTION_ID_HASH> -> fn updateProfile(prevState, formData)                 |
|         v                                                                                         |
|  [Security & Context Barrier]                                                                     |
|         |-- Origin vs Host header check (CSRF Guard)                                              |
|         |-- Authentication context assertion (RBAC)                                               |
|         v                                                                                         |
|  [Zod Validation & Sanitization Engine]                                                           |
|         |                                                                                         |
|         +---> (Invalid) --+                                                                       |
|         |                 | Return FormState { status: 'ERROR', fieldErrors, ... }                |
|         v (Valid)         v                                                                       |
|  [Database Transaction (Prisma / Drizzle / ORM)]                                                  |
|         |                                                                                         |
|         +---> (DB Crash) -> Rollback & Return FormState { status: 'DATABASE_ERROR' }              |
|         v (Success)                                                                               |
|  [Next.js Cache Management System]                                                                |
|         |-- revalidateTag('profile-cache')                                                        |
|         |-- revalidatePath('/dashboard/profile')                                                  |
+---------------------------------------------------------------------------------------------------+
  |
  | 4. HTTP 200 OK Response Payload
  |    - React Flight Protocol Stream: [New Server Component Tree]
  |    - Action Return Value: { status: 'SUCCESS', data: {...} }
  v
+===================================================================================================+
| NETWORK BOUNDARY                                                                                  |
+===================================================================================================+
  |
  | 5. Client Re-conciliation
  v
+---------------------------------------------------------------------------------------------------+
| React Fiber Engine & DOM Reconciliation                                                           |
| - useActionState menerima status terbaru                                                          |
| - useOptimistic di-commit atau di-rollback jika mutasi gagal                                      |
| - Layout & Pages re-render otomatis berdasarkan RSC Flight Stream yang diperbarui                |
+---------------------------------------------------------------------------------------------------+
