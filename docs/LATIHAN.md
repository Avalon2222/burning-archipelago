# 🏋️ Latihan

Diurutkan dari mudah ke menantang. Tiap latihan punya petunjuk dan kunci yang bisa dibuka. Usahakan mencoba
minimal 10 menit sebelum membuka kunci. Setelah tiap latihan, jalankan `python -m pytest tests/` dan
`streamlit run app.py`.

---

### Latihan 1 — Ambang warna FRP ⭐

Legenda peta memakai lima ambang FRP: 0, 5, 15, 40, 100 MW. Tambahkan satu kelas lagi untuk api ekstrem di atas 250 MW
dengan warna ungu gelap `#4a0a4a`, dan pastikan legenda ikut berubah tanpa disentuh.

<details><summary>Petunjuk</summary>
Semua ada di satu konstanta di <code>src/peta.py</code>. Legenda dibangun dari konstanta yang sama.
</details>

<details><summary>Kunci</summary>

```python
WARNA_FRP = [(0, "#ffd166"), (5, "#ff9b3d"), (15, "#ff5d1a"), (40, "#e01b1b"), (100, "#8a0b2d"), (250, "#4a0a4a")]
```

`warna_frp` memilih warna ambang terakhir yang terlampaui, dan `_legenda_api` mengulang daftar yang sama. Mengubah satu
tempat mengubah keduanya: itulah gunanya konstanta.
</details>

---

### Latihan 2 — Kalimat ringkasan per hari ⭐

Di halaman *Fires now*, di bawah grafik per hari, tambahkan satu kalimat yang menyebut tanggal dengan titik api
terbanyak, misalnya "Hari terpanas: 27 Okt (6.120 titik)". Fungsi `analisis.titik_per_hari` sudah ada.

<details><summary>Petunjuk</summary>
<code>per_hari</code> mengembalikan kolom <code>tanggal</code> dan <code>jumlah</code>; <code>idxmax()</code> memberi
indeks baris terbesar. Tanggal adalah objek <code>datetime.date</code>, formatnya dengan <code>strftime("%d %b")</code>.
</details>

<details><summary>Kunci</summary>

```python
per_hari = analisis.titik_per_hari(titik)
puncak = per_hari.loc[per_hari["jumlah"].idxmax()]
st.caption(f"Hari terpanas: {puncak['tanggal']:%d %b} ({int(puncak['jumlah']):,} titik).")
```
</details>

---

### Latihan 3 — Filter siang/malam ⭐⭐

Tambahkan `st.radio("Day / night", ["Semua", "Siang", "Malam"])` di sidebar dan saring `titik` sesuai pilihan. Lalu
bandingkan: berapa persen titik malam yang berkeyakinan tinggi dibanding titik siang?

<details><summary>Petunjuk</summary>
Kolom <code>siang_malam</code> sudah berisi "Siang"/"Malam". Penyaringan dilakukan di blok yang sama dengan filter
keyakinan di <code>app.py</code>. Untuk perbandingannya, pakai <code>groupby("siang_malam")["keyakinan"]</code>.
</details>

<details><summary>Kunci</summary>

```python
fase = st.radio("Day / night", ["Semua", "Siang", "Malam"], horizontal=True)
if fase != "Semua":
    titik = titik[titik["siang_malam"] == fase]
```

Perbandingan:

```python
titik.groupby("siang_malam")["keyakinan"].apply(lambda s: (s == "Tinggi").mean())
```

Deteksi malam biasanya punya porsi "Tinggi" yang lebih besar, karena tidak ada pantulan matahari yang membuat
algoritma ragu. Bab 1.1 di BELAJAR.md menjelaskan alasannya.
</details>

---

### Latihan 4 — Ambang tutupan kanopi lain ⭐⭐

GFW menyediakan ambang 10, 15, 20, 25, 30, 50, 75 %. Ubah `scripts/perbarui_sample.py` agar bisa menerima argumen
`--ambang 50`, unduh ulang, dan lihat berapa besar total kehilangan 2001–2025 berubah.

<details><summary>Petunjuk</summary>
Ambang muncul di dua string SQL di <code>src/sumber.py</code> lewat f-string <code>AMBANG_GFW</code>. Buat kedua SQL
menjadi fungsi yang menerima ambang, lalu teruskan dari argparse. Jangan lupa <code>meta.json</code>.
</details>

<details><summary>Kunci</summary>

```python
def sql_tahunan(ambang: int) -> str:
    return ("SELECT adm1, umd_tree_cover_loss__year, SUM(umd_tree_cover_loss__ha) AS hilang_ha, ... "
            f"FROM data WHERE iso='IDN' AND umd_tree_cover_density_2000__threshold={ambang} "
            "GROUP BY adm1, umd_tree_cover_loss__year")
```

