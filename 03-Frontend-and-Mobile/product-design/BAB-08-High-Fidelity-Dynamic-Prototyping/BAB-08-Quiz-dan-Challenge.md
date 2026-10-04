# BAB 08 — Quiz & Challenge: High-Fidelity Dynamic Prototyping

## 🎯 Tujuan
Menguji pemahaman Anda tentang konsep, best practices, dan troubleshooting dalam pembuatan High-Fidelity Dynamic Prototyping.

---

## 📝 Quiz

### Level: Basic (Konsep Inti)
1. **Apa perbedaan utama antara low-fidelity dan high-fidelity prototyping?**
2. **Sebutkan 3 tool yang sering digunakan untuk membuat high-fidelity prototype!**
3. **Mengapa interaktivitas dinamis (dynamic interactivity) penting dalam high-fidelity prototype?**
4. **Apa yang dimaksud dengan "micro-interactions" dalam konteks prototyping?**
5. **Kapan waktu yang paling tepat untuk membuat high-fidelity prototype dalam siklus product design?**

### Level: Intermediate (Mekanisme Internal & Troubleshooting)
1. **Bagaimana cara mengelola state (variabel) secara efektif dalam dynamic prototype yang kompleks (misalnya di Figma atau Protopie)?**
2. **Jelaskan perbedaan antara component-level animation dan page-level transition! Kapan Anda harus menggunakan masing-masing?**
3. **Saat melakukan user testing dengan high-fidelity prototype, pengguna mengalami lag yang parah. Apa kemungkinan penyebabnya dan bagaimana cara Anda men-debug isu tersebut?**
4. **Bagaimana cara Anda mensimulasikan input data pengguna (seperti form submission) di dalam dynamic prototype tanpa menggunakan backend sungguhan?**
5. **Apa tantangan terbesar dalam memelihara (maintaining) high-fidelity prototype seiring dengan perubahan design system? Bagaimana cara mengatasinya?**

### Level: Scenario (Kasus Nyata Produksi)
1. **Skenario A:** Anda merancang aplikasi e-commerce. Tim developer meminta prototype untuk animasi transisi dari halaman produk ke keranjang belanja yang memiliki interaksi *drag-and-drop*. Tool apa yang Anda pilih dan bagaimana cara mendokumentasikan spesifikasi animasi tersebut (timing, easing, duration) agar mudah diimplementasikan oleh engineer?
2. **Skenario B:** Saat user testing, pengguna merasa kebingungan dengan alur *checkout* karena prototype Anda tidak menyimpan status dari halaman sebelumnya (misal: total harga tidak update). Bagaimana pendekatan Anda menggunakan "Variables" atau "Conditional Logic" untuk mensimulasikan persistence state di prototype?
3. **Skenario C:** Anda membuat prototipe untuk aplikasi mobile dashboard dengan banyak chart dinamis. Prototipe saat ini sangat berat dan *crash* ketika dijalankan di perangkat mobile sungguhan. Langkah optimasi apa saja yang akan Anda lakukan untuk memastikan prototipe dapat diuji dengan lancar?

---

## 🚀 Chapter Challenge

**Tantangan: Membangun "Smart Cart" Prototype Logic**

**Deskripsi:**
Rancanglah logika (state machine) untuk prototipe keranjang belanja dinamis (Smart Cart) tanpa harus coding UI-nya. Anda harus mendefinisikan state, trigger, dan action.

**Requirements:**
1. Pengguna dapat menambah, mengurangi, dan menghapus item.
2. Jika jumlah item menjadi 0, tampilkan "Empty State".
3. Terapkan diskon 10% jika total harga melebihi Rp500.000.
4. Buat diagram alur interaksi (State-Transition Diagram).

**Constraints:**
- Jangan gunakan lebih dari 5 variabel global.
- Harus ada simulasi delay loading (skeleton screen) saat proses "Checkout" ditekan.

---

## 🧠 Knowledge Check

### Saya harus memahami
- Konsep state, variables, dan conditional logic dalam prototyping.
- Perbedaan micro-interactions dan macro-transitions.
- Cara menyiapkan prototipe untuk User Testing (UT) dan handoff ke developer.

### Saya tidak perlu menghafal
- Semua shortcut atau fitur spesifik dari satu tool (seperti Figma atau Protopie), karena tool terus berkembang.
- Nilai eksak dari *easing curves* (cukup pahami konsep bezier curve dasar).

### Saya harus bisa melakukan
- Membuat komponen interaktif yang memiliki multiple states (misal: button default, hover, pressed, disabled).
- Menyambungkan alur antar halaman dengan transisi yang natural.
- Mensimulasikan input data sederhana untuk keperluan testing.

### ✅ Checklist
- [ ] Memahami konsep High-Fidelity vs Low-Fidelity.
- [ ] Mampu mengimplementasikan Variables dan Conditional Logic.
- [ ] Bisa membuat micro-interactions yang relevan.
- [ ] Dapat melakukan debugging prototipe yang berat atau error.
- [ ] Mampu melakukan handoff animasi ke tim developer.
