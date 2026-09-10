# Playbook Dispatch Paralel — 100 Contoh Perintah Multi-Peran

- **Status**: dokumentasi penggunaan sisi operator (usage playbook). Bukan definisi agen, bukan konfigurasi.
- **Dibuat**: 2026-09-10, atas permintaan owner ("berikan contoh input paralel … catat semuanya dalam dokumentasi").
- **Sumber kebenaran surface tool** (semua live-verified): allow-list 15 instance di
  `$DSH_HOME/profiles/web/cordis.patch.yml` (dump 2026-09-10), probe tulis
  `runs/write-access-check-2026-09-10/`, liveness 15/15
  `runs/live-parallel-15-roles-2026-09-10/`, mapping `config/role-preset-mapping.yaml`
  (mapping_version 2), matrix `config/permissions.yaml` (matrix_version 2).

## Cara pakai

- Owner cukup memberi **tujuan** (1–2 kalimat, bahasa santai boleh). Prompt lengkap
  per subagen disusun oleh parent/orkestrator — owner tidak pernah perlu menulis prompt teknis.
- Isi `[kurung]` = diisi owner, atau diisi parent dari konteks. Ambigu → parent bertanya
  sekali atau menyatakan asumsi secara eksplisit.
- Nomor 1–100 bersifat stabil untuk dirujuk: "eksekusi contoh #57 untuk proyek X".
- Komposisi role di tiap contoh adalah **komposisi awal** berdasarkan domain peran; saat
  eksekusi nyata parent menyesuaikan ke task spesifik (role ↔ task match, bukan menghabiskan kuota).

## Aturan emas (berbasis bukti live)

1. **Role ↔ task match** — gunakan role yang relevan saja; kecepatan datang dari paralelisme,
   bukan dari banyaknya agen.
2. **Syarat paralel**: dua tugas boleh paralel jika tidak bertukar file dan tidak saling menunggu.
3. **Multi-writer** = beberapa panggilan `subagent_cto` sekaligus, **satu penulis per file/path**,
   kontrak antarmuka dipin di plan (pola terbukti: Wave paralel-2 studio, 2026-09-09).
   Commit parent wajib `git commit --only <path>` (lesson R18 — index git bersama semua agen).
4. **Reviewer/verifikator read-only** aman diserentakkan dengan pekerjaan siapa pun.
5. **Klaim & angka subagen wajib diverifikasi programatik oleh parent** sebelum dipakai.
6. **Puluhan task / multi-fase / hasil terstruktur** → minta tool `workflow` secara eksplisit.
7. Raw file-write di antara spesialis hanya `cto`; 14 role lain deny edit/write by design
   (least privilege) — kebutuhan tulis besar dialirkan ke cto atau parent, bukan dengan membuka write.

## Katalog — Batch 1–2 (1–20): dasar & proyek umum

