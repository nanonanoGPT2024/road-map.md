/**
 * Container Lifecycle FSM & Signal Termination Simulator
 * Hands-on Lab: BAB 02 - Module 01
 * 
 * Demonstrates:
 * 1. Finite State Machine (FSM): Created -> Running -> Paused -> Stopped.
 * 2. Graceful Shutdown (SIGTERM) vs Timeout Force Kill (SIGKILL).
 * 3. Exit Codes: 0 (Clean), 1 (App Error), 137 (SIGKILL/OOM), 143 (SIGTERM).
 */

class MockContainer {
  constructor(name, handlesSigterm = true) {
    this.name = name;
    this.handlesSigterm = handlesSigterm;
    this.state = 'CREATED'; // CREATED, RUNNING, PAUSED, STOPPED
    this.exitCode = null;
    this.logs = [];
  }

  start() {
    if (this.state !== 'CREATED' && this.state !== 'STOPPED') {
      throw new Error(`Cannot start container ${this.name} from state: ${this.state}`);
    }
    this.state = 'RUNNING';
    this.logs.push(`[${this.name}] Process started (PID 1). State: RUNNING`);
    console.log(`🚀 [docker start] ${this.name} state transitioned to RUNNING`);
  }

  pause() {
    if (this.state !== 'RUNNING') throw new Error(`Cannot pause container in state: ${this.state}`);
    this.state = 'PAUSED';
    this.logs.push(`[${this.name}] Freezer cgroup activated. CPU threads frozen.`);
    console.log(`⏸️  [docker pause] ${this.name} state transitioned to PAUSED`);
  }

  unpause() {
    if (this.state !== 'PAUSED') throw new Error(`Cannot unpause container in state: ${this.state}`);
    this.state = 'RUNNING';
    this.logs.push(`[${this.name}] Freezer cgroup deactivated. CPU threads thawed.`);
    console.log(`▶️  [docker unpause] ${this.name} state transitioned to RUNNING`);
  }

  // Simulating docker stop (SIGTERM with timeout fallback to SIGKILL)
  async stop(timeoutMs = 400) {
    console.log(`\n🛑 [docker stop -t ${timeoutMs}ms] Sending SIGTERM (Signal 15) to ${this.name} (PID 1)...`);

    if (this.handlesSigterm) {
      console.log(`   ↳ [${this.name}] SIGTERM trapped! Closing DB pool and finishing inflight requests...`);
      await new Promise(r => setTimeout(r, 120)); // Graceful cleanup
      this.state = 'STOPPED';
      this.exitCode = 0; // Clean exit
      this.logs.push(`[${this.name}] Graceful shutdown completed cleanly.`);
      console.log(`✅ [Graceful Exit] ${this.name} stopped cleanly with Exit Code ${this.exitCode}`);
      return;
    }

    // Uncooperative app: ignores SIGTERM!
    console.warn(`   ⚠️  [${this.name}] Ignored SIGTERM! Hanging indefinitely...`);
    console.log(`   ⏳ Waiting for timeout of ${timeoutMs}ms to elapse...`);
    await new Promise(r => setTimeout(r, timeoutMs));

    console.error(`💥 [TIMEOUT EXPIRED] Sending SIGKILL (Signal 9) to force kill ${this.name}!`);
    this.state = 'STOPPED';
    this.exitCode = 137; // 128 + 9 = 137
    this.logs.push(`[${this.name}] Forcefully terminated by SIGKILL after timeout.`);
    console.log(`❌ [Force Kill] ${this.name} killed with Exit Code ${this.exitCode}`);
  }

  // Simulating docker kill (Instant SIGKILL)
  kill() {
    console.log(`\n⚡ [docker kill] Instant SIGKILL (Signal 9) sent to ${this.name}...`);
    this.state = 'STOPPED';
    this.exitCode = 137;
    this.logs.push(`[${this.name}] Terminated instantly via docker kill.`);
    console.log(`❌ [Instant Kill] ${this.name} stopped with Exit Code ${this.exitCode}`);
  }

  // Simulating internal application crash
  simulateCrash() {
    console.log(`\n💥 [CRASH] Unhandled Exception inside ${this.name}...`);
    this.state = 'STOPPED';
    this.exitCode = 1;
    this.logs.push(`[${this.name}] Crashed: ReferenceError at /app/index.js`);
    console.log(`❌ [App Crash] ${this.name} stopped with Exit Code ${this.exitCode}`);
  }
}

// -----------------------------------------------------------------
// LAB EXECUTION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🕹️  DOCKER CONTAINER LIFECYCLE & SIGNALS LAB`);
  console.log(`======================================================\n`);

  // SCENARIO 1: Full FSM Loop (Create -> Start -> Pause -> Unpause -> Stop Gracefully)
  console.log(`--- SCENARIO 1: COOPERATIVE APP GRACEFUL LIFECYCLE ---`);
  const webApp = new MockContainer('order-api', true);
  webApp.start();
  webApp.pause();
  webApp.unpause();
  await webApp.stop(300);

  // SCENARIO 2: Uncooperative App (Ignores SIGTERM, hits timeout, killed via SIGKILL)
  console.log(`\n--- SCENARIO 2: UNCOOPERATIVE APP TIMEOUT FALLBACK ---`);
  const rogueApp = new MockContainer('legacy-crawler', false); // does NOT handle sigterm
  rogueApp.start();
  await rogueApp.stop(300);

  // SCENARIO 3: Instant docker kill
  console.log(`\n--- SCENARIO 3: INSTANT DOCKER KILL ---`);
  const workerApp = new MockContainer('heavy-worker', true);
  workerApp.start();
  workerApp.kill();

  // SCENARIO 4: Internal App Crash
  console.log(`\n--- SCENARIO 4: INTERNAL EXCEPTION CRASH ---`);
  const buggyApp = new MockContainer('buggy-service', true);
  buggyApp.start();
  buggyApp.simulateCrash();

  // PRINT SUMMARY TABLE OF EXIT CODES
  console.log(`\n======================================================`);
  console.log(`📊 CONTAINER EXIT CODES SUMMARY MATRIX`);
  console.log(`======================================================`);
  const containers = [webApp, rogueApp, workerApp, buggyApp];
  console.log(`| Container Name    | State   | Exit Code | Termination Cause               |`);
  console.log(`|-------------------|---------|-----------|----------------------------------|`);
  containers.forEach(c => {
    const cause = c.exitCode === 0 ? 'Normal / Graceful (SIGTERM)' :
                  c.exitCode === 1 ? 'Internal App Error' :
                  c.exitCode === 137 ? 'Force Killed (SIGKILL / OOM)' :
                  c.exitCode === 143 ? 'Terminated by SIGTERM' : 'Unknown';
    console.log(`| ${c.name.padEnd(17)} | ${c.state.padEnd(7)} | ${c.exitCode.toString().padEnd(9)} | ${cause.padEnd(32)} |`);
  });
  console.log(`======================================================\n`);

  console.log(`🎉 Container Lifecycle & Signals Lab Completed Successfully!`);
}

runLab();
