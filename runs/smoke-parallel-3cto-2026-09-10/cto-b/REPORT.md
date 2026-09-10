# CTO-B smoke

Timestamp (UTC): 2026-09-10T14:20:11Z

Strategi retry dan backoff: retry hanya untuk operasi yang idempoten atau aman diulang, dengan klasifikasi error eksplisit — retryable (timeout, 429/503, gangguan jaringan transient) versus non-retryable (validasi 4xx, auth, bug logika) — lalu gunakan exponential backoff dengan full jitter (delay acak antara 0 dan base × 2^attempt) yang dibatasi interval maksimum dan jumlah attempt terbatas, agar retry tidak berubah menjadi amplifikasi beban; hormati sinyal server seperti Retry-After, sinkronkan total deadline retry dengan timeout pemanggil supaya tidak ada retry yang melewati batas permintaan, dan perlakukan retry budget sebagai sumber daya: saat error rate naik, lebih baik shed load daripada menambah tekanan pada sistem yang sudah degenerasi.
