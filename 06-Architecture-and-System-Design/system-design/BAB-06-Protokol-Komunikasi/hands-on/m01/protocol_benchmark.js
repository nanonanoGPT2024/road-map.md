// protocol_benchmark.js
// Benchmark Performa: Serialisasi Teks JSON vs Binary Protocol Buffers (Protobuf) Simulator

// 1. Data Sample: Transaksi Pembayaran E-Commerce
const sampleTransaction = {
  transactionId: 10982734,
  senderId: 991823,
  recipientId: 442109,
  amount: 1575000,
  currency: "IDR",
  timestamp: 1726050000,
  isSuccessful: true,
  notes: "Pembayaran tagihan laptop"
};

// ===================================================================
// A. ENKODER / DEKODER JSON STANDAR
// ===================================================================
function runJSONBenchmark(iterations = 10000) {
  // Serialisasi (Object -> JSON String -> Buffer)
  const jsonString = JSON.stringify(sampleTransaction);
  const jsonBuffer = Buffer.from(jsonString, 'utf-8');

  const startEncode = process.hrtime.bigint();
  for (let i = 0; i < iterations; i++) {
    JSON.stringify(sampleTransaction);
  }
  const encodeDurationMs = Number(process.hrtime.bigint() - startEncode) / 1e6;

  const startDecode = process.hrtime.bigint();
  for (let i = 0; i < iterations; i++) {
    JSON.parse(jsonString);
  }
  const decodeDurationMs = Number(process.hrtime.bigint() - startDecode) / 1e6;

  return {
    payloadSizeBytes: jsonBuffer.length,
    encodeDurationMs,
    decodeDurationMs,
    samplePayload: jsonString
  };
}

// ===================================================================
// B. ENKODER / DEKODER SIMULATOR PROTOCOL BUFFERS (BINER PADAT)
// ===================================================================
// Pada Protobuf nyata, field name dihilangkan dan diganti dengan integer tag + varint encoding
function encodeSimulatedProtobuf(data) {
  // Alokasi buffer biner kecil
  const buf = Buffer.alloc(32);
  let offset = 0;

  // Tag 1 (int32): transactionId
  buf.writeUInt8((1 << 3) | 0, offset++);
  buf.writeUInt32LE(data.transactionId, offset); offset += 4;

  // Tag 2 (int32): senderId
  buf.writeUInt8((2 << 3) | 0, offset++);
  buf.writeUInt32LE(data.senderId, offset); offset += 4;

  // Tag 3 (int32): recipientId
  buf.writeUInt8((3 << 3) | 0, offset++);
  buf.writeUInt32LE(data.recipientId, offset); offset += 4;

  // Tag 4 (int32): amount
  buf.writeUInt8((4 << 3) | 0, offset++);
  buf.writeUInt32LE(data.amount, offset); offset += 4;

  // Tag 5 (bool): isSuccessful
  buf.writeUInt8((5 << 3) | 0, offset++);
  buf.writeUInt8(data.isSuccessful ? 1 : 0, offset++);

  return buf.subarray(0, offset);
}

function decodeSimulatedProtobuf(buf) {
  let offset = 0;
  const result = {};

  offset++; // tag 1
  result.transactionId = buf.readUInt32LE(offset); offset += 4;

  offset++; // tag 2
  result.senderId = buf.readUInt32LE(offset); offset += 4;

  offset++; // tag 3
  result.recipientId = buf.readUInt32LE(offset); offset += 4;

  offset++; // tag 4
  result.amount = buf.readUInt32LE(offset); offset += 4;

  offset++; // tag 5
  result.isSuccessful = buf.readUInt8(offset++) === 1;

  return result;
}

function runProtobufBenchmark(iterations = 10000) {
  const protoBuf = encodeSimulatedProtobuf(sampleTransaction);

  const startEncode = process.hrtime.bigint();
  for (let i = 0; i < iterations; i++) {
    encodeSimulatedProtobuf(sampleTransaction);
  }
  const encodeDurationMs = Number(process.hrtime.bigint() - startEncode) / 1e6;

  const startDecode = process.hrtime.bigint();
  for (let i = 0; i < iterations; i++) {
    decodeSimulatedProtobuf(protoBuf);
  }
  const decodeDurationMs = Number(process.hrtime.bigint() - startDecode) / 1e6;

  return {
    payloadSizeBytes: protoBuf.length,
    encodeDurationMs,
    decodeDurationMs,
    samplePayload: protoBuf.toString('hex')
  };
}

// ===================================================================
// RUN BENCHMARK
// ===================================================================
function main() {
  const ITERATIONS = 50000;
  console.log("===================================================================");
  console.log(` BENCHMARK SERIALISASI: JSON (REST) vs PROTOCOL BUFFERS (gRPC)     `);
  console.log(` Pengujian: ${ITERATIONS.toLocaleString()} iterasi komputasi encode/decode`);
  console.log("===================================================================\n");

  const jsonRes = runJSONBenchmark(ITERATIONS);
  const protoRes = runProtobufBenchmark(ITERATIONS);

  console.log("┌──────────────────────────┬────────────────────┬────────────────────┐");
  console.log("│ Metrik Kinerja           │ JSON (REST)        │ Protobuf (gRPC)    │");
  console.log("├──────────────────────────┼────────────────────┼────────────────────┤");
  console.log(`│ Ukuran Payload (Bytes)   │ ${`${jsonRes.payloadSizeBytes} Bytes`.padEnd(18, ' ')} │ ${`${protoRes.payloadSizeBytes} Bytes`.padEnd(18, ' ')} │`);
  console.log(`│ Waktu Encoding (50k ops) │ ${`${jsonRes.encodeDurationMs.toFixed(2)} ms`.padEnd(18, ' ')} │ ${`${protoRes.encodeDurationMs.toFixed(2)} ms`.padEnd(18, ' ')} │`);
  console.log(`│ Waktu Decoding (50k ops) │ ${`${jsonRes.decodeDurationMs.toFixed(2)} ms`.padEnd(18, ' ')} │ ${`${protoRes.decodeDurationMs.toFixed(2)} ms`.padEnd(18, ' ')} │`);
  console.log("└──────────────────────────┴────────────────────┴────────────────────┘\n");

  console.log(`[CONTOH ISI PAYLOAD]:`);
  console.log(` - JSON String    : ${jsonRes.samplePayload}`);
  console.log(` - Protobuf Binary: <Hex: ${protoRes.samplePayload}>`);

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN ANALISIS ARSITEKTUR]:");
  const bytesSaved = (((jsonRes.payloadSizeBytes - protoRes.payloadSizeBytes) / jsonRes.payloadSizeBytes) * 100).toFixed(1);
  const speedUp = (jsonRes.decodeDurationMs / protoRes.decodeDurationMs).toFixed(1);
  console.log(` 1. Efisiensi Jaringan : Protobuf menghemat ${bytesSaved}% bandwidth (sangat krusial untuk 1 miliar calls)!`);
  console.log(` 2. Efisiensi CPU      : Parsing biner Protobuf ${speedUp}x lipat lebih cepat dari parsing teks JSON.`);
  console.log("===================================================================\n");
}

main();
