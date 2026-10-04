+----------------------------------------------------------------------------------------------------+
|                                      GLOBAL CLIENTS / BROWSERS                                     |
+----------------------------------------------------------------------------------------------------+
                                                  │
                                                  ▼
+----------------------------------------------------------------------------------------------------+
|                              EDGE NETWORK (CDN / ANYCAST ROUTING)                                  |
|                                                                                                    |
|   +--------------------------------------------------------------------------------------------+   |
|   | Next.js Edge Runtime (Vercel Edge / Cloudflare Workers)                                    |   |
|   | - Middleware, Auth Verification, Fast Edge Route Handlers                                  |   |
|   +--------------------------------------------------------------------------------------------+   |
|             │                                                                 │                    |
|             │ (Sub-millisecond Read/Write)                                     │ (Stateless HTTP)   |
|             ▼                                                                 ▼                    |
|   +-------------------+                                             +--------------------+         |
|   | Upstash Redis KV  |                                             | Neon HTTP Query    |         |
|   | (Global Cluster)  |                                             | Gateway            |         |
|   +-------------------+                                             +--------------------+         |
|             ▲                                                                 │                    |
+-------------│-----------------------------------------------------------------│--------------------+
              │                                                                 │
              │ Cache Invalidation                                              │ Fast Edge Read
              │ via Server Actions                                              │
              │                                                                 │
+-------------│-----------------------------------------------------------------│--------------------+
|             │                REGION DATA CENTER (AWS us-east-1)               │                    |
|             │                                                                 │                    |
|   +-------------------------------------------------------------+             │                    |
|   | Next.js Serverless Functions (Node.js Runtime)              |             │                    |
|   | - Prisma / Drizzle ORM                                      |             │                    |
|   | - Complex Business Logic, Heavy Mutations, Server Actions   |             │                    |
|   +-------------------------------------------------------------+             │                    |
|             │                                                                 │                    |
|             │ TCP Handshake (Connection via Singleton Pooler)                 │                    |
|             ▼                                                                 │                    |
|   +-------------------------------------------------------------+             │                    |
|   | External Connection Pooler (PgBouncer / Supavisor)          |             │                    |
|   | - Pooling Mode: Transaction                                 |             │                    |
|   | - Mengubah ribuan koneksi fungsi -> Pool stabil 20-50 conn  |             │                    |
|   +-------------------------------------------------------------+             │                    |
|             │                                                                 │                    |
|             │ Persistent Local Unix Socket / Low-Latency TCP                  │                    |
|             ▼                                                                 ▼                    |
|   +------------------------------------------------------------------------------------+           |
|   | Primary PostgreSQL Database Cluster (Engine: Neon / Supabase / AWS Aurora RDS)     |           |
|   | - Storage Engine (NVMe/EBS)                                                        |           |
|   | - Write-Ahead Logging (WAL)                                                        |           |
|   +------------------------------------------------------------------------------------+           |
+----------------------------------------------------------------------------------------------------+