Dengan ambang 50 %, tutupan 2000 dan kehilangan keduanya mengecil, tetapi tidak sebanding: hutan tanaman muda dan
belukar (tajuk 30–50 %) keluar dari hitungan, sehingga "kehilangan" lebih condong ke hutan rapat. Bandingkan angka
persennya, bukan hanya hektarenya.
</details>

---

### Latihan 5 — Uji titik di garis pantai ⭐⭐

Kota Jayapura (140,7181° BT, 2,5337° LS) jatuh di luar semua poligon karena garis pantainya disederhanakan. Tulis
fungsi `provinsi_terdekat(lon, lat, jarak_maks_km=15)` di `src/wilayah.py` yang, untuk titik yang tidak masuk poligon
mana pun, mencari simpul poligon terdekat dan mengembalikan provinsinya bila jaraknya di bawah ambang. Tambahkan tes.

<details><summary>Petunjuk</summary>
Semua simpul cincin luar sudah tersimpan di <code>self.poligon</code>. Jarak kasar: 1° lintang ≈ 111 km, 1° bujur ≈
111 km × cos(lintang). Hitung ke semua simpul sekaligus dengan numpy, ambil <code>argmin</code>.
</details>

<details><summary>Kunci</summary>

```python
def provinsi_terdekat(self, lon: float, lat: float, jarak_maks_km: float = 15) -> str | None:
    terbaik, nama_terbaik = float("inf"), None
    for nama, luar, _, _ in self.poligon:
        dx = (luar[:, 0] - lon) * 111.0 * np.cos(np.radians(lat))
        dy = (luar[:, 1] - lat) * 111.0
        jarak = float(np.sqrt(dx * dx + dy * dy).min())
        if jarak < terbaik:
            terbaik, nama_terbaik = jarak, nama
    return nama_terbaik if terbaik <= jarak_maks_km else None
```

Tes: Jayapura harus menjadi "Papua", sedangkan Kuala Lumpur tetap `None`. Lalu pikirkan: haruskah ini dipakai untuk
semua titik laut? Tidak. Artefak Laut Arafura berjarak ratusan kilometer dari daratan dan tetap tersaring, tetapi
titik 5 km di lepas pantai Riau (kapal? suar?) akan masuk provinsi. Pilih ambang dengan sadar dan tulis di
SUMBER_DATA.md.
</details>

---

### Latihan 6 — Tren per provinsi: naik atau turun? ⭐⭐⭐

Tambahkan kolom `tren` ke tabel di halaman *Fire vs loss*: kemiringan garis regresi kehilangan tahunan pada lima tahun
terakhir (ha per tahun). Provinsi dengan tren positif besar sedang memburuk. Tulis fungsinya di `src/analisis.py`
dengan `numpy.polyfit`, dan ujilah dengan deret buatan yang kemiringannya kamu ketahui.

<details><summary>Petunjuk</summary>
<code>np.polyfit(tahun, hilang, 1)[0]</code> memberi kemiringan. Kelompokkan <code>tahunan</code> per provinsi, ambil
lima tahun terakhir, terapkan. Hati-hati provinsi yang datanya kurang dari dua tahun.
</details>

<details><summary>Kunci</summary>

```python
def tren_terakhir(tahunan: pd.DataFrame, n_tahun: int = 5) -> pd.Series:
    def kemiringan(g: pd.DataFrame) -> float:
        g = g.sort_values("tahun").tail(n_tahun)
        if len(g) < 2:
            return float("nan")
        return float(np.polyfit(g["tahun"], g["hilang_ha"], 1)[0])
    return tahunan.groupby("provinsi_gfw").apply(kemiringan, include_groups=False).rename("tren_ha_per_tahun")
```

Tes: deret `[100, 200, 300, 400, 500]` pada tahun 2021–2025 harus memberi kemiringan 100 (gunakan `pytest.approx`).
</details>

---

### Latihan 7 — Musim kemarau penuh dengan MAP_KEY ⭐⭐⭐

Buat `scripts/unduh_musim.py` yang, dengan MAP_KEY dari `.streamlit/secrets.toml`, mengunduh titik api VIIRS SNPP
arsip (`VIIRS_SNPP_SP`) untuk Agustus–Oktober satu tahun pilihan (misalnya 2023) dalam potongan 10 hari, menandai
provinsi, lalu menyimpan jumlah per provinsi ke `data/sample/musim_2023.csv`. Ulangi analisis Spearman dengan data itu.

<details><summary>Petunjuk</summary>
<code>sumber.ambil_api(key, 10, "SNPP", tanggal="2023-08-01", arsip=True)</code> memberi 10 hari mulai tanggal itu.
Sembilan panggilan menutup satu musim. Baca kunci dengan modul <code>tomllib</code> (bawaan Python 3.11+). Periksa sisa
kuota dengan <code>sumber.status_key</code>.
</details>

<details><summary>Kunci</summary>

