/**
 * Hands-on M02: PostgreSQL 8KB Page Layout & MVCC Tuple Visibility Engine
 * Track: PostgreSQL Mastery - BAB 01
 * 
 * Demonstrasi struktur fisik disk page & MVCC:
 * 1. 8192 bytes Page Layout (PageHeaderData, ItemPointer, Tuples)
 * 2. Slotted Page Architecture (pd_lower vs pd_upper)
 * 3. HeapTupleHeaderData (xmin, xmax, cid)
 * 4. MVCC Snapshot Visibility Check (Read Committed semantics)
 * 5. Zero external dependencies (Node.js)
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m"
};

const BLCKSZ = 8192; // 8KB PostgreSQL default page size
const PAGE_HEADER_SIZE = 24;

class PostgresPage {
  constructor(pageId = 0) {
    this.pageId = pageId;
    this.pd_lower = PAGE_HEADER_SIZE;
    this.pd_upper = BLCKSZ;
    this.itemPointers = []; // Line pointers array: [{ offset, len }]
    this.tuples = [];       // Physical tuples stored at top of page
  }

  // Insert a new tuple into the 8KB page
  insertTuple(data, xmin, xmax = 0) {
    const serialized = JSON.stringify(data);
    const tupleSize = 24 + serialized.length; // 24 bytes HeapTupleHeaderData + payload
    const neededSpace = 4 + tupleSize; // 4 bytes ItemPointer + tuple

    // Check free space: pd_upper - pd_lower
    const freeSpace = this.pd_upper - this.pd_lower;
    if (freeSpace < neededSpace) {
      throw new Error(`Page #${this.pageId} Full: Free space (${freeSpace}B) < Required (${neededSpace}B)`);
    }

    // Allocate tuple at top of page (grows downward)
    this.pd_upper -= tupleSize;
    const tupleOffset = this.pd_upper;

    const tuple = {
      header: { xmin, xmax, offset: tupleOffset, size: tupleSize },
      payload: data
    };
    this.tuples.push(tuple);

    // Allocate ItemPointer at bottom of page (grows upward)
    const itemId = this.itemPointers.length + 1;
    this.itemPointers.push({ itemId, offset: tupleOffset, len: tupleSize });
    this.pd_lower += 4;

    return { itemId, tupleOffset };
  }

  // Check tuple visibility against an active MVCC Snapshot
  isTupleVisible(tuple, snapshot) {
    // Snapshot: { xmin, xmax, activeXids }
    const { xmin, xmax } = tuple.header;

    // 1. If created by transaction that is not yet committed (active) -> Invisible
    if (snapshot.activeXids.includes(xmin) || xmin >= snapshot.xmax) {
      return false;
    }

    // 2. If deleted by a transaction that already committed -> Invisible
    if (xmax !== 0 && !snapshot.activeXids.includes(xmax) && xmax < snapshot.xmax) {
      return false;
    }

    return true;
  }

  printLayout() {
    console.log(`\n--- PostgreSQL 8KB Page #${this.pageId} Layout ---`);
    console.log(`PageHeader: 0 - 24B | pd_lower: ${this.pd_lower}B (ItemPointers: ${this.itemPointers.length})`);
    console.log(`pd_upper: ${this.pd_upper}B | Total Tuples: ${this.tuples.length}`);
    console.log(`Unallocated Free Space: ${this.pd_upper - this.pd_lower} bytes (${(((this.pd_upper - this.pd_lower)/BLCKSZ)*100).toFixed(1)}%)`);
  }
}

// ==========================================
// TEST SUITE & RUNNER
// ==========================================
function runLab() {
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}  LAB HANDS-ON: POSTGRES 8KB PAGE & MVCC VISIBILITY   ${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);

  const page = new PostgresPage(0);

  console.log(`\n${ANSI.bold}[Step 1] Inserting rows into Page 0 (Simulating INSERT xid=100)...${ANSI.reset}`);
  page.insertTuple({ id: 1, name: "Ali", balance: 1500000 }, 100);
  page.insertTuple({ id: 2, name: "Siti", balance: 2500000 }, 100);
  page.printLayout();

  console.log(`\n${ANSI.bold}[Step 2] Simulating UPDATE (Delete row 1 via xmax=105, Insert new version xmin=105)...${ANSI.reset}`);
  page.tuples[0].header.xmax = 105; // Marked dead by xid 105
  page.insertTuple({ id: 1, name: "Ali", balance: 1800000 }, 105);
  page.printLayout();

  console.log(`\n${ANSI.bold}[Step 3] Running MVCC Visibility Check for Transaction XID=102 (Snapshot)...${ANSI.reset}`);
  // Snapshot taken before XID 105 committed
  const snapshotTx102 = { xmin: 100, xmax: 105, activeXids: [105] };
  console.log("Snapshot 102 state:", snapshotTx102);

  const visibleRows102 = page.tuples.filter(t => page.isTupleVisible(t, snapshotTx102));
  console.log(`Visible tuples for Tx 102 (should see Old Ali balance 1.500.000):`, visibleRows102.map(t => t.payload));

  console.log(`\n${ANSI.bold}[Step 4] Running MVCC Visibility Check for Transaction XID=110 (Post-Commit Snapshot)...${ANSI.reset}`);
  // Snapshot taken after XID 105 committed
  const snapshotTx110 = { xmin: 106, xmax: 110, activeXids: [] };
  const visibleRows110 = page.tuples.filter(t => page.isTupleVisible(t, snapshotTx110));
  console.log(`Visible tuples for Tx 110 (should see Updated Ali balance 1.800.000):`, visibleRows110.map(t => t.payload));

  const ali102 = visibleRows102.find(t => t.payload.id === 1);
  const ali110 = visibleRows110.find(t => t.payload.id === 1);
  if (ali102 && ali102.payload.balance === 1500000 && ali110 && ali110.payload.balance === 1800000) {
    console.log(`\n${ANSI.green}${ANSI.bold}✓ SUCCESS: PostgreSQL Slotted Page layout & MVCC isolation verified!${ANSI.reset}`);
  } else {
    throw new Error("MVCC visibility assertion mismatch");
  }
}

runLab();
