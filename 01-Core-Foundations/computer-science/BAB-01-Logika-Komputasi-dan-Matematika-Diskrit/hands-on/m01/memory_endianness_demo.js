/**
 * Hands-on CS: Binary Representation, Bits, & Endianness
 */
console.log("=== COMPUTER SCIENCE: MEMORY & BINARY INTERNALS ===");

const buffer = new ArrayBuffer(4);
const view32 = new Uint32Array(buffer);
const view8 = new Uint8Array(buffer);

view32[0] = 0x12345678;

console.log("32-bit Integer Hex: 0x12345678");
console.log("Byte memory layout (Hex per byte):");
const bytes = Array.from(view8).map(b => '0x' + b.toString(16).padStart(2, '0'));
console.log(bytes.join(" "));

const isLittleEndian = view8[0] === 0x78;
console.log(`Arsitektur CPU Host: ${isLittleEndian ? "Little-Endian (x86/ARM standar)" : "Big-Endian"}`);
console.log("=== LAB MEMORY SELESAI ===");