| # | Perintah (inti) | Blok paralel |
|---|---|---|
| 1 | Riset 5 kompetitor: fitur, harga, posisi sosial | kai + cfo + somad |
| 2 | Feasibility integrasi [Y]: tren, kompatibilitas, titik integrasi | kai + scout + cto (read-only) |
| 3 | Duel opsi A vs B (mis. cache): analisis paralel + rekomendasi berbukti | cto A + cto B + atlas; badsector red-team |
| 4 | Implementasi fitur: 3 modul independen | cto ×3, path terpisah, kontrak dipin di plan + test suite |
| 5 | Review diff PR dari 4 sisi | badsector + argus + scout + talon |
| 6 | Audit proyek: arsitektur, keamanan, failure-mode | atlas + argus + tess |
| 7 | Verifikasi klaim rilis (test/angka) | parent run + vera + ledger |
| 8 | Paket peluncuran fitur: tren, sosial, biaya | kai + somad + cfo |
| 9 | Lanjut Plan 2 studio (subagent-driven) | cto paralel file-disjoint + verifikasi |
| 10 | Workflow: migrasi 30 skema, fase analisis→eksekusi→verifikasi | tool `workflow` |
| 11 | Website company profile: referensi + copy dulu, lalu implement | G1 kai + somad → G2 cto + argus |
| 12 | Brief MVP aplikasi mobile: pasar, biaya, feasibility | kai + cfo + cto |
| 13 | Business plan: pasar, unit economics, red-team asumsi | kai + cfo + badsector |
| 14 | Dashboard dari [CSV]: pipeline + UI paralel, skema dipin dulu | cto ×2 + verifikasi test |
| 15 | Upgrade framework 2 versi mayor: breaking changes, dampak, rollback | scout + cto + talon |
| 16 | 10 artikel SEO: riset keyword dulu, draft + fact-check | G1 kai → G2 nova + badsector |
| 17 | Toko online: harga kompetitor, copy, cek platform | kai + somad + scout |
| 18 | Pitch deck investor: market, proyeksi, narasi | kai + cfo + nova |
| 19 | Analisis feedback user: klaster, quick-win, biaya | kai/somad + cto + cfo |
| 20 | Modernisasi ke cloud: inventaris, risiko, biaya | zeko + tess + cfo |

## Katalog — Batch 3–4 (21–40): rekayasa, data, konten, personal

| # | Perintah (inti) | Blok paralel |
|---|---|---|
| 21 | Triage 30 laporan bug: klaster, prioritas dampak vs biaya | cto + cfo + badsector |
| 22 | Lengkapi test modul tak ter-tes: gap → tulis paralel → coverage | vera → cto ×2 → parent verifikasi |
| 23 | Post-mortem insiden: timeline, root cause, cegah-ulang | zeko + tess + ledger + badsector |
| 24 | Benchmark performa: skenario, baseline, bottleneck | cto + tess + talon |
| 25 | Desain API publik: kontrak, dokumentasi, contoh | atlas + quill + scout + cto |
| 26 | Pecah monolith: batas modul, urutan aman, rollback | atlas + tess + talon |
| 27 | Rancang CI/CD: pipeline, gate kualitas, deploy | scout + talon + zeko |
| 28 | Lokalisasi ke 5 bahasa: ekstrak → terjemah per bahasa → QA | cto → nova fan-out + quill |
| 29 | Pipeline scraping: etika/ToS, parser, jadwal | kai + argus + cto (preseden: dtf-crawl) |
| 30 | Bersihkan dataset kotor: anomali, rule, verifikasi | cto + vera + badsector |
| 31 | Kalender konten sosial 30 hari | kai + somad + cfo |
| 32 | Harga produk baru: pasar, biaya, skenario margin (2 opsi) | kai + cfo + badsector |
| 33 | Bedah iklan 3 kompetitor: kreatif, positioning, spend | somad + kai + cfo |
| 34 | Newsletter mingguan: kurasi, format, draft edisi 1 | kai + somad + nova |
| 35 | Skrip video: riset hook → outline + draft → cek klaim | kai → somad + nova → badsector |
| 36 | Whitepaper: data, struktur argumen, draft bab | kai + quill + nova + badsector |
| 37 | OKR kuartal: benchmark, metrik, red-team target | kai + cfo + badsector |
| 38 | Keputusan beli barang mahal: 3 kandidat, TCO | kai + cfo + badsector |
| 39 | Rombak CV + LinkedIn: benchmark, rewrite, cek klaim | kai + nova + vera |
| 40 | Rencanakan acara/konferensi kecil: vendor, budget, rundown | kai + cfo + somad |

## Katalog — Batch 5 (41–70): rekayasa & keandalan, data & AI, bisnis

