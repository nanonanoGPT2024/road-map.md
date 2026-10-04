import Foundation
import Security
import LocalAuthentication
import CryptoKit

public final class SecureEnclaveVault {
    public static let shared = SecureEnclaveVault()
    private let keyTag = "com.enterprise.vault.sepKey".data(using: .utf8)!

    private init() {}

    /// Membuat atau mengambil Secure Enclave P-256 Private Key
    public func retrieveOrCreateHardwareKey() throws -> SecureEnclave.P256.KeyAgreement.PrivateKey {
        // Cek dukungan ketersediaan SEP pada SoC perangkat
        guard SecureEnclave.isAvailable else {
            throw VaultError.secureEnclaveUnavailable
        }

        // Tentukan aturan proteksi hardware-bound dengan UserPresence (Biometric / Passcode)
        var error: Unmanaged<CFError>?
        guard let accessControl = SecAccessControlCreateWithFlags(
            kCFAllocatorDefault,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            [.privateKeyUsage, .biometryCurrentSet],
            &error
        ) else {
            throw VaultError.accessControlCreationFailed(error?.takeRetainedValue())
        }

        // Cek apakah kunci sudah terdaftar di Keychain
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: keyTag,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecReturnRef as String: true
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)

        if status == errSecSuccess, let secKey = item as! SecKey? {
            // Rekonstruksi CryptoKit representation dari SecKey
            return try SecureEnclave.P256.KeyAgreement.PrivateKey(secKey: secKey)
        } else if status == errSecItemNotFound {
            // Buat kunci baru langsung di dalam Secure Enclave
            let authContext = LAContext()
            authContext.touchIDAuthenticationAllowableReuseDuration = 0 // Strict context
            
            let privateKey = try SecureEnclave.P256.KeyAgreement.PrivateKey(
                accessControl: accessControl,
                authenticationContext: authContext
            )
            
            // Simpan referensi ke Keychain
            let addQuery: [String: Any] = [
                kSecClass as String: kSecClassKey,
                kSecAttrApplicationTag as String: keyTag,
                kSecValueRef as String: privateKey.secKey!,
                kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            ]
            
            let addStatus = SecItemAdd(addQuery as CFDictionary, nil)
            guard addStatus == errSecSuccess else {
                throw VaultError.keychainPersistenceFailed(addStatus)
            }
            return privateKey
        } else {
            throw VaultError.keychainQueryFailed(status)
        }
    }
}

public enum VaultError: Error {
    case secureEnclaveUnavailable
    case accessControlCreationFailed(CFError?)
    case keychainPersistenceFailed(OSStatus)
    case keychainQueryFailed(OSStatus)
}

extension SecureEnclave.P256.KeyAgreement.PrivateKey {
    var secKey: SecKey? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
            kSecValueData as String: self.dataRepresentation,
            kSecReturnRef as String: true
        ]
        var item: CFTypeRef?
        let status = SecItemAdd(query as CFDictionary, &item)
        if status == errSecSuccess || status == errSecDuplicateItem {
            return (item as! SecKey)
        }
        return nil
    }
    
    convenience init(secKey: SecKey) throws {
        var error: Unmanaged<CFError>?
        guard let data = SecKeyCopyExternalRepresentation(secKey, &error) as Data? else {
            throw error!.takeRetainedValue()
        }
        try self.init(dataRepresentation: data)
    }
}
