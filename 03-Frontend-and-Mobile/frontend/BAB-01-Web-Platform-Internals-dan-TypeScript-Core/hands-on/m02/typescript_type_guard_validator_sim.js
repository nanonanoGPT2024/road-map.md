/**
 * Hands-on M02: TypeScript Runtime Type Guard & Schema Narrowing Engine
 * Track: Frontend & TypeScript Mastery - BAB 01
 * 
 * Demonstrasi prinsip Type System & Type Narrowing:
 * 1. Discriminated Unions Pattern
 * 2. Custom Type Predicates / Type Guards
 * 3. Exhaustive Pattern Matching (Never check)
 * 4. Zero external dependencies (Node.js)
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m"
};

// 1. Primitive Type Validators
const T = {
  string: (val) => typeof val === "string",
  number: (val) => typeof val === "number" && !Number.isNaN(val),
  boolean: (val) => typeof val === "boolean",
  literal: (expected) => (val) => val === expected,
  array: (itemValidator) => (val) => Array.isArray(val) && val.every(itemValidator),
  object: (shape) => (val) => {
    if (typeof val !== "object" || val === null) return false;
    for (const [key, validator] of Object.entries(shape)) {
      if (!validator(val[key])) return false;
    }
    return true;
  }
};

// 2. Schema Parser with Narrowing & Result Monad
class Schema {
  constructor(name, validator) {
    this.name = name;
    this.validator = validator;
  }

  parse(data) {
    if (this.validator(data)) {
      return { success: true, data };
    }
    return {
      success: false,
      error: `Validation failed: Payload does not conform to schema '${this.name}'`
    };
  }
}

// 3. User & Auth Schemas (Discriminated Union)
const UserProfileSchema = new Schema("UserProfile", T.object({
  id: T.string,
  username: T.string,
  age: T.number,
  roles: T.array(T.string)
}));

const AdminActionSchema = new Schema("AdminAction", T.object({
  type: T.literal("ADMIN_EVENT"),
  adminId: T.string,
  action: T.string,
  timestamp: T.number
}));

const UserActionSchema = new Schema("UserAction", T.object({
  type: T.literal("USER_EVENT"),
  userId: T.string,
  payload: T.object({
    clickTarget: T.string
  })
}));

// 4. Exhaustive Matcher Simulation
function processAppEvent(event) {
  switch (event.type) {
    case "ADMIN_EVENT":
      return `Processed Admin [${event.adminId}] executing [${event.action}]`;
    case "USER_EVENT":
      return `Processed User [${event.userId}] clicking [${event.payload.clickTarget}]`;
    default:
      // Exhaustive check (TypeScript 'assertNever')
      throw new Error(`Unhandled discriminated union variant: ${JSON.stringify(event)}`);
  }
}

// ==========================================
// TEST SUITE & RUNNER
// ==========================================
function runLab() {
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}  LAB HANDS-ON: TS TYPE GUARD & SCHEMA NARROWING SIM  ${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);

  // Test 1: Valid User Profile
  console.log(`\n${ANSI.bold}[Test 1] Parsing Valid User Payload${ANSI.reset}`);
  const rawUser = { id: "usr_101", username: "alex_dev", age: 28, roles: ["engineer", "admin"] };
  const res1 = UserProfileSchema.parse(rawUser);
  console.log("Validation Result:", res1.success ? `${ANSI.green}VALID${ANSI.reset}` : `${ANSI.red}INVALID${ANSI.reset}`);
  if (!res1.success) throw new Error("Expected valid payload");

  // Test 2: Invalid User Profile (Type Mismatch)
  console.log(`\n${ANSI.bold}[Test 2] Rejecting Invalid Types (Age as String)${ANSI.reset}`);
  const invalidUser = { id: "usr_102", username: "budi", age: "twenty", roles: [] };
  const res2 = UserProfileSchema.parse(invalidUser);
  console.log("Validation Result:", res2.success ? `${ANSI.green}VALID${ANSI.reset}` : `${ANSI.red}REJECTED (${res2.error})${ANSI.reset}`);
  if (res2.success) throw new Error("Expected invalid payload to fail");

  // Test 3: Discriminated Union Pattern & Exhaustive Processing
  console.log(`\n${ANSI.bold}[Test 3] Discriminated Union Event Processing${ANSI.reset}`);
  const adminEvent = { type: "ADMIN_EVENT", adminId: "adm_01", action: "PURGE_CACHE", timestamp: Date.now() };
  const userEvent = { type: "USER_EVENT", userId: "usr_55", payload: { clickTarget: "btn-checkout" } };

  console.log("Event 1:", processAppEvent(adminEvent));
  console.log("Event 2:", processAppEvent(userEvent));

  console.log(`\n${ANSI.green}${ANSI.bold}✓ SUCCESS: All Type Guard and Narrowing assertions passed!${ANSI.reset}`);
}

runLab();
