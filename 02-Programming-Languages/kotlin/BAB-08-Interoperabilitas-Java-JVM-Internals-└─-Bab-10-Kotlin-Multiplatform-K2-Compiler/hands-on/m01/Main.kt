package com.bank.core

import java.io.IOException
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.PKCS8EncodedKeySpec

actual class NativeCryptoEngine {

    @Throws(BankSecurityException::class, IOException::class)
    @JvmName("signTransactionPayload")
    actual fun signPayload(payload: ByteArray, privateKeyDer: ByteArray): TransactionSignature {
        if (payload.isEmpty()) {
            throw InvalidPayloadException("Payload transaksi kosong.")
        }

        try {
            val keySpec = PKCS8EncodedKeySpec(privateKeyDer)
            val kf = KeyFactory.getInstance("RSA")
            val privateKey = kf.generatePrivate(keySpec)

            val sig = Signature.getInstance("SHA256withRSA")
            sig.initSign(privateKey)
            sig.update(payload)
            val signatureBytes = sig.sign()

            // Mengonversi byte array ke Hex string secara efisien
            val hexString = signatureBytes.joinToString("") { "%02x".format(it) }
            return TransactionSignature(hexString)
        } catch (e: Exception) {
            throw BankSecurityException("Gagal menandatangani payload: ${e.message}", e)
        }
    }
}
