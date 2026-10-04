package com.enterprise.security.tamper

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Process
import java.io.BufferedReader
import java.io.File
import java.io.FileReader
import java.security.MessageDigest

class EnvironmentIntegrityEngine(private val context: Context) {

    companion object {
        // Hash SHA-256 Release Signing Certificate tim internal
        private const val EXPECTED_SIGNATURE_SHA256 = 
            "E3:B0:C4:42:98:FC:1C:14:9A:FB:F4:C8:99:6F:B9:24:27:AE:41:E4:64:9B:93:4C:A4:95:99:1B:78:52:B8:55"
        
        private val KNOWN_ROOT_PATHS = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su"
        )
    }

    fun verifyCompleteSystemIntegrity(): Boolean {
        if (isRootedDevice()) return false
        if (isFridaHookingDetected()) return false
        if (!validateAppSignature()) return false
        return true
    }

    private fun isRootedDevice(): Boolean {
        val buildTags = Build.TAGS
        if (buildTags != null && buildTags.contains("test-keys")) {
            return true
        }

        for (path in KNOWN_ROOT_PATHS) {
            if (File(path).exists()) return true
        }

        // Cek command execution probe
        var process: java.lang.Process? = null
        return try {
            process = Runtime.getRuntime().exec(arrayOf("/system/xbin/which", "su"))
            val reader = BufferedReader(java.io.InputStreamReader(process.inputStream))
            reader.readLine() != null
        } catch (t: Throwable) {
            false
        } finally {
            process?.destroy()
        }
    }

    /**
     * Membaca memory mapping dari Linux `/proc/self/maps`
     * Jika Frida diinjeksi via frida-server atau gadget, modul libc frida atau ptrace port akan tertera di mapping.
     */
    private fun isFridaHookingDetected(): Boolean {
        return try {
            val pid = Process.myPid()
            val mapsFile = File("/proc/$pid/maps")
            if (!mapsFile.exists()) return false

            BufferedReader(FileReader(mapsFile)).use { reader ->
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    val currentLine = line?.lowercase() ?: continue
                    if (currentLine.contains("frida") || 
                        currentLine.contains("gadget") || 
                        currentLine.contains("gum-js-loop")) {
                        return true
                    }
                }
            }
            false
        } catch (e: Exception) {
            // Jika access /proc di-block oleh kernel sandbox yang sangat ketat, anggap aman atau log
            false
        }
    }

    @Suppress("DEPRECATION")
    private fun validateAppSignature(): Boolean {
        return try {
            val packageManager = context.packageManager
            val packageName = context.packageName

            val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val packageInfo = packageManager.getPackageInfo(
                    packageName, 
                    PackageManager.GET_SIGNING_CERTIFICATES
                )
                packageInfo.signingInfo?.apkContentsSigners
            } else {
                val packageInfo = packageManager.getPackageInfo(
                    packageName, 
                    PackageManager.GET_SIGNATURES
                )
                packageInfo.signatures
            }

            if (signatures.isNullOrEmpty()) return false

            val currentCertBytes = signatures[0].toByteArray()
            val md = MessageDigest.getInstance("SHA-256")
            val digest = md.digest(currentCertBytes)
            val currentSignatureHash = bytesToHex(digest)

            currentSignatureHash.equals(EXPECTED_SIGNATURE_SHA256, ignoreCase = true)
        } catch (e: Exception) {
            false
        }
    }

    private fun bytesToHex(bytes: ByteArray): String {
        return bytes.joinToString(":") { String.format("%02X", it) }
    }
}
