/**
 * SIMULATOR: FIDO2 WebAuthn Passkeys & TOTP MFA Cryptographic Engine
 * -----------------------------------------------------------------------------
 * File: webauthn_passkey_fido2_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency, Node.js native crypto) dari seremoni
 * pendaftaran dan otentikasi Passkey (ECDSA P-256), proteksi anti-phishing (RP ID bound),
 * deteksi replay attack (counter check), serta verifier TOTP MFA (RFC 6238).
 */

const crypto = require("crypto");

// =============================================================================
// 1. SIMULATOR WEBAUTHN / PASSKEYS CEREMONIES (ECDSA P-256)
// =============================================================================

class WebAuthnServer {
  constructor(rpId, origin) {
    this.rpId = rpId; // e.g. "portal.perusahaan.com"
    this.origin = origin; // e.g. "https://portal.perusahaan.com"
    this.pendingChallenges = new Map(); // userId -> { challenge, expiresAt }
    this.credentialsDb = new Map(); // credentialId -> { userId, publicKeyPem, counter }
  }

  // Langkah 1: Buat Opsi Registrasi
  createRegistrationOptions(userId, username) {
    const challenge = crypto.randomBytes(32).toString("base64url");
    this.pendingChallenges.set(userId, {
      challenge,
      expiresAt: Date.now() + 5 * 60 * 1000,
    });

    return {
      challenge,
      rp: { name: "Enterprise Portal", id: this.rpId },
      user: { id: userId, name: username },
      pubKeyCredParams: [{ alg: -7, type: "public-key" }], // ES256
    };
  }

  // Langkah 2: Verifikasi Respon Registrasi (Simpan Public Key)
  verifyRegistration(userId, response) {
    const pending = this.pendingChallenges.get(userId);
    if (!pending || Date.now() > pending.expiresAt) {
      throw new Error("Challenge registrasi tidak ditemukan atau telah kadaluwarsa");
    }

    if (response.clientData.challenge !== pending.challenge) {
      throw new Error("Challenge mismatch: Tanda tangan registrasi tidak sah");
    }

    if (response.clientData.origin !== this.origin) {
      throw new Error(`Origin mismatch: ${response.clientData.origin} != ${this.origin}`);
    }

    // Simpan public key di database server (Private key tetap ada di chip hardware client!)
    this.credentialsDb.set(response.credentialId, {
      userId,
      publicKeyPem: response.publicKeyPem,
      counter: 0,
    });

    this.pendingChallenges.delete(userId);
    return { verified: true, credentialId: response.credentialId };
  }

  // Langkah 3: Buat Opsi Login (Challenge Baru)
  createAuthenticationOptions(userId) {
    const challenge = crypto.randomBytes(32).toString("base64url");
    this.pendingChallenges.set(userId, {
      challenge,
      expiresAt: Date.now() + 5 * 60 * 1000,
    });

    return {
      challenge,
      rpId: this.rpId,
      timeout: 60000,
    };
  }

  // Langkah 4: Verifikasi Assertion Tanda Tangan Biometrik
  verifyAuthentication(userId, response) {
    const pending = this.pendingChallenges.get(userId);
    if (!pending || Date.now() > pending.expiresAt) {
      throw new Error("Challenge login telah kadaluwarsa");
    }

    const cred = this.credentialsDb.get(response.credentialId);
    if (!cred || cred.userId !== userId) {
      throw new Error("Kredensial Passkey tidak terdaftar untuk pengguna ini");
    }

    // A. Verifikasi Origin & RP ID (Perlindungan Terhadap Phishing!)
    if (response.clientData.origin !== this.origin) {
      throw new Error(`[ANTI-PHISHING AKTIF] Domain ${response.clientData.origin} ditolak! RP ID resmi adalah ${this.rpId}`);
    }

    // B. Verifikasi Challenge
    if (response.clientData.challenge !== pending.challenge) {
      throw new Error("Challenge mismatch");
    }

    // C. Verifikasi Counter (Perlindungan Terhadap Replay Attack!)
    if (response.counter <= cred.counter) {
      throw new Error(`[REPLAY ATTACK TERDETEKSI] Counter ${response.counter} tidak lebih besar dari counter tersimpan ${cred.counter}!`);
    }

    // D. Verifikasi Tanda Tangan Kriptografis ECDSA P-256
    const dataToVerify = Buffer.concat([
      Buffer.from(response.authenticatorData, "utf-8"),
      crypto.createHash("sha256").update(JSON.stringify(response.clientData)).digest(),
    ]);

    const verify = crypto.createVerify("SHA256");
    verify.update(dataToVerify);
    const isValidSignature = verify.verify(cred.publicKeyPem, Buffer.from(response.signature, "base64url"));

    if (!isValidSignature) {
      throw new Error("Tanda tangan biometrik tidak valid secara matematis!");
    }

    // Update counter untuk mencegah replay
    cred.counter = response.counter;
    this.pendingChallenges.delete(userId);

    return { verified: true, message: "Otentikasi biometrik berhasil!" };
  }
}

