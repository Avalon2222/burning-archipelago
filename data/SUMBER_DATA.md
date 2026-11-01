# Sumber data & catatan metodologi

Seluruh data berasal dari layanan publik. Titik api bisa diambil tanpa kunci apa pun (berkas CSV terbuka FIRMS);
MAP_KEY gratis hanya membuka jendela waktu yang lebih panjang dan arsip. Tabel kehilangan tutupan pohon diunduh
dari endpoint CSV terbuka GFW Data API. Tidak ada data pengguna yang dikumpulkan.

## 1. Titik api — NASA FIRMS (VIIRS 375 m)

| Hal | Keterangan |
|---|---|
| Produk | VIIRS I-Band 375 m Active Fire, Collection 2, Near Real-Time (NRT), satelit NOAA-20 dan NOAA-21. Suomi NPP berhenti dikirim NASA per 2 November 2026 sehingga tidak dipakai. |
| Tanpa kunci | `https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_SouthEast_Asia_7d.csv` dan `.../noaa-21-viirs-c2/csv/J2_VIIRS_C2_SouthEast_Asia_7d.csv`: wilayah Asia Tenggara, 7 hari terakhir, diperbarui tiap beberapa jam. Disaring ke kotak 94,5°–141,5° BT, 11,5° LS–6,5° LU. |
| Dengan MAP_KEY | `https://firms.modaps.eosdis.nasa.gov/api/country/csv/{MAP_KEY}/{SUMBER}/IDN/{HARI}[/{TANGGAL}]`, `SUMBER` = `VIIRS_NOAA20_NRT` atau `VIIRS_NOAA21_NRT`, `HARI` 1–10. Produk `_SP` (standard processing) melayani arsip sejak 2012. Kuota 5000 transaksi per 10 menit. Kunci diminta gratis di <https://firms.modaps.eosdis.nasa.gov/api/map_key/> dan disimpan di `.streamlit/secrets.toml` (`[firms] map_key`), tidak pernah ikut repo. |
| Kolom yang dipakai | `latitude, longitude, acq_date, acq_time, bright_ti4, confidence, frp, daynight, satellite` → `lat, lon, waktu_utc, kecerahan, keyakinan, frp, siang_malam, satelit`. |
| Lisensi | Data NASA, domain publik. Kutipan yang diminta: *NASA FIRMS, VIIRS NOAA-20/NOAA-21 375 m Active Fire product*. |

### Apa itu "titik api"

Satu titik adalah satu piksel 375 × 375 m yang suhu kecerahannya pada 3,7 µm (kanal I-4) jauh lebih tinggi dari piksel
tetangganya. Itu **anomali termal**, belum tentu kebakaran hutan: bisa kebakaran lahan, pembakaran sisa panen, suar gas,
pabrik, atau gunung api. Satu kebakaran besar menghasilkan banyak titik berdampingan; satu titik bisa berarti api kecil
yang hanya mengisi 1 % piksel. **Jumlah titik bukan jumlah kebakaran dan bukan luas terbakar.**

- **FRP (Fire Radiative Power, MW)**: daya radiasi yang dipancarkan piksel. Sebanding dengan laju pembakaran biomassa.
  Median titik di Indonesia sekitar 3–5 MW; gambut dalam atau lahan terbuka besar melewati 40 MW.
- **Keyakinan** (`confidence`): VIIRS memberi `low / nominal / high`. `low` sering muncul di tepi swath, kilau matahari
  di air, atau permukaan panas tanpa api. Aplikasi menyaring `Nominal` dan `Tinggi` secara bawaan.
- **Siang/malam**: deteksi malam lebih bersih karena tidak ada pantulan matahari; satelit polar melintas sekitar
  01:30 dan 13:30 waktu lokal, sehingga grafik per jam memperlihatkan jadwal satelit, bukan jam kebakaran.

### Titik di laut

Pada sampel 25 Oktober 2026, NOAA-20 mencatat ribuan titik "keyakinan tinggi" dengan suhu kecerahan jenuh 367 K di
Laut Arafura, jauh dari daratan, semuanya pada satu lintasan siang hari. Itu artefak sensor atau kilau matahari, bukan
api. Karena itu aplikasi hanya menghitung titik yang jatuh di dalam poligon provinsi (saklar *Land only*), dan titik
laut atau negara tetangga (Malaysia, Timor-Leste, Papua Nugini ikut masuk kotak pembatas) dilaporkan terpisah.

## 2. Kehilangan tutupan pohon — Global Forest Watch (Hansen/UMD)

| Hal | Keterangan |
|---|---|
| Dataset | `gadm__tcl__adm1_change` (per tahun) dan `gadm__tcl__adm1_summary` (tutupan 2000/2010, luas), versi `v20260424`, GFW Data API. Data dasar: Hansen et al. 2013, *High-Resolution Global Maps of 21st-Century Forest Cover Change*, Science 342, diperbarui UMD GLAD tiap tahun. |
| Endpoint | `https://data-api.globalforestwatch.org/dataset/{dataset}/{versi}/download/csv?sql=...` (tanpa kunci; endpoint `query` memerlukan kunci). SQL lengkap ada di `src/sumber.py`. |
| Ambang | Tutupan kanopi ≥ 30 % pada tahun 2000, standar yang dipakai situs GFW. Ambang lain (10–75 %) tersedia di dataset yang sama. |
| Kolom | `umd_tree_cover_loss__ha` (kehilangan), `umd_tree_cover_loss_from_fires__ha` (bagian yang disebabkan kebakaran menurut Tyukavina et al. 2022), `gfw_gross_emissions_co2e_all_gases__Mg` (emisi kotor, Harris et al. 2021), `umd_tree_cover_extent_2000__ha`, `umd_tree_cover_extent_2010__ha`, `area__ha`, `umd_tree_cover_gain__ha` (2000–2020). |
| Wilayah | 34 provinsi GADM 4.1 (`gadm_administrative_boundaries` v4.1). Nama GADM berbeda dari BPS: "Jakarta Raya", "Yogyakarta", "Bangka Belitung". Empat provinsi hasil pemekaran Papua 2022 belum ada di GADM 4.1. |
| Lisensi | CC BY 4.0 (Hansen/UMD/Google/USGS/NASA via Global Forest Watch). |

