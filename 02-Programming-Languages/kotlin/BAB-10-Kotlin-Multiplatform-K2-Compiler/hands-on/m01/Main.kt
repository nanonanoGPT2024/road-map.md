package com.enterprise.crypto

import kotlinx.cinterop.*
import platform.CoreCrypto.*
import platform.Security.SecRandomCopyBytes
import platform.Security.kSecRandomDefault
import platform.posix.size_t

@OptIn(ExperimentalForeignApi::class)
actual class PlatformAESEncryptor actual constructor(secretKeyBytes: ByteArray) {
    private val key = secretKeyBytes.copyOf()

    private companion object {
        const val IV_LENGTH_BYTES = 12
        const val TAG_LENGTH_BYTES = 16
    }

    actual fun encrypt(plaintext: ByteArray): EncryptedPayload {
        val iv = ByteArray(IV_LENGTH_BYTES)
        val randomStatus = iv.usePinned { pinnedIv ->
            SecRandomCopyBytes(kSecRandomDefault, IV_LENGTH_BYTES.convert(), pinnedIv.addressOf(0))
        }
        check(randomStatus == 0) { "SecRandomCopyBytes gagal menghasilkan IV yang aman: $randomStatus" }

        val ciphertext = ByteArray(plaintext.size)
        val tag = ByteArray(TAG_LENGTH_BYTES)

        memScoped {
            val keyPtr = key.refTo(0).getPointer(this)
            val ivPtr = iv.refTo(0).getPointer(this)
            val plainPtr = if (plaintext.isNotEmpty()) plaintext.refTo(0).getPointer(this) else null
            val cipherPtr = if (ciphertext.isNotEmpty()) ciphertext.refTo(0).getPointer(this) else null
            val tagPtr = tag.refTo(0).getPointer(this)

            val status = CCCryptorGCM(
                kCCEncrypt,
                kCCAlgorithmAES,
                keyPtr,
                key.size.convert<size_t>(),
                ivPtr,
                iv.size.convert<size_t>(),
                null,
                0.convert<size_t>(),
                plainPtr,
                plaintext.size.convert<size_t>(),
                cipherPtr,
                tagPtr,
                TAG_LENGTH_BYTES.convert<size_t>()
            )

            check(status == kCCSuccess) { "Kompilasi CCCryptorGCM Enkripsi Gagal dengan status: $status" }
        }

        return EncryptedPayload(ciphertext, iv, tag)
    }

    actual fun decrypt(payload: EncryptedPayload): ByteArray {
        val plaintext = ByteArray(payload.ciphertext.size)

        memScoped {
            val keyPtr = key.refTo(0).getPointer(this)
            val ivPtr = payload.iv.refTo(0).getPointer(this)
            val cipherPtr = if (payload.ciphertext.isNotEmpty()) payload.ciphertext.refTo(0).getPointer(this) else null
            val tagPtr = payload.authenticationTag.refTo(0).getPointer(this)
            val plainPtr = if (plaintext.isNotEmpty()) plaintext.refTo(0).getPointer(this) else null

            // CCCryptorGCMOneshot / CCCryptorGCM (kCCDecrypt)
            val status = CCCryptorGCM(
                kCCDecrypt,
                kCCAlgorithmAES,
                keyPtr,
                key.size.convert<size_t>(),
                ivPtr,
                payload.iv.size.convert<size_t>(),
                null,
                0.convert<size_t>(),
                cipherPtr,
                payload.ciphertext.size.convert<size_t>(),
                plainPtr,
                tagPtr,
                payload.authenticationTag.size.convert<size_t>()
            )

            check(status == kCCSuccess) { "Kompilasi CCCryptorGCM Dekripsi Gagal atau Mac GCM mismatch: $status" }
        }

        return plaintext
    }
}