| # | Perintah (inti) | Blok paralel |
|---|---|---|
| 41 | Security hardening pra-rilis: threat model, dep audit, secrets scan | argus + scout + cto |
| 42 | Load test & capacity: skenario beban, proyeksi kapasitas & biaya | tess + talon + cfo |
| 43 | Migrasi skema DB tanpa downtime: urutan, jalur mundur, monitoring | cto + talon + zeko |
| 44 | Observability upgrade: peta log/metrik, gap, standar baru | zeko + tess + atlas |
| 45 | Backup & DR: RTO/RPO, restore, biaya — restore diuji nyata | talon + zeko + cfo → vera |
| 46 | Feature flag rollout: tahap %, kill switch, komunikasi | talon + tess + somad |
| 47 | Runbook 5 skenario gagal: deteksi, mitigasi, eskalasi | zeko + tess → quill → vera |
| 48 | Deprecation endpoint lama: pemakai, jadwal, komunikasi | scout + quill + somad |
| 49 | Peta code ownership: modul, pemilik, area yatim | atlas + ledger + zeko |
| 50 | Build-vs-buy komponen: vendor, biaya 3 tahun, lock-in | kai + cfo + scout + badsector |
| 51 | Dependency cleanup: tak terpakai, rentan, alternatif | scout + argus + cto |
| 52 | Gabung repo A+B: batas paket, duplikasi, riwayat | atlas + scout + ledger |
| 53 | Pilih LLM untuk fitur: kualitas, biaya token, integrasi | kai + cfo + cto + badsector |
| 54 | Prompt library: format, kasus uji, kriteria eval | quill + cto + badsector + vera |
| 55 | Pipeline prediksi churn: fitur, baseline, evaluasi | cto + vera + tess |
| 56 | Kebijakan retensi log/data: kepatuhan, biaya, implementasi | quill + argus + zeko |
| 57 | Alerting metrik: threshold vs anomali, noise, eskalasi | cto + zeko + tess |
| 58 | Audit dataset latih: label, bias, provenance | vera + badsector + ledger |
| 59 | Search internal: keyword vs embedding (biaya/kualitas/kompleksitas) | cto + kai + cfo |
| 60 | Data contract sumber→konsumen: skema, jaminan, pelanggaran | quill + atlas + vera |
| 61 | Masuk pasar wilayah baru: kompetitor lokal, regulasi, biaya | kai + cfo + badsector |
| 62 | Rencana efisiensi biaya: kandidat, dampak, risiko | cfo + zeko + badsector |
| 63 | Due diligence partner/vendor: track record, finansial, ketergantungan | kai + cfo + argus + badsector |
| 64 | Segmentasi pelanggan: klaster, nilai, aksi per segmen | kai + cfo + somad |
| 65 | Playbook retensi/churn: sinyal, intervensi, pengukuran | cto + cfo + somad |
| 66 | Crisis comms playbook: skenario, template, jalur approval | somad + quill + badsector |
| 67 | Roadmap produk 6 bulan dari 3 input → satu prioritas | kai/somad + atlas + badsector → sintesis |
| 68 | Evaluasi channel marketplace/B2B: biaya, operasional, potensi | somad + kai + cfo |
| 69 | Post-launch review 90 hari: klaim vs metrik, sinyal sosial | vera + somad + ledger + badsector |
| 70 | Nilai buka cabang: pasar lokal, biaya, operasional | kai + cfo + zeko + badsector |

## Katalog — Batch 6 (71–100): konten, personal, organisasi