### Peringatan GFW yang wajib dibaca

- **Tutupan pohon ≠ hutan.** Semua vegetasi di atas 5 m dihitung, termasuk kebun sawit tua, karet, dan hutan tanaman
  industri. Panen akasia di HTI tercatat sebagai "kehilangan", meski ditanam lagi tahun berikutnya.
- **Kehilangan ≠ deforestasi.** Kehilangan adalah tajuk yang lenyap pada tahun itu, apa pun sebabnya. Definisi deforestasi
  KLHK (perubahan kelas penutupan lahan hutan ke non-hutan) menghasilkan angka yang jauh lebih kecil.
- **Perubahan metode.** Data 2011 ke atas diproduksi dengan algoritma yang lebih peka (termasuk Landsat 8 sejak 2013),
  sehingga perbandingan langsung 2001–2010 dengan 2011+ perlu hati-hati.
- **Kehilangan akibat kebakaran** berasal dari model (Tyukavina et al. 2022) yang memisahkan kebakaran dari sebab lain
  berdasarkan pola spektral; angkanya taksiran, bukan verifikasi lapangan.
- **Emisi** adalah emisi kotor dari gangguan pengganti tegakan (stand-replacing), tidak termasuk degradasi, dan tidak
  dikurangi serapan tumbuh kembali.

## 3. Batas provinsi — `data/provinsi.geojson`

| Hal | Keterangan |
|---|---|
| Sumber | *Indonesia GeoJSON & TopoJSON Maps (38 Provinces)* oleh Deny Herianto, CC BY 4.0: <https://github.com/denyherianto/indonesia-geojson-topojson-maps-with-38-provinces> |
| Pengolahan | Properti `kode_bps` dan `provinsi`; koordinat dibulatkan ke 4 desimal (~11 m); berkas yang sama dipakai proyek `follow-the-money`. |
| Pemakaian | Menentukan provinsi tiap titik api (*ray casting*, `src/wilayah.py`) dan menggambar batas. Untuk koroplet GFW, 38 poligon digabung menjadi 34 dengan menyambung MultiPolygon (`wilayah.gabung_provinsi`). |

Karena poligonnya disederhanakan, titik api tepat di garis pantai (misalnya kota Jayapura) kadang jatuh di luar semua
poligon dan terhitung "laut". Porsinya kecil dibanding artefak laut yang sesungguhnya.

## 4. Data contoh (`data/sample/`)

- `titik_api_7hari.csv.gz`: gabungan dua berkas terbuka FIRMS pada tanggal yang tercatat di `meta.json`, disaring ke
  kotak Indonesia, dibulatkan 4 desimal, terkompresi gzip (sekitar 48 ribu baris, 0,5 MB).
- `meta.json`: waktu pengambilan dan jumlah baris, versi GFW, ambang tutupan.
- `data/gfw_tahunan.csv` dan `data/gfw_tutupan.csv`: tabel GFW yang sudah dirapikan; bukan "contoh" karena data tahunan
  memang tidak perlu diambil langsung setiap kali aplikasi dibuka.

Perbarui semuanya dengan `python scripts/perbarui_sample.py` (tanpa kunci). Dipakai saat pengguna memilih mode offline,
saat FIRMS tidak bisa dihubungi, dan oleh `pytest`.

## 5. Rumus dan konstanta

- **Kepadatan titik api** = titik ÷ luas provinsi (ha) × 1.000.000, yaitu titik per juta hektare (10.000 km²).
- **Persen tutupan 2000 yang hilang** = Σ kehilangan pada rentang tahun ÷ tutupan 2000 × 100. Bisa melampaui angka
  "deforestasi bersih" karena tumbuh kembali tidak dikurangkan.
- **Kluster 0,25°** = kotak 0,25° × 0,25° (sekitar 28 × 28 km di khatulistiwa) dengan titik terbanyak.
- **Korelasi peringkat Spearman** antara kepadatan titik minggu ini dan persen kehilangan kumulatif per provinsi GFW.
- Pembanding: lapangan sepak bola 0,714 ha (105 × 68 m); luas daratan DKI Jakarta 66.150 ha; emisi satu mobil penumpang
  4,6 ton CO₂e per tahun (US EPA).

## Disclaimer

Proyek ini menampilkan ulang data publik untuk tujuan edukasi dan portofolio. Ia bukan sistem pemantauan resmi dan tidak
berafiliasi dengan NASA, Global Forest Watch, WRI, KLHK, BNPB, atau BMKG. Titik api adalah anomali termal yang belum
diverifikasi, dan "tutupan pohon" bukan padanan "hutan" menurut hukum Indonesia. Untuk keputusan apa pun, rujuk ke
[sipongi.menlhk.go.id](https://sipongi.menlhk.go.id/), [bnpb.go.id](https://bnpb.go.id/), dan
[globalforestwatch.org](https://www.globalforestwatch.org/).
