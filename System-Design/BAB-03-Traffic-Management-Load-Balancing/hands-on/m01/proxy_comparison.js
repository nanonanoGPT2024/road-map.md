// proxy_comparison.js
// Simulator Arsitektural: Perbedaan Forward Proxy vs Reverse Proxy dalam Menangani Request

const http = require('http');

// ==========================================
// 1. BACKEND PRIVATE SERVER (TIDAK BOLEH DIAKSES LANGSUNG OLEH PUBLIK)
// ==========================================
const BACKEND_PORT = 5001;
const backendServer = http.createServer((req, res) => {
  // Backend membaca siapa pengirim asli berdasarkan header yang disuntikkan proxy
  const clientIp = req.headers['x-forwarded-for'] || req.socket.remoteAddress;
  const isHttps = req.headers['x-forwarded-proto'] === 'https';
  const viaProxy = req.headers['via'] || 'None';

  console.log(`\n  [PRIVATE BACKEND SERVER] Menerima Request:`);
  console.log(`   -> Path URL            : ${req.url}`);
  console.log(`   -> Remote Socket IP    : ${req.socket.remoteAddress}`);
  console.log(`   -> X-Forwarded-For IP  : ${clientIp}`);
  console.log(`   -> Protokol Asli Client: ${isHttps ? 'HTTPS (Terenkripsi)' : 'HTTP (Plain)'}`);
  console.log(`   -> Header Via          : ${viaProxy}`);

  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    message: "Halo dari Private Backend!",
    detectedClientIp: clientIp,
    backendProcessPid: process.pid
  }));
});

// ==========================================
// 2. REVERSE PROXY SERVER (BERTINDAK ATAS NAMA BACKEND SERVER)
// ==========================================
const REVERSE_PROXY_PORT = 5000;
const reverseProxyServer = http.createServer((req, res) => {
  console.log(`\n[REVERSE PROXY :${REVERSE_PROXY_PORT}] Menerima Request dari Internet Publik:`);
  console.log(` -> Client Asli: ${req.socket.remoteAddress}`);

  // Reverse proxy menyuntikkan header identitas asli sebelum meneruskan ke backend
  const proxyReq = http.request({
    hostname: '127.0.0.1',
    port: BACKEND_PORT,
    path: req.url,
    method: req.method,
    headers: {
      ...req.headers,
      'host': 'api.perusahaan.internal',
      'x-real-ip': req.socket.remoteAddress,
      'x-forwarded-for': req.socket.remoteAddress,
      'x-forwarded-proto': 'https', // Simulasi SSL Termination
      'via': '1.1 reverse-proxy-nginx-simulator'
    }
  }, (backendRes) => {
    // Teruskan respon dari backend kembali ke client publik
    res.writeHead(backendRes.statusCode, backendRes.headers);
    backendRes.pipe(res);
  });

  proxyReq.on('error', (err) => {
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end(`502 Bad Gateway: ${err.message}\n`);
  });

  req.pipe(proxyReq);
});

// ==========================================
// 3. JALANKAN DEMO
// ==========================================
backendServer.listen(BACKEND_PORT, () => {
  reverseProxyServer.listen(REVERSE_PROXY_PORT, async () => {
    console.log("===================================================================");
    console.log("     DEMONSTRASI REVERSE PROXY & SSL TERMINATION SIMULATOR         ");
    console.log("===================================================================");
    console.log(`1. Private Backend Server aktif di port :${BACKEND_PORT} (Hanya internal)`);
    console.log(`2. Public Reverse Proxy aktif di port   :${REVERSE_PROXY_PORT} (Gerbang Publik)`);

    // Simulasi Client dari Luar mengirim request ke Reverse Proxy
    console.log("\n>>> [SIMULASI CLIENT]: Mengirim request ke http://localhost:5000/api/users...");
    
    http.get(`http://localhost:${REVERSE_PROXY_PORT}/api/users`, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        console.log(`\n<<< [CLIENT MENERIMA RESPON]:`);
        console.log(` Status: ${res.statusCode} OK`);
        console.log(` Data  : ${body}`);

        console.log("\n===================================================================");
        console.log(" [ANALISIS ARSITEKTUR]:");
        console.log(" 1. Client hanya berkomunikasi dengan Reverse Proxy (Port 5000).");
        console.log(" 2. Backend (Port 5001) terlindungi total di balik private network.");
        console.log(" 3. Header X-Forwarded-Proto memberitahu backend bahwa enkripsi TLS aman.");
        console.log("===================================================================\n");

        // Tutup server setelah demo selesai
        backendServer.close();
        reverseProxyServer.close();
      });
    });
  });
});
