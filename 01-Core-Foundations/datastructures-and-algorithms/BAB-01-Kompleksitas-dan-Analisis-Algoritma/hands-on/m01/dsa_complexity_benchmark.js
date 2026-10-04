/**
 * Hands-on DSA: Membandingkan Kompleksitas Waktu O(1), O(n), dan O(n^2)
 */
console.log("=== DSA BENCHMARK: TIME COMPLEXITY COMPARISON ===");

const n = 10000;
const arr = Array.from({ length: n }, (_, i) => i);

// 1. O(1) Lookup
console.time("O(1) Array Index Lookup");
const val = arr[5000];
console.timeEnd("O(1) Array Index Lookup");

// 2. O(n) Linear Search
console.time("O(n) Linear Search");
let found = false;
for (let i = 0; i < arr.length; i++) {
  if (arr[i] === -1) { found = true; break; }
}
console.timeEnd("O(n) Linear Search");

// 3. O(n^2) Nested Loop Mini
const miniN = 1000;
console.time(`O(n^2) Nested Loop (n=${miniN})`);
let counter = 0;
for (let i = 0; i < miniN; i++) {
  for (let j = 0; j < miniN; j++) {
    counter++;
  }
}
console.timeEnd(`O(n^2) Nested Loop (n=${miniN})`);
console.log("=== BENCHMARK SELESAI ===");
