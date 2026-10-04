/**
 * Hands-on M02: JSON Schema Validator, Consumer-Driven Contract, & Rate Limiter Simulator
 * 
 * Demonstrasi:
 * 1. Engine Validasi JSON Schema Standar Mandiri (Zero-Dependencies).
 * 2. Simulasi Verifikasi Kontrak Microservices (Pact / Consumer-Driven Contract).
 * 3. Deteksi Celah Keamanan BOLA (IDOR) pada API.
 * 4. Pengujian Rate Limiting (HTTP 429 Too Many Requests & Throttling).
 */

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. MINI JSON SCHEMA VALIDATOR ENGINE
// ==========================================
class JsonSchemaValidator {
  validate(data, schema, path = "root") {
    const errors = [];

    // 1. Type validation
    if (schema.type) {
      if (schema.type === "integer") {
        if (typeof data !== "number" || !Number.isInteger(data)) {
          errors.push(`[${path}] Expected integer, got ${typeof data} (${data})`);
        }
      } else if (schema.type === "array") {
        if (!Array.isArray(data)) errors.push(`[${path}] Expected array, got ${typeof data}`);
      } else if (typeof data !== schema.type) {
        errors.push(`[${path}] Expected ${schema.type}, got ${typeof data}`);
      }
    }

    if (errors.length > 0) return { valid: false, errors };

    // 2. Constraints for numbers
    if (typeof data === "number") {
      if (schema.minimum !== undefined && data < schema.minimum) {
        errors.push(`[${path}] Value ${data} is less than minimum ${schema.minimum}`);
      }
      if (schema.maximum !== undefined && data > schema.maximum) {
        errors.push(`[${path}] Value ${data} is greater than maximum ${schema.maximum}`);
      }
    }

    // 3. Constraints for strings
    if (typeof data === "string") {
      if (schema.pattern && !new RegExp(schema.pattern).test(data)) {
        errors.push(`[${path}] String '${data}' does not match pattern ${schema.pattern}`);
      }
      if (schema.enum && !schema.enum.includes(data)) {
        errors.push(`[${path}] Value '${data}' not in allowed enum: [${schema.enum.join(", ")}]`);
      }
    }

    // 4. Object properties & required fields
    if (schema.type === "object" && typeof data === "object" && data !== null) {
      if (schema.required) {
        for (const reqKey of schema.required) {
          if (data[reqKey] === undefined) {
            errors.push(`[${path}] Missing required property '${reqKey}'`);
          }
        }
      }

      if (schema.additionalProperties === false) {
        const allowed = new Set(Object.keys(schema.properties || {}));
        for (const key of Object.keys(data)) {
          if (!allowed.has(key)) {
            errors.push(`[${path}] Additional property '${key}' is not allowed in schema`);
          }
        }
      }

      if (schema.properties) {
        for (const [key, propSchema] of Object.entries(schema.properties)) {
          if (data[key] !== undefined) {
            const nestedResult = this.validate(data[key], propSchema, `${path}.${key}`);
            if (!nestedResult.valid) {
              errors.push(...nestedResult.errors);
            }
          }
        }
      }
    }

    return { valid: errors.length === 0, errors };
  }
}

// ==========================================
// 2. CONSUMER-DRIVEN CONTRACT (PACT SIMULATOR)
// ==========================================
class ContractVerifier {
  static verify(providerResponse, contractExpectations) {
    const differences = [];
    for (const [field, expectedType] of Object.entries(contractExpectations)) {
      if (providerResponse[field] === undefined) {
        differences.push(`Contract Breach: Field '${field}' is missing from provider response!`);
      } else if (typeof providerResponse[field] !== expectedType) {
        differences.push(
          `Contract Breach: Field '${field}' expected type '${expectedType}', but provider returned '${typeof providerResponse[field]}'`
        );
      }
    }
    return {
      passed: differences.length === 0,
      differences
    };
  }
}

// ==========================================
// 3. RATE LIMITER SIMULATOR (HTTP 429)
// ==========================================
class RateLimiter {
  constructor(limitPerSecond) {
    this.limit = limitPerSecond;
    this.requests = [];
  }

  handleRequest() {
    const now = Date.now();
    // Filter requests in the last 1000ms
    this.requests = this.requests.filter(timestamp => now - timestamp < 1000);

    if (this.requests.length >= this.limit) {
      return {
        status: 429,
        headers: { "Retry-After": 1 },
        body: { error: "TOO_MANY_REQUESTS", message: "Rate limit exceeded. Please wait 1 second." }
      };
    }

    this.requests.push(now);
    return {
      status: 200,
      headers: { "X-RateLimit-Remaining": this.limit - this.requests.length },
      body: { status: "OK", data: "Data fetched successfully" }
    };
  }
}

