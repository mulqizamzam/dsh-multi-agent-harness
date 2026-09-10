# CTO-A smoke

Timestamp (UTC): 2026-09-10T14:21:02Z

Strategi caching in-memory: simpan data yang sering dibaca (hasil query, konfigurasi, objek hasil komputasi) langsung di RAM proses dengan TTL dan invalidasi berbasis event, pilih eviction policy (LRU/LFU) sesuai pola akses, dan batasi ukuran cache agar beban tidak hanya bergeser menjadi tekanan GC/OOM. Untuk deployment multi-instance, cache lokal tidak konsisten antar-node, jadi terima stale-read singkat sebagai trade-off eksplisit atau tambahkan invalidasi terkoordinasi (mis. pub/sub); ukur hit-ratio dan dampak ke p99 latency sebelum memperluas cakupan cache, karena cache yang salah sasaran justru menambah kompleksitas tanpa keuntungan performa.