| # | Perintah (inti) | Blok paralel |
|---|---|---|
| 71 | Nama + tagline brand: 20 kandidat, cek domain, asosiasi | nova + somad + kai + scout |
| 72 | Storyboard kampanye video: konsep, shot list, estimasi | somad + nova + cfo |
| 73 | E-book 10 halaman: outline → draft bab paralel → editor | kai → nova fan-out + badsector → rakit |
| 74 | Podcast pilot: posisi pasar, format, naskah ep. 1 | kai + somad + nova |
| 75 | Template review bebas bias: kriteria, skoring, uji ulang | kai + badsector + nova |
| 76 | Terjemahan dokumen panjang: glosarium → per bagian → QA | quill → nova fan-out + vera |
| 77 | Naskah komik 5 chapter: worldbuilding, karakter, cliffhanger | nova + kai + somad |
| 78 | Pidato 10 menit: audiens, pesan inti, draft | somad + nova + badsector |
| 79 | Kalender editorial 3 bulan: pilar, keyword, jadwal | kai + somad + quill |
| 80 | Media kit brand: fakta kunci, aset, angle | kai + somad + vera |
| 81 | Jalur belajar skill 3 bulan: sumber, prasyarat, latihan | kai + quill + badsector |
| 82 | Persiapan wawancara: pertanyaan lazim, latihan, konsistensi CV | kai + nova + vera |
| 83 | Perjalanan N hari: itinerary, budget, risiko musim | kai + cfo + badsector |
| 84 | RAB renovasi: harga material, tahapan, risiko molor | kai + cfo + tess + badsector |
| 85 | Rencana keuangan tahunan: pos, alokasi, skenario darurat | cfo + kai + badsector |
| 86 | Bandingkan penyedia ISP/cloud/hosting: harga, SLA, fit teknis | kai + cfo + scout |
| 87 | Transisi karier A→B: gap skill, pasar, rencana 6 bulan | kai + cfo + quill + badsector |
| 88 | SOP proses usaha: langkah, pemilik, titik kendali | quill + nova + vera |
| 89 | Rencana rekrut role: benchmark, rubrik, uji bias rubrik | kai + cfo + quill + badsector |
| 90 | Onboarding klien baru: brief, scope, jadwal | somad + quill + cfo |
| 91 | Persiapan hackathon: tema/juri, stack, pitch | kai + cto + somad |
| 92 | Validasi ide produk digital: niche, revenue, MVP termurah | kai + cfo + badsector |
| 93 | Dokumentasi sistem tanpa docs: per modul paralel, satu gaya | fan-out cto/vera + quill + nova |
| 94 | Onboarding kit repo: setup, peta kode, tugas pertama | cto + quill + nova → vera |
| 95 | Audit aksesibilitas WCAG: temuan per halaman, fix termurah | quill + cto + vera |
| 96 | Inventaris aset digital: daftar, pemilik, status | zeko + ledger + quill |
| 97 | Evaluasi proses kerja tim: timeline, kemacetan, rekomendasi | ledger + badsector + nova |
| 98 | Komposisi tim 6 bulan: beban kerja, skill gap, biaya | cfo + atlas + kai |
| 99 | Standar kode + checklist review: aturan, contoh, tooling | quill + cto + atlas |
| 100 | Kursus online: kurikulum, materi, strategi & harga | quill + nova + kai + cfo |

## Taksonomi pola berulang

