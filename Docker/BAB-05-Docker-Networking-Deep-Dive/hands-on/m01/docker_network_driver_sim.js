/**
 * Docker Network Drivers & iptables DNAT Port Forwarder Simulator
 * Hands-on Lab: BAB 05 - Module 01
 * 
 * Demonstrates:
 * 1. Network Driver Behaviors: bridge, host, none.
 * 2. iptables DNAT (Destination NAT) packet translation.
 * 3. Security Check: Public (0.0.0.0) vs Localhost-only (127.0.0.1) Port Binding.
 */

class MockNetworkNamespace {
  constructor(name, driver = 'bridge', hostIp = '192.168.1.50') {
    this.name = name;
    this.driver = driver;
    this.hostIp = hostIp;
    this.interfaces = {};
    this.setupInterfaces();
  }

  setupInterfaces() {
    if (this.driver === 'none') {
      this.interfaces = { 'lo': '127.0.0.1/8' };
    } else if (this.driver === 'host') {
      this.interfaces = {
        'lo': '127.0.0.1/8',
        'eth0': `${this.hostIp}/24 (Direct Host Interface)`
      };
    } else if (this.driver === 'bridge') {
      const randomOctet = Math.floor(2 + Math.random() * 250);
      this.interfaces = {
        'lo': '127.0.0.1/8',
        'eth0': `172.17.0.${randomOctet}/16 (Virtual veth endpoint via docker0)`
      };
    }
  }

  canReachInternet() {
    return this.driver === 'bridge' || this.driver === 'host';
  }
}

class IptablesDNATRouter {
  constructor(hostIp = '192.168.1.50') {
    this.hostIp = hostIp;
    this.dnatRules = []; // Array of { bindIp, hostPort, containerIp, containerPort }
  }

  addPortMapping(bindIp, hostPort, containerIp, containerPort) {
    this.dnatRules.push({ bindIp, hostPort, containerIp, containerPort });
    console.log(`[iptables -t nat -A DOCKER] Added DNAT Rule: ${bindIp}:${hostPort} ──> ${containerIp}:${containerPort}`);
  }

  routePacket(clientIp, targetIp, targetPort) {
    console.log(`\n📨 [Incoming Packet] From ${clientIp} to ${targetIp}:${targetPort}`);

    // Check if target matches host
    if (targetIp !== this.hostIp && targetIp !== '127.0.0.1') {
      console.error(`❌ [Drop] Target IP ${targetIp} does not belong to host.`);
      return false;
    }

    // Find matching DNAT rule
    const rule = this.dnatRules.find(r => r.hostPort === targetPort);
    if (!rule) {
      console.error(`❌ [Connection Refused] No container listening on port ${targetPort}`);
      return false;
    }

    // Check binding security (127.0.0.1 restriction)
    if (rule.bindIp === '127.0.0.1' && clientIp !== '127.0.0.1' && clientIp !== 'localhost') {
      console.error(`🛡️  [SECURITY BLOCKED] Port ${targetPort} is strictly bound to 127.0.0.1! External IP ${clientIp} rejected.`);
      return false;
    }

    console.log(`⚡ [iptables DNAT Applied] Rewriting packet destination to: ${rule.containerIp}:${rule.containerPort}`);
    console.log(`✅ [Packet Delivered] Container on ${rule.containerIp} successfully processed the request.`);
    return true;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🌐 DOCKER NETWORK DRIVERS & IPTABLES SIMULATOR`);
  console.log(`======================================================\n`);

  // PART 1: Comparing Network Drivers
  console.log(`--- PART 1: NETWORK DRIVERS INTERFACE INSPECTION ---`);
  const cBridge = new MockNetworkNamespace('web-bridge', 'bridge');
  const cHost = new MockNetworkNamespace('webrtc-host', 'host');
  const cNone = new MockNetworkNamespace('crypto-none', 'none');

  console.log(`1. Bridge Driver:`, cBridge.interfaces, `| Internet: ${cBridge.canReachInternet()}`);
  console.log(`2. Host Driver  :`, cHost.interfaces, `| Internet: ${cHost.canReachInternet()}`);
  console.log(`3. None Driver  :`, cNone.interfaces, `| Internet: ${cNone.canReachInternet()}`);

  // PART 2: iptables DNAT Port Forwarding Engine
  console.log(`\n--- PART 2: IPTABLES PORT FORWARDING & BINDING SECURITY ---`);
  const router = new IptablesDNATRouter('192.168.1.50');

  // Rule 1: Public web server (-p 8080:80 / default 0.0.0.0)
  router.addPortMapping('0.0.0.0', 8080, '172.17.0.2', 80);

  // Rule 2: Secure database bound strictly to localhost (-p 127.0.0.1:5432:5432)
  router.addPortMapping('127.0.0.1', 5432, '172.17.0.3', 5432);

  // Test Case A: External client connects to public web server
  console.log(`\n[Test A] External client accessing Public Web Server:`);
  router.routePacket('203.0.113.15', '192.168.1.50', 8080);

  // Test Case B: External client attempts to access secure internal database
  console.log(`\n[Test B] External attacker attempting to access Database on port 5432:`);
  router.routePacket('203.0.113.15', '192.168.1.50', 5432);

  // Test Case C: Local admin script accesses database via localhost
  console.log(`\n[Test C] Localhost admin script accessing Database on port 5432:`);
  router.routePacket('127.0.0.1', '127.0.0.1', 5432);

  console.log(`\n🎉 Docker Network Drivers & Port Forwarding Lab Complete!`);
}

runLab();