```python
import tomllib, pandas as pd
from src import sumber, analisis

key = tomllib.load(open(".streamlit/secrets.toml", "rb"))["firms"]["map_key"]
potongan = []
for awal in pd.date_range("2023-08-01", "2023-10-30", freq="10D"):
    potongan.append(sumber.ambil_api(key, 10, "SNPP", tanggal=awal.strftime("%Y-%m-%d"), arsip=True))
titik = sumber.tandai_provinsi(pd.concat(potongan, ignore_index=True))
analisis.titik_per_provinsi(titik).to_csv("data/sample/musim_2023.csv", index=False)
```

2023 adalah tahun El Niño: Kalimantan Tengah dan Sumatera Selatan akan naik jauh. Hitung Spearman terhadap kehilangan
2001–2023 dan bandingkan dengan nilai minggu ini. Apakah korelasinya tetap mendekati nol? Jika ya, tesis "cuaca vs
iklim" di Bab 5 menguat; jika tidak, kamu baru saja menemukan sesuatu yang lebih menarik dari aplikasi ini.
</details>

---

### Latihan 8 — Kabupaten, bukan provinsi ⭐⭐⭐

GFW juga punya `gadm__tcl__adm2_change` (kabupaten/kota). Unduh kehilangan per kabupaten per tahun untuk satu provinsi
pilihan dan gambar grafik batang 10 kabupaten teratas. Nama kabupaten ada di `gadm_administrative_boundaries` dengan
`adm_level='2'` dan kolom `gid_2`, `name_2`.

<details><summary>Petunjuk</summary>
Pola SQL-nya sama dengan <code>SQL_GFW_TAHUNAN</code>, tambahkan <code>adm2</code> di SELECT dan GROUP BY, dan saring
<code>adm1</code> ke nomor provinsi yang kamu pilih. <code>gid_2</code> berbentuk <code>IDN.25.3_1</code>: angka
pertama adm1, kedua adm2.
</details>

<details><summary>Kunci</summary>

```python
sql = ("SELECT adm1, adm2, umd_tree_cover_loss__year, SUM(umd_tree_cover_loss__ha) AS hilang_ha "
       "FROM data WHERE iso='IDN' AND adm1=25 AND umd_tree_cover_density_2000__threshold=30 "
       "GROUP BY adm1, adm2, umd_tree_cover_loss__year")
d = sumber._unduh_gfw("gadm__tcl__adm2_change", sumber.VERSI_GFW, sql)
nama = sumber._unduh_gfw("gadm_administrative_boundaries", sumber.VERSI_GADM,
                         "SELECT gid_2, name_2 FROM data WHERE gid_0='IDN' AND adm_level='2'")
nama["adm1"] = nama["gid_2"].str.extract(r"IDN\.(\d+)\.")[0].astype(int)
nama["adm2"] = nama["gid_2"].str.extract(r"IDN\.\d+\.(\d+)_")[0].astype(int)
d = d.merge(nama[["adm1", "adm2", "name_2"]], on=["adm1", "adm2"])
```

Di Riau (adm1 = 25), Pelalawan dan Indragiri Hilir biasanya memimpin: gambut pesisir yang dikonversi menjadi HTI dan
sawit pada 2000-an.
</details>

---

### Latihan 9 — Peta hari demi hari (animasi) ⭐⭐⭐⭐

Ganti peta titik api dengan `plotly.express.scatter_mapbox` (atau `scatter_map` di Plotly 7) yang punya
`animation_frame="tanggal"`, sehingga pengguna bisa memutar tujuh hari seperti film. Pertahankan warna FRP dan batasi
jumlah titik per bingkai.

<details><summary>Petunjuk</summary>
Plotly menginginkan kolom kategori untuk warna, jadi buat <code>kelas_frp</code> dengan <code>pd.cut</code> memakai
ambang <code>WARNA_FRP</code>. <code>animation_frame</code> butuh nilai yang bisa diurutkan: ubah tanggal ke string
ISO. Gaya peta gelap: <code>map_style="carto-darkmatter"</code>.
</details>

<details><summary>Kunci</summary>

```python
ambang = [a for a, _ in peta.WARNA_FRP] + [float("inf")]
d = titik.copy()
d["kelas_frp"] = pd.cut(d["frp"], bins=ambang, right=False, labels=[f"≥ {a} MW" for a, _ in peta.WARNA_FRP])
d["hari"] = d["tanggal"].astype(str)
fig = px.scatter_map(d.sort_values("hari"), lat="lat", lon="lon", color="kelas_frp", animation_frame="hari",
                     color_discrete_sequence=[w for _, w in peta.WARNA_FRP], zoom=4, center=dict(lat=-2.3, lon=118),
                     map_style="carto-darkmatter", height=600, opacity=0.7)
fig.update_traces(marker=dict(size=5))
st.plotly_chart(fig, width="stretch")
```

Perhatikan bagaimana kluster Papua Selatan menyala dan padam dalam dua hari, sedangkan Kalimantan Tengah membara stabil.
Itulah perbedaan antara pembakaran lahan terbuka dan gambut yang terbakar di bawah permukaan.
</details>