1. **Riset fan-out** — semua murni baca/pikir, nol risiko (#1, 2, 12, 13, 61, 92).
2. **Multi-gelombang** — G1 hasil jadi input G2; tetap cepat karena input lengkap (#11, 16, 35, 73, 76).
3. **Multi-writer path-disjoint** — kecepatan implementasi tanpa tabrakan (#4, 14; terbukti Wave paralel-2).
4. **Review/verifikasi read-only paralel** — bisa menembak artefak yang sama, aman (#5, 7, 22, 95).
5. **Red-team penyeimbang** — badsector ditempelkan ke kesimpulan role lain (#3, 13, 32, 67).
6. **Fan-out per item** — satu pola, banyak objek identik (#28, 73, 76, 93).
7. **Workflow skala besar** — puluhan task, multi-fase, hasil terstruktur (#10; minta eksplisit).

## Anatomi prompt level implementasi (10 contoh)

> **Provenance**: 10 contoh level implementasi pertama lahir di sesi 2026-09-10 dan
> hanya tersimpan di chat; teks aslinya tidak ada di file repo. Seksi ini rekonstruksi
> 2026-09-10 (disetujui owner) dari distilat yang terdokumentasi di dokumen terkelola
> Mnemon `a7ad4821` + templat dispatch live pada `runs/smoke-parallel-3cto-2026-09-10/`.
> Struktur & aturan = distilat asli; wording tiap contoh = rekonstruksi dari entri katalog.

Setiap prompt subagen memuat **4 elemen wajib**: `Tujuan` · `Batasan` (path/scope/tool) ·
`Kriteria selesai` · `Stop condition`. Dua prompt dalam satu blok paralel tidak boleh
saling merujuk hasil (aturan 1); referensi lintas-hasil hanya sah antar-gelombang (contoh 10).

**Aturan tambahan** (hasil 10 contoh):

1. **Self-contained** — prompt saudara dalam satu blok paralel TIDAK boleh mengasumsikan
   atau merujuk hasil satu sama lain; ketergantungan timbal balik = gelombang berikutnya.
2. **Larangan standar** — read-only kecuali cto; jangan delegasi (sub-delegasi DENY);
   jangan sentuh path di luar scope yang disebut.
3. **Batas panjang output eksplisit** per laporan — mencegah laporan melebar.
4. **Verifikasi programatik parent** setelah blok settle — test suite / hitung artefak /
   cek file di disk (preseden: smoke 3×CTO 2026-09-10, file census oleh parent).

### Contoh 1 — fan-out riset read-only (katalog #1; blok kai + cfo + somad)
Prompt `kai`:
- Tujuan: petakan 5 kompetitor [X]: fitur inti, harga, posisi pasar.
- Batasan: read-only; hanya `webSearch`; jangan delegasi; jangan tulis file.
- Kriteria selesai: tabel 5 baris (kompetitor × fitur/harga/posisi) + 3 temuan pembeda.
- Stop condition: berhenti setelah tabel final; laporan ≤ 30 baris.

### Contoh 2 — saudara self-contained, tanpa rujukan silang (katalog #1; blok sama)
Prompt `cfo` (saudara contoh 1):
- Tujuan: bandingkan unit economics 5 kompetitor [X]: harga, margin, model pendapatan.
- Batasan: read-only; jangan menunggu atau merujuk laporan kai; data harga dari risetmu sendiri.
- Kriteria selesai: tabel perbandingan + 2 implikasi pricing untuk [kita].
- Stop condition: laporan ≤ 25 baris.

### Contoh 3 — multi-writer path-disjoint (katalog #4; cto ×3)
Prompt `subagent_cto` (slot A; slot B & C identik dengan path/topik lain):
- Tujuan: implementasi modul `cache/` sesuai kontrak antarmuka di plan §3.
- Batasan: tulis HANYA di `src/cache/**`; jangan sentuh `src/retry/**` (slot B) atau
  `src/flags/**` (slot C); jangan `git commit`; saudaramu menulis direktori tetangga
  di workspace yang sama.
- Kriteria selesai: kode + test modul lulus `pytest src/cache`.
- Stop condition: laporan ≤ 20 baris setelah test lulus.
(Preseden live: smoke 3×CTO 2026-09-10 — 3 instance, path disjoint, 0 tabrakan.)

### Contoh 4 — review paralel read-only (katalog #3; badsector + argus + tess + vera)
Prompt `badsector`:
- Tujuan: temukan asumsi lemah & kontradiksi di dokumen [D].
- Batasan: read-only; boleh baca repo; jangan tulis file; jangan delegasi.
- Kriteria selesai: daftar temuan berperingkat (HIGH/MED/LOW) + kutipan baris sumber.
- Stop condition: daftar final lalu berhenti; ≤ 40 baris.

### Contoh 5 — red-team standalone (pola 5; counterexample tertangkap)
Draf SALAH (mengasumsikan output agen lain → melanggar aturan 1):
- "Red-team rekomendasi kandidat A dari agen lain."
Draf BENAR (mandiri):
- Tujuan: identifikasi mode gagal umum untuk keputusan bertipe [ini] + mitigasi per mode.
- Batasan: read-only; jangan merujuk rekomendasi siapa pun; analisis dari first principles.
- Kriteria selesai: ≥ 5 mode gagal, masing-masing dengan mitigasi konkret.
- Stop condition: laporan ≤ 30 baris.

### Contoh 6 — verifikasi acceptance criteria (katalog #5; vera)
Prompt `vera`:
- Tujuan: cocokkan klaim selesai [task T] terhadap acceptance criteria di plan §2.
- Batasan: read-only; TANPA web; verifikasi dari artefak repo, bukan dari klaim teks.
- Kriteria selesai: tabel klaim ↔ bukti (PASS/FAIL) + daftar klaim tak didukung.
- Stop condition: laporan ≤ 25 baris.

### Contoh 7 — fan-out per item (katalog #73; scout per modul)
Prompt `scout` (modul i dari N; pola identik diperbanyak per item):
- Tujuan: cek kompatibilitas upgrade [dep X vN] untuk modul [i]: API terpakai, versi pin, jalur migrasi.
- Batasan: read-only; cakupan HANYA modul [i]; jangan menyimpulkan modul lain.
- Kriteria selesai: verdict (OK/BREAK/RISK) + baris kode bukti.
- Stop condition: laporan ≤ 15 baris per modul.

### Contoh 8 — boundary web subagen (katalog #12)
Prompt `kai`:
- Tujuan: ringkas tren [topik] dari 3 sumber.
- Batasan: hanya `webSearch`; kau TIDAK punya `read_page` — jika halaman penuh dibutuhkan,
  berhenti dan laporkan URL-nya untuk di-fetch parent.
- Kriteria selesai: 3 ringkasan + URL tiap sumber.
- Stop condition: jangan menunggu fetch parent dalam blok yang sama (fetch = gelombang
  berikutnya); laporan ≤ 20 baris.

### Contoh 9 — dekomposisi kebijakan (katalog #56; quill)
Prompt `quill`:
- Tujuan: dekomposisi kebijakan retensi [X] menjadi invarian yang bisa diuji.
- Batasan: read-only; TANPA web; analisis risiko sisi teknis/operasional, bukan nasihat hukum.
- Kriteria selesai: daftar invarian (id, pernyataan, cara uji) + pemetaan ke test yang ada.
- Stop condition: laporan ≤ 35 baris.

### Contoh 10 — referensi lintas-hasil hanya antar-gelombang (katalog #11; multi-gelombang)
Gelombang 2 — prompt `cto` SETELAH gelombang 1 (riset) settle dan parent menyalin hasilnya:
- Tujuan: implementasi [fitur F] memakai keputusan G1 (keputusan final ditempel di prompt ini).
- Batasan: tulis HANYA di `src/feature/**`; jangan mengevaluasi ulang opsi dari G1.
- Kriteria selesai: build + test lulus; keputusan G1 tercermin di kode.
- Stop condition: laporan ≤ 20 baris.
(Satu-satunya bentuk referensi lintas-hasil yang sah: input ditempel parent ke prompt,
bukan dirujuk implisit ke agen lain.)

## Batasan & kalibrasi

- Pemetaan role = komposisi awal; parent menyesuaikan saat eksekusi nyata.
- Subagen tidak punya `read_page`; fetch halaman penuh & penulisan file non-kode dilakukan parent.
- 14/15 spesialis deny edit/write by design (least privilege, ADR 0003 D3); verification result
  dan hasil review adalah **data**, bukan otoritas — eksekusi tetap lewat gate + otoritas Human.
- Contoh bertanda "kepatuhan/regulasi" (#56, 61, 63) adalah analisis risiko sisi teknis/operasional,
  bukan nasihat hukum.

## Integritas

- Dokumen penggunaan; tidak mengubah konfigurasi, policy, atau kode. Commit repo tetap aksi
  eksplisit Human (konvensi proyek).
