[Hardware Display Controller]
       │
       │ VSYNC Pulse (tiap 8.3ms / 16.6ms)
       ▼
┌────────────────── UI THREAD (App Process) ────────────────────────┐
│                                                                   │
│  Choreographer.doFrame()                                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 1. Input Handling -> 2. Animation -> 3. Traversal (Measure, │  │
│  │    Layout, Draw) -> Compose Recomposition / Layout          │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                │                                  │
│                                ▼                                  │
│                 RenderThread.syncAndDrive()                       │
└────────────────────────────────┼──────────────────────────────────┘
                                 │
                                 ▼
┌────────────────── RENDER THREAD (App Process) ────────────────────┐
│  DrawFrameTask -> Upload GPU Shaders -> EGL swapBuffers()         │
└────────────────────────────────┼──────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────── SURFACEFLINGER ─────────────────────────┐
│  Compositor menyatukan Hardware Layer -> FrameBuffer ke Panel     │
└───────────────────────────────────────────────────────────────────┘
                                 ▲
                                 │
   MASALAH: JANK TERJADI JIKA UI THREAD / RENDER THREAD TERHAMBAT
                                 │
 ┌───────────────────────────────┴─────────────────────────────────┐
 │ GC Interruption: Generational Concurrent Copying (CC) GC        │
 │ - Thread Suspended (Stop-The-World) untuk Roots Scanning         │
 │ - Excessive Object Allocation Churn pada UI Loop                │
 │ - Heavy I/O Disk Read atau Lock Contention di Main Thread       │
 └─────────────────────────────────────────────────────────────────┘