// ==========================================
// 4. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║    JSON SCHEMA, CONTRACT VERIFICATION & SECURITY QA LAB       ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  // 1. JSON SCHEMA VALIDATION DEMO
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. VALIDASI RESPON API DENGAN JSON SCHEMA ===${ANSI.reset}`);
  const userProfileSchema = {
    type: "object",
    required: ["id", "username", "role", "balance"],
    additionalProperties: false,
    properties: {
      id: { type: "integer", minimum: 1 },
      username: { type: "string", pattern: "^[a-z0-9_]{3,15}$" },
      role: { type: "string", enum: ["ADMIN", "USER", "MERCHANT"] },
      balance: { type: "number", minimum: 0 }
    }
  };

  const validator = new JsonSchemaValidator();

  // Kasus Valid
  const validPayload = {
    id: 1042,
    username: "budi_santo",
    role: "USER",
    balance: 750000
  };
  const res1 = validator.validate(validPayload, userProfileSchema);
  console.log(`  Payload Valid: ${res1.valid ? ANSI.green + "✓ PASS" : ANSI.red + "✗ FAIL"}${ANSI.reset}`);

  // Kasus Invalid (Multiple Schema Breaches)
  const corruptPayload = {
    id: "1042", // String, bukan integer!
    username: "User Dengan Spasi", // Melanggar regex!
    role: "SUPER_ADMIN", // Tidak ada dalam enum!
    balance: -5000, // Nilai di bawah minimum!
    unauthorizedSecretField: "leaked_db_password" // additionalProperties: false
  };
  const res2 = validator.validate(corruptPayload, userProfileSchema);
  console.log(`\n  Payload Corrupt (Testing Schema Rejection):`);
  for (const err of res2.errors) {
    console.log(`    ${ANSI.red}✗ ${err}${ANSI.reset}`);
  }

  // 2. CONSUMER-DRIVEN CONTRACT TESTING (PACT)
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. CONSUMER-DRIVEN CONTRACT VERIFICATION (PACT) ===${ANSI.reset}`);
  const consumerExpectation = {
    orderId: "string",
    totalAmount: "number",
    currency: "string"
  };

  // Skenario A: Provider merilis perubahan yang kompatibel
  const providerBuildA = { orderId: "ORD-9901", totalAmount: 150000, currency: "IDR", extraDiscount: 10 };
  const pactA = ContractVerifier.verify(providerBuildA, consumerExpectation);
  console.log(`  Build Provider A: ${pactA.passed ? ANSI.green + "✓ CONTRACT HONORED" : ANSI.red + "✗ BREAK"}${ANSI.reset}`);

  // Skenario B: Provider merilis perubahan berbahaya (Rename totalAmount -> total_price)
  const providerBuildB = { orderId: "ORD-9902", total_price: 150000, currency: "IDR" };
  const pactB = ContractVerifier.verify(providerBuildB, consumerExpectation);
  console.log(`  Build Provider B (Breaking Change): ${pactB.passed ? ANSI.green + "✓ PASS" : ANSI.red + "✗ DEPLOYMENT BLOCKED"}${ANSI.reset}`);
  for (const diff of pactB.differences) {
    console.log(`    ${ANSI.yellow}🚨 ${diff}${ANSI.reset}`);
  }

  // 3. SECURITY QA: BOLA / IDOR ACCESS CONTROL SIMULATION
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. SECURITY TESTING: BOLA / IDOR PREVENTION ===${ANSI.reset}`);
  function accessResource(requesterUserId, targetResourceOwnerId) {
    if (requesterUserId !== targetResourceOwnerId) {
      return { status: 403, error: "FORBIDDEN: You do not own this resource" };
    }
    return { status: 200, data: "Sensitive Financial Statement" };
  }

  const legitAccess = accessResource("USR_01", "USR_01");
  const bolaAttack = accessResource("USR_ATTACKER", "USR_VICTIM");

  console.log(`  Akses Sah Sendiri (User 1 ➔ Resource 1): HTTP ${legitAccess.status} (${ANSI.green}OK${ANSI.reset})`);
  console.log(`  Uji Penetrasi BOLA (Attacker ➔ Resource Victim): HTTP ${bolaAttack.status} (${ANSI.green}PROTECTED 403${ANSI.reset})`);

  // 4. RATE LIMITING & THROTTLING TEST
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 4. RATE LIMITING TEST (BURST OF 4 REQUESTS, LIMIT: 3/SEC) ===${ANSI.reset}`);
  const limiter = new RateLimiter(3);
  for (let i = 1; i <= 4; i++) {
    const response = limiter.handleRequest();
    if (response.status === 200) {
      console.log(`  Request #${i}: HTTP 200 OK | Remaining: ${response.headers["X-RateLimit-Remaining"]}`);
    } else {
      console.log(`  Request #${i}: ${ANSI.red}HTTP 429 Too Many Requests${ANSI.reset} | Retry-After: ${response.headers["Retry-After"]}s`);
    }
  }

  console.log(`\n${ANSI.green}✓ JSON Schema, Contract, & Security Lab completed successfully!${ANSI.reset}\n`);
}

main();