// Simulator Perangkat Keras Pengguna (Secure Enclave / TPM)
class AuthenticatorHardwareSimulator {
  constructor(deviceName) {
    this.deviceName = deviceName;
    this.keyPair = null;
    this.credentialId = `cred_${crypto.randomBytes(8).toString("hex")}`;
    this.counter = 0;
  }

  // Registrasi: Generate pasangan kunci asimetris
  register(options, currentOrigin) {
    // Generate ECDSA P-256 Keypair di chip aman
    this.keyPair = crypto.generateKeyPairSync("ec", {
      namedCurve: "prime256v1",
      publicKeyEncoding: { type: "spki", format: "pem" },
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
    });

    const clientData = {
      type: "webauthn.create",
      challenge: options.challenge,
      origin: currentOrigin,
    };

    return {
      credentialId: this.credentialId,
      publicKeyPem: this.keyPair.publicKey,
      clientData,
    };
  }

  // Login: Tandatangani challenge menggunakan Private Key
  authenticate(options, currentOrigin) {
    this.counter++;
    const clientData = {
      type: "webauthn.get",
      challenge: options.challenge,
      origin: currentOrigin,
    };

    const authenticatorData = `authData:${options.rpId}:flags:userVerified`;
    const dataToSign = Buffer.concat([
      Buffer.from(authenticatorData, "utf-8"),
      crypto.createHash("sha256").update(JSON.stringify(clientData)).digest(),
    ]);

    const sign = crypto.createSign("SHA256");
    sign.update(dataToSign);
    const signature = sign.sign(this.keyPair.privateKey, "base64url");

    return {
      credentialId: this.credentialId,
      counter: this.counter,
      authenticatorData,
      clientData,
      signature,
    };
  }
}

// =============================================================================
// 2. SIMULATOR TOTP (RFC 6238) MFA ENGINE
// =============================================================================

class TOTPEngine {
  // Generate 6 digit token untuk interval waktu tertentu
  static generateCode(secret, timeStep = Math.floor(Date.now() / 30000)) {
    const timeBuffer = Buffer.alloc(8);
    timeBuffer.writeBigInt64BE(BigInt(timeStep));

    const hmac = crypto.createHmac("sha1", secret).update(timeBuffer).digest();
    // Dynamic truncation ala RFC 4226 / 6238
    const offset = hmac[hmac.length - 1] & 0xf;
    const binary =
      ((hmac[offset] & 0x7f) << 24) |
      ((hmac[offset + 1] & 0xff) << 16) |
      ((hmac[offset + 2] & 0xff) << 8) |
      (hmac[offset + 3] & 0xff);

    const otp = binary % 1000000;
    return otp.toString().padStart(6, "0");
  }

  // Verifikasi token dengan toleransi pergeseran waktu (+/- 1 jendela 30 detik)
  static verifyCode(secret, userCode) {
    const currentStep = Math.floor(Date.now() / 30000);
    for (let offset = -1; offset <= 1; offset++) {
      const validCode = this.generateCode(secret, currentStep + offset);
      if (validCode === userCode) return true;
    }
    return false;
  }
}

// =============================================================================
// 3. RUN SIMULATION SUITE
// =============================================================================

