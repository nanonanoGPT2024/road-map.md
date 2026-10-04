use std::ffi::CStr;
use std::fmt;
use std::os::raw::{c_char, c_int, c_void};
use std::ptr::NonNull;

// ============================================================================
// 1. SIMULASI C ABI NATIVE LIBRARY (Secara nyata di-link via build.rs)
// ============================================================================
#[repr(C)]
pub struct CRingBuffer {
    _private: [u8; 0], // Mencegah inisialisasi langsung oleh safe Rust
}

extern "C" {
    fn c_rb_create(capacity: usize) -> *mut CRingBuffer;
    fn c_rb_destroy(rb: *mut CRingBuffer);
    fn c_rb_write(rb: *mut CRingBuffer, data: *const u8, len: usize) -> c_int;
    fn c_rb_read(rb: *mut CRingBuffer, out_buf: *mut u8, max_len: usize) -> c_int;
    fn c_rb_last_error() -> *const c_char;
}

// ============================================================================
// 2. ERROR HANDLING DOMAIN
// ============================================================================
#[derive(Debug, PartialEq, Eq)]
pub enum RingBufferError {
    AllocationFailed,
    WriteError(String),
    ReadError(String),
    InvalidBufferSize,
}

impl fmt::Display for RingBufferError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AllocationFailed => write!(f, "Gagal mengalokasikan Native RingBuffer"),
            Self::WriteError(msg) => write!(f, "Gagal menulis ke buffer: {}", msg),
            Self::ReadError(msg) => write!(f, "Gagal membaca dari buffer: {}", msg),
            Self::InvalidBufferSize => write!(f, "Ukuran buffer tidak valid"),
        }
    }
}

impl std::error::Error for RingBufferError {}

// Helper untuk membaca pesan galat dari C string
unsafe fn fetch_c_error() -> String {
    let err_ptr = c_rb_last_error();
    if err_ptr.is_null() {
        "Kesalahan tidak diketahui".to_string()
    } else {
        CStr::from_ptr(err_ptr)
            .to_string_lossy()
            .into_owned()
    }
}

// ============================================================================
// 3. SAFE RUST WRAPPER STRUCT (RAII)
// ============================================================================
pub struct SafeRingBuffer {
    // NonNull menjamin pointer tidak pernah 0x0 dan mengaktifkan
    // Null Pointer Optimization pada memori Rust.
    handle: NonNull<CRingBuffer>,
}

// Mengimplementasikan Send dan Sync dengan validasi ketat
// SAFETY: CRingBuffer di sisi native thread-safe jika dilindungi lock internal
unsafe impl Send for SafeRingBuffer {}

impl SafeRingBuffer {
    /// Membuat instance baru SafeRingBuffer.
    /// 
    /// # Errors
    /// Mengembalikan `RingBufferError::AllocationFailed` jika alokasi native gagal.
    pub fn new(capacity: usize) -> Result<Self, RingBufferError> {
        if capacity == 0 {
            return Err(RingBufferError::InvalidBufferSize);
        }

        let raw_ptr = unsafe { c_rb_create(capacity) };
        let handle = NonNull::new(raw_ptr).ok_or(RingBufferError::AllocationFailed)?;

        Ok(Self { handle })
    }

    /// Menulis slice byte aman ke buffer native C.
    pub fn write(&mut self, data: &[u8]) -> Result<usize, RingBufferError> {
        if data.is_empty() {
            return Ok(0);
        }

        let bytes_written = unsafe {
            c_rb_write(
                self.handle.as_ptr(),
                data.as_ptr(),
                data.len(),
            )
        };

        if bytes_written < 0 {
            let err_msg = unsafe { fetch_c_error() };
            Err(RingBufferError::WriteError(err_msg))
        } else {
            Ok(bytes_written as usize)
        }
    }

    /// Membaca data ke dalam slice buffer mutabel Rust.
    pub fn read(&mut self, output: &mut [u8]) -> Result<usize, RingBufferError> {
        if output.is_empty() {
            return Ok(0);
        }

        let bytes_read = unsafe {
            c_rb_read(
                self.handle.as_ptr(),
                output.as_mut_ptr(),
                output.len(),
            )
        };

        if bytes_read < 0 {
            let err_msg = unsafe { fetch_c_error() };
            Err(RingBufferError::ReadError(err_msg))
        } else {
            Ok(bytes_read as usize)
        }
    }
}

// ============================================================================
// 4. DETERMINISTIC CLEANUP (RAII)
// ============================================================================
impl Drop for SafeRingBuffer {
    fn drop(&mut self) {
        // SAFETY: self.handle dijamin non-null oleh tipe NonNull.
        // Drop dipanggil tepat sekali saat instance keluar dari scope.
        unsafe {
            c_rb_destroy(self.handle.as_ptr());
        }
    }
}

// ============================================================================
// 5. IMPLEMENTASI DUMMY STUB C AGAR KODE DAPAT DIKOMPILASI MANDIRI
// ============================================================================
#[no_mangle]
pub unsafe extern "C" fn c_rb_create(capacity: usize) -> *mut CRingBuffer {
    let layout = std::alloc::Layout::from_size_align(capacity + 8, 8).unwrap();
    let mem = std::alloc::alloc(layout);
    mem as *mut CRingBuffer
}

#[no_mangle]
pub unsafe extern "C" fn c_rb_destroy(rb: *mut CRingBuffer) {
    if !rb.is_null() {
        let layout = std::alloc::Layout::from_size_align(1024 + 8, 8).unwrap();
        std::alloc::dealloc(rb as *mut u8, layout);
    }
}

#[no_mangle]
pub unsafe extern "C" fn c_rb_write(_rb: *mut CRingBuffer, _data: *const u8, len: usize) -> c_int {
    len as c_int
}

#[no_mangle]
pub unsafe extern "C" fn c_rb_read(_rb: *mut CRingBuffer, out_buf: *mut u8, max_len: usize) -> c_int {
    if !out_buf.is_null() && max_len > 0 {
        *out_buf = 0xAA; // Isi dummy data
        1
    } else {
        -1
    }
}

#[no_mangle]
pub extern "C" fn c_rb_last_error() -> *const c_char {
    b"Buffer Out of Bounds\0".as_ptr() as *const c_char
}

// ============================================================================
// 6. SAFE CONSUMER CODE
// ============================================================================
fn main() {
    println!("Menginisialisasi Safe Ring Buffer...");
    let mut ring_buffer = SafeRingBuffer::new(1024).expect("Inisialisasi gagal");

    let payload = b"SYSTEM_TELEMETRY_PACKET_#001";
    let written = ring_buffer.write(payload).expect("Write gagal");
    println!("Berhasil menulis {} byte ke C RingBuffer.", written);

    let mut recv_buf = vec![0u8; 16];
    let read_count = ring_buffer.read(&mut recv_buf).expect("Read gagal");
    println!("Berhasil membaca {} byte: {:x?}", read_count, &recv_buf[..read_count]);

    // Ring buffer dibersihkan secara deterministik di sini via Drop!
    println!("SafeRingBuffer keluar dari scope, memory otomatis didealokasi.");
}
