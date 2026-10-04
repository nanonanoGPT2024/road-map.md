/**
 * Docker Embedded DNS (127.0.0.11) & Multi-Tier Network Segmentation Simulator
 * Hands-on Lab: BAB 05 - Module 02
 * 
 * Demonstrates:
 * 1. Docker Embedded DNS resolution (127.0.0.11) by container name.
 * 2. Multi-Tier Network Segmentation (frontend-net vs backend-net).
 * 3. Dual-homed Gateway routing & Zero-Trust database isolation.
 */

class DockerNetwork {
  constructor(name, subnet) {
    this.name = name;
    this.subnet = subnet;
    this.connectedContainers = new Map(); // containerName -> ip
    this.dnsTable = new Map(); // hostname/alias -> ip
  }

  attachContainer(containerName, ip, aliases = []) {
    this.connectedContainers.set(containerName, ip);
    this.dnsTable.set(containerName, ip);
    aliases.forEach(alias => this.dnsTable.set(alias, ip));
    console.log(`🔌 [Network: ${this.name}] Attached '${containerName}' with IP ${ip}`);
  }

  resolveDns(queryName) {
    if (this.dnsTable.has(queryName)) {
      const resolvedIp = this.dnsTable.get(queryName);
      console.log(`🔍 [Docker DNS 127.0.0.11] Resolved '${queryName}' ──> ${resolvedIp} (in ${this.name})`);
      return resolvedIp;
    }
    console.warn(`⚠️  [Docker DNS 127.0.0.11] NXDOMAIN: '${queryName}' not found in network '${this.name}'!`);
    return null;
  }
}

class NetworkNode {
  constructor(name) {
    this.name = name;
    this.attachments = new Map(); // networkName -> { network, ip }
  }

  joinNetwork(network, ip, aliases = []) {
    this.attachments.set(network.name, { network, ip });
    network.attachContainer(this.name, ip, aliases);
  }

  sendPing(targetHostname) {
    console.log(`\n📡 [${this.name}] Initiating ping to '${targetHostname}'...`);

    // Container queries Docker DNS on its attached networks
    for (const { network, ip: senderIp } of this.attachments.values()) {
      const targetIp = network.resolveDns(targetHostname);
      if (targetIp) {
        console.log(`⚡ [Packet Transmission] [${this.name} (${senderIp})] ──(ICMP Echo via ${network.name})──> [${targetHostname} (${targetIp})]`);
        console.log(`✅ [64 bytes from ${targetIp}] seq=1 ttl=64 time=0.072ms. PING SUCCESS!`);
        return true;
      }
    }

    console.error(`❌ [PING FAILED] Destination '${targetHostname}' is UNREACHABLE from '${this.name}'!`);
    console.error(`   ↳ Reason: Target does not share any common network with sender.`);
    return false;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🌐 DOCKER EMBEDDED DNS & NETWORK SEGMENTATION LAB`);
  console.log(`======================================================\n`);

  // PART 1: Create 2 Segmented User-Defined Bridge Networks
  const frontendNet = new DockerNetwork('frontend-net', '172.28.1.0/24');
  const backendNet = new DockerNetwork('backend-net', '172.28.2.0/24');

  // PART 2: Instantiate 3-Tier Microservice Containers
  console.log(`--- SETTING UP 3-TIER ARCHITECTURE ---`);
  const webClient = new NetworkNode('web-frontend');
  const apiGateway = new NetworkNode('api-gateway');
  const database = new NetworkNode('postgres-db');

  // Attach Nodes according to Security Topology:
  // 1. Web is ONLY on frontend-net
  webClient.joinNetwork(frontendNet, '172.28.1.2');

  // 2. API Gateway is DUAL-HOMED (Connected to both networks as intermediary)
  apiGateway.joinNetwork(frontendNet, '172.28.1.3', ['api', 'gateway']);
  apiGateway.joinNetwork(backendNet, '172.28.2.3', ['api', 'gateway']);

  // 3. Database is ONLY on backend-net (Isolated from Web)
  database.joinNetwork(backendNet, '172.28.2.10', ['db', 'primary-db']);

  // PART 3: Communication & DNS Resolution Tests
  console.log(`\n======================================================`);
  console.log(`🧪 TESTING INTER-CONTAINER CONNECTIVITY & DNS`);
  console.log(`======================================================`);

  // TEST 1: Web Frontend talks to API Gateway by Container Name (Expect Success)
  console.log(`>>> TEST 1: Web Frontend calls API Gateway by Name <<<`);
  webClient.sendPing('api-gateway');

  // TEST 2: API Gateway talks to Database by Alias 'db' (Expect Success)
  console.log(`\n>>> TEST 2: API Gateway calls Database by Alias 'db' <<<`);
  apiGateway.sendPing('db');

  // TEST 3: Web Frontend attempts direct breach to Database (Expect BLOCKED / Unreachable)
  console.log(`\n>>> TEST 3: Direct Web-to-Database Connection (Security Check) <<<`);
  webClient.sendPing('postgres-db');

  console.log(`\n======================================================`);
  console.log(`🛡️  SECURITY VERIFICATION:`);
  console.log(`Database 'postgres-db' is 100% isolated from public 'web-frontend'!`);
  console.log(`Attackers compromising the frontend CANNOT pivot directly to DB.`);
  console.log(`======================================================\n`);

  console.log(`🎉 Docker Embedded DNS & Segmentation Lab Completed Successfully!`);
}

runLab();