function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: FIDO2 WEBAUTHN PASSKEYS & TOTP MULTI-FACTOR ENGINE");
  console.log("===========================================================================\n");

  const server = new WebAuthnServer("portal.perusahaan.com", "https://portal.perusahaan.com");
  const userDevice = new AuthenticatorHardwareSimulator("Apple MacBook Pro TouchID");

  const userId = "usr_ceo_001";
  const userEmail = "ceo@perusahaan.com";

  // SKENARIO 1: SEREMONI REGISTRASI PASSKEY
  console.log("--- SKENARIO 1: Seremoni Pendaftaran Passkey Biometrik ---");
  const regOptions = server.createRegistrationOptions(userId, userEmail);
  console.log(`  1. Server menerbitkan Challenge: ${regOptions.challenge.substring(0, 16)}...`);

  // Pengguna memindai sidik jari TouchID pada origin yang sah
  const regResponse = userDevice.register(regOptions, "https://portal.perusahaan.com");
  console.log(`  2. Device ${userDevice.deviceName} membuat ECDSA P-256 Keypair.`);
  console.log(`     Credential ID: ${regResponse.credentialId}`);

  const regResult = server.verifyRegistration(userId, regResponse);
  console.log(`  3. Server memvalidasi dan menyimpan Public Key.`);
  console.log(`  ✅ [REGISTRASI SUKSES] Status: ${regResult.verified}\n`);

  // SKENARIO 2: SEREMONI LOGIN DENGAN PASSKEY RESMI
  console.log("--- SKENARIO 2: Seremoni Login Bebas Kata Sandi (Passkey Assertion) ---");
  const authOptions = server.createAuthenticationOptions(userId);
  console.log(`  1. Server menerbitkan Challenge Login: ${authOptions.challenge.substring(0, 16)}...`);

  const authResponse = userDevice.authenticate(authOptions, "https://portal.perusahaan.com");
  console.log(`  2. Pengguna memindai TouchID. Counter Hardware: ${authResponse.counter}`);

  const authResult = server.verifyAuthentication(userId, authResponse);
  console.log(`  3. Server memverifikasi signature matematika ECDSA.`);
  console.log(`  ✅ [LOGIN BERHASIL] ${authResult.message}\n`);

  // SKENARIO 3: SERANGAN PHISHING (ORIGIN MISMATCH)
  console.log("--- SKENARIO 3: Simulasi Serangan Phishing Domain Palsu ---");
  console.log("  ⚠️  Korban dijebak membuka situs tiruan: 'https://portal-perusahaan-login.xyz'...");
  const phishAuthOptions = server.createAuthenticationOptions(userId);

  // Perangkat keras menandatangani atas nama origin palsu
  const phishResponse = userDevice.authenticate(phishAuthOptions, "https://portal-perusahaan-login.xyz");
  try {
    server.verifyAuthentication(userId, phishResponse);
  } catch (err) {
    console.log(`  🛡️  [SERANGAN DITANGKAL SECARA OTOMATIS]`);
    console.log(`     Pesan Server: ${err.message}\n`);
  }

  // SKENARIO 4: SERANGAN REPLAY ATTACK (MENGIRIM ULANG SIGNATURE LAMA)
  console.log("--- SKENARIO 4: Simulasi Replay Attack (Mencegat & Mengirim Response Lama) ---");
  console.log("  ⚠️  Penyerang mencoba mengirim kembali authResponse dari Skenario 2...");
  try {
    // Server generate challenge baru tapi penyerang menyuntikkan response lama (counter <= storedCounter)
    server.pendingChallenges.set(userId, { challenge: authResponse.clientData.challenge, expiresAt: Date.now() + 60000 });
    server.verifyAuthentication(userId, authResponse);
  } catch (err) {
    console.log(`  🛡️  [SERANGAN DITANGKAL SECARA OTOMATIS]`);
    console.log(`     Pesan Server: ${err.message}\n`);
  }

  // SKENARIO 5: TOTP MFA ENGINE TEST (RFC 6238)
  console.log("--- SKENARIO 5: Generator & Verifier TOTP MFA (6-Digit Code) ---");
  const totpSecret = "KUNCI_RAHASIA_MFA_ENTERPRISE_BASE32";
  const currentCode = TOTPEngine.generateCode(totpSecret);
  console.log(`  Aplikasi Google Authenticator menampilkan: [ ${currentCode} ]`);

  const isValidCode = TOTPEngine.verifyCode(totpSecret, currentCode);
  console.log(`  Verifikasi Kode Server : ${isValidCode ? "SAH & DITERIMA ✅" : "DITOLAK ❌"}`);

  const isInvalidCode = TOTPEngine.verifyCode(totpSecret, "000111");
  console.log(`  Verifikasi Kode Salah ('000111') : ${isInvalidCode ? "DITERIMA" : "DITOLAK DENGAN BENAR 🛡️"}\n`);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Arsitektur Keamanan Passwordless & MFA 100% Solid!");
  console.log("===========================================================================");
}

runSimulation();
