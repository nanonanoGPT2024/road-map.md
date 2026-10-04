/**
 * hands-on/m01/logging_drivers_rotation_sim.js
 * 
 * Simulasi Docker Logging Engine:
 * 1. Log Interception (stdout/stderr -> json wrapper with timestamps).
 * 2. Log Rotation Engine (max-size & max-file eviction strategy).
 * 3. Logging Buffer Mode Comparison (Blocking vs Non-Blocking Ring Buffer).
 * 4. Disk Safety Verification: Demonstrating how rotation caps storage growth.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("          DOCKER LOGGING DRIVER & ROTATION SIMULATOR v1.8                       ");
console.log("================================================================================\n");

class DockerLogRotationEngine {
    constructor(maxBytesPerFile = 1024, maxFiles = 3) {
        this.maxBytesPerFile = maxBytesPerFile;
        this.maxFiles = maxFiles;
        this.logFiles = [[]]; // Index 0 is active file, 1 is .1, 2 is .2
        this.totalBytesWritten = 0;
        this.totalLogsRotated = 0;
    }

    // Wrap stdout into Docker JSON log format
    formatJsonLog(stream, message) {
        return JSON.stringify({
            log: message + "\n",
            stream: stream,
            time: new Date().toISOString()
        });
    }

    // Write log entry with rotation mechanism
    writeLog(stream, message) {
        const jsonRecord = this.formatJsonLog(stream, message);
        const recordBytes = Buffer.byteLength(jsonRecord, 'utf8');

        // Check active file size
        const currentActiveSize = this.logFiles[0].reduce((acc, row) => acc + Buffer.byteLength(row, 'utf8'), 0);

        if (currentActiveSize + recordBytes > this.maxBytesPerFile) {
            this.rotate();
        }

        this.logFiles[0].push(jsonRecord);
        this.totalBytesWritten += recordBytes;
    }

    // Rotate files: active -> .1 -> .2 -> drop oldest
    rotate() {
        this.totalLogsRotated++;
        console.log(`  [ROTATION TRIGGERED] Active log exceeded ${this.maxBytesPerFile} bytes. Rolling file generation...`);
        
        // Shift files down the chain
        this.logFiles.unshift([]); // New active empty file
        
        // Prune if exceeds maxFiles
        if (this.logFiles.length > this.maxFiles) {
            const pruned = this.logFiles.pop();
            console.log(`  [PRUNED] Oldest archive (.${this.logFiles.length}) containing ${pruned.length} lines deleted.`);
        }
    }

    getStatus() {
        return this.logFiles.map((f, idx) => {
            const name = idx === 0 ? "container.log (active)" : `container.log.${idx}`;
            const bytes = f.reduce((acc, row) => acc + Buffer.byteLength(row, 'utf8'), 0);
            return { name, lines: f.length, bytes };
        });
    }
}

// Simulation of Blocking vs Non-Blocking mode
class LoggingBufferModeTest {
    static async testBlockingMode(messagesCount, ioDelayMs = 40) {
        console.log(`[MODE: BLOCKING] Mengirim ${messagesCount} log dengan simulated disk latency ${ioDelayMs}ms:`);
        const start = Date.now();
        for (let i = 1; i <= messagesCount; i++) {
            await sleep(ioDelayMs); // Disk write blocks application thread
        }
        const elapsed = Date.now() - start;
        console.log(`  -> Total waktu eksekusi: ${elapsed}ms (Aplikasi terblokir selama I/O!)\n`);
        return elapsed;
    }

    static async testNonBlockingMode(messagesCount, ringBufferSize = 5) {
        console.log(`[MODE: NON-BLOCKING] Mengirim ${messagesCount} log dengan ring buffer kapasitas ${ringBufferSize}:`);
        const ringBuffer = [];
        let droppedCount = 0;
        const start = Date.now();

        for (let i = 1; i <= messagesCount; i++) {
            const logEntry = `Log item #${i}`;
            if (ringBuffer.length >= ringBufferSize) {
                // Buffer overflow: drop oldest to protect app performance
                ringBuffer.shift();
                droppedCount++;
            }
            ringBuffer.push(logEntry);
            // Producer non-blocking: 0 ms delay!
        }
        const elapsed = Date.now() - start;
        console.log(`  -> Total waktu eksekusi: ${elapsed}ms (Instan! Aplikasi tidak pernah terblokir)`);
        console.log(`  -> Buffer state: ${ringBuffer.length} log dalam memory, ${droppedCount} log tertua di-drop demi menjaga throughput aplikasi.\n`);
        return elapsed;
    }
}

async function main() {
    console.log("=== BAGIAN 1: SIMULASI LOG ROTATION DOCKER DAEMON ===");
    console.log("Konfigurasi: max-size: 1KB, max-file: 3\n");

    const engine = new DockerLogRotationEngine(1024, 3);

    // Simulate high volume application logs
    for (let i = 1; i <= 35; i++) {
        const stream = i % 8 === 0 ? "stderr" : "stdout";
        engine.writeLog(stream, `HTTP GET /api/v1/checkout - 200 OK - Request ID: req_txn_${1000 + i}`);
    }

    console.log("\nStatus File Log di Host Disk (/var/lib/docker/containers/<id>/):");
    console.log("--------------------------------------------------------------------------------");
    console.log(String("File Name").padEnd(30) + String("Lines").padEnd(15) + "Size on Disk");
    console.log("--------------------------------------------------------------------------------");
    engine.getStatus().forEach(f => {
        console.log(f.name.padEnd(30) + String(f.lines).padEnd(15) + `${f.bytes} bytes`);
    });
    console.log("--------------------------------------------------------------------------------");
    console.log(`Total data generated: ${engine.totalBytesWritten} bytes.`);
    console.log(`Total active storage capped safely at ~${engine.getStatus().reduce((a, b) => a + b.bytes, 0)} bytes.\n`);

    console.log("=== BAGIAN 2: PERBANDINGAN LATENCY (BLOCKING VS NON-BLOCKING) ===");
    await LoggingBufferModeTest.testBlockingMode(10, 30);
    await LoggingBufferModeTest.testNonBlockingMode(10, 5);

    console.log("=== KESIMPULAN REKOMENDASI PRODUCTION ===");
    console.log("1. Selalu pasang 'max-size' dan 'max-file' di /etc/docker/daemon.json.");
    console.log("2. Gunakan 'mode: non-blocking' pada service API microservices dengan traffic tinggi.");
    console.log("3. Gunakan 'truncate -s 0 <file.log>' jika perlu mengosongkan log darurat tanpa mematikan container.");
}

main().catch(console.error);
