+===================================================================================================+
|                                    LEGACY BRIDGE ARCHITECTURE                                     |
+===================================================================================================+
 [JS Thread]                                                                         [Native Thread]
      |                                                                                     |
      | 1. Invoke NativeMethod(payload)                                                     |
      | 2. JSON.stringify(payload)                                                          |
      | 3. Push ke MessageQueue Batch                                                       |
      +--------------> [ BRIDGE SERIALIZATION PIPE (JSON String Buffer) ] ----------------->+
                                                                                            | 4. Flush Buffer
                                                                                            | 5. JSON.parse(payload)
                                                                                            | 6. Thread Switch: Background/UI
                                                                                            | 7. Eksekusi Java/ObjC Method
                                                                                            | 8. Hasil di-JSON.stringify
      +<------------- [ BRIDGE SERIALIZATION PIPE (JSON String Buffer) ] <------------------+
      | 9. Deserialize & Resolve Promise                                                    
      v                                                                                     

+===================================================================================================+
|                                  MODERN JSI / TURBOMODULE RUNTIME                                 |
+===================================================================================================+
 [JavaScript Virtual Machine (Hermes / V8)]
  |
  |-- Global Context
       |
       +-- jsObject = global.TurboModuleRegistry.getEnforcing('CustomCryptoModule')
            |
            | (JavaScript Engine memegang jsi::Object yang membungkus jsi::HostObject)
            |
            v
 [JSI Abstraction Layer (C++)]
  |
  |---> Eksekusi: jsObject.computeSHA256("payload")
  |     - Direct Virtual Method Call (vtable pointer lookup)
  |     - Argumen dilewatkan sebagai const jsi::Value& (No Serialization!)
  |
  +---> [C++ Implementation Class: NativeCustomCryptoHostObject : public jsi::HostObject]
         |
         |---> [Opsi 1: Eksekusi Langsung C++ Engine (Synchronous)]
         |     - Zero Bridge overhead
         |     - Zero Context Switch latency
         |     - Return jsi::String (Ref pointer dibuat langsung di JS Heap)
         |
         |---> [Opsi 2: Offload Task via Thread Pool (Asynchronous via Promise)]
               - Eksekusi thread: std::async / ThreadPool / Native WorkQueue
               - Return: jsi::Value yang membungkus instance Promise
               - Resolve via Native JSI Runtime Runner
