/**
 * LAB SIMULATION: Model Context Protocol (MCP) JSON-RPC 2.0 Engine
 * 
 * Mensimulasikan:
 * 1. MCP Server (Subprocess / Service mandiri dengan Database Tools).
 * 2. MCP Client (Modul integrasi di dalam OpenClaw Gateway).
 * 3. Tool Discovery Handshake ('tools/list').
 * 4. Tool Execution Request ('tools/call') dengan Read-Only Enforcement.
 */

// 1. MCP SERVER IMPLEMENTATION (MOCK DATABASE SERVICE)
class McpDatabaseServer {
  constructor(serverName) {
    this.serverName = serverName;
    // Mock Database Tables
    this.database = {
      users: [
        { id: 1, name: "Budi Santoso", role: "admin", status: "active" },
        { id: 2, name: "Siti Rahma", role: "developer", status: "active" },
        { id: 3, name: "Andi Wijaya", role: "guest", status: "pending" }
      ],
      orders: [
        { orderId: "ORD-101", userId: 1, total: 250000 },
        { orderId: "ORD-102", userId: 2, total: 780000 }
      ]
    };
  }

  // Handle Inbound JSON-RPC 2.0 Request
  handleJsonRpc(request) {
    const { jsonrpc, id, method, params } = request;

    if (jsonrpc !== "2.0") {
      return { jsonrpc: "2.0", id, error: { code: -32600, message: "Invalid JSON-RPC version" } };
    }

    // Handshake: Kembalikan daftar kemampuan tools yang didukung
    if (method === "tools/list") {
      return {
        jsonrpc: "2.0",
        id,
        result: {
          tools: [
            {
              name: "describe_tables",
              description: "Menampilkan daftar seluruh tabel yang ada di database",
              inputSchema: { type: "object", properties: {} }
            },
            {
              name: "run_read_query",
              description: "Mengeksekusi query SELECT SQL read-only pada database",
              inputSchema: {
                type: "object",
                properties: {
                  table: { type: "string", description: "Nama tabel target" }
                },
                required: ["table"]
              }
            }
          ]
        }
      };
    }

    // Eksekusi Pemanggilan Tool
    if (method === "tools/call") {
      const { name, arguments: args } = params;

      if (name === "describe_tables") {
        return {
          jsonrpc: "2.0",
          id,
          result: {
            content: [
              {
                type: "text",
                text: JSON.stringify(Object.keys(this.database))
              }
            ]
          }
        };
      }

      if (name === "run_read_query") {
        const table = args.table;
        if (!this.database[table]) {
          return {
            jsonrpc: "2.0",
            id,
            error: { code: -32001, message: `Tabel '${table}' tidak ditemukan dalam database.` }
          };
        }

        return {
          jsonrpc: "2.0",
          id,
          result: {
            content: [
              {
                type: "text",
                text: JSON.stringify(this.database[table], null, 2)
              }
            ]
          }
        };
      }

      return { jsonrpc: "2.0", id, error: { code: -32601, message: `Tool '${name}' tidak dikenal.` } };
    }

    return { jsonrpc: "2.0", id, error: { code: -32601, message: `Method '${method}' tidak didukung.` } };
  }
}

// 2. MCP CLIENT IMPLEMENTATION (OPENCLAW CLIENT)
class McpClient {
  constructor(clientName, serverInstance) {
    this.clientName = clientName;
    this.server = serverInstance;
    this.requestId = 1;
    this.availableTools = [];
  }

  // 1. Initial Handshake & Tool Discovery
  async discoverTools() {
    console.log(`🔌 [MCP Client] Mengirim request 'tools/list' ke server '${this.server.serverName}'...`);
    const rpcRequest = {
      jsonrpc: "2.0",
      id: this.requestId++,
      method: "tools/list"
    };

    const response = this.server.handleJsonRpc(rpcRequest);
    this.availableTools = response.result.tools;
    console.log(`✅ [MCP Discovery] Berhasil menemukan ${this.availableTools.length} tools dari MCP Server:`);
    this.availableTools.forEach(t => console.log(`   - ${t.name}: "${t.description}"`));
    return this.availableTools;
  }

  // 2. Call Tool via JSON-RPC
  async callTool(toolName, args = {}) {
    console.log(`\n⚙️  [MCP Call] Memanggil tool '${toolName}' dengan parameter:`, JSON.stringify(args));
    const rpcRequest = {
      jsonrpc: "2.0",
      id: this.requestId++,
      method: "tools/call",
      params: {
        name: toolName,
        arguments: args
      }
    };

    const response = this.server.handleJsonRpc(rpcRequest);
    if (response.error) {
      throw new Error(`MCP Server Error (${response.error.code}): ${response.error.message}`);
    }

    return response.result.content[0].text;
  }
}

// ======================= PENGUJIAN SKENARIO =======================
async function runLab() {
  console.log("===================================================================");
  console.log("🛠️  PENGUJIAN MODEL CONTEXT PROTOCOL (MCP) INTERACTION");
  console.log("===================================================================\n");

  const server = new McpDatabaseServer("LocalPostgresMcp");
  const client = new McpClient("OpenClawGateway", server);

  // 1. Handshake & Penemuan Tool
  await client.discoverTools();

  // 2. Pemanggilan Tool 1: describe_tables
  const tables = await client.callTool("describe_tables");
  console.log(`📊 Hasil describe_tables: ${tables}`);

  // 3. Pemanggilan Tool 2: run_read_query untuk tabel 'users'
  const usersData = await client.callTool("run_read_query", { table: "users" });
  console.log(`👥 Hasil Query Data Users:`);
  console.log(usersData);

  // 4. Pengujian Penanganan Error: Query ke tabel yang tidak ada
  console.log("\n-------------------------------------------------------------------");
  console.log("--- Pengujian Penanganan Error MCP ---");
  try {
    await client.callTool("run_read_query", { table: "salary_secret_table" });
  } catch (err) {
    console.error(`❌ ${err.message}`);
  }

  console.log("\n===================================================================");
  console.log(" Kesimpulan:");
  console.log("1. Standar JSON-RPC 2.0 memisahkan client AI dengan server tool secara bersih.");
  console.log("2. Tool discovery memungkinkan OpenClaw mengadopsi kapabilitas baru tanpa redeploy.");
  console.log("3. Respons terstruktur mempermudah penyuntikan data kontekstual ke LLM.");
}

runLab();
