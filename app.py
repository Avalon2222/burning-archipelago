"""The Burning Archipelago — titik api NASA FIRMS dan kehilangan tutupan pohon
Global Forest Watch di Indonesia, per provinsi dan per tahun.

Jalankan: ``streamlit run app.py``
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src import analisis, grafik, peta, sumber, wilayah

st.set_page_config(page_title="The Burning Archipelago", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    .blok-judul h1 {margin-bottom:0; font-size:2.3rem; letter-spacing:-0.02em}
    .blok-judul .tagline {color:#ff7a1a; font-size:1.05rem; font-weight:600; margin:0 0 .3rem}
    .blok-judul .sub {color:#a9a79f; margin:0}
    div[data-testid="stMetricValue"] {font-size:1.55rem}
    .catatan {color:#a9a79f; font-size:.85rem}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def ambil_key() -> str | None:
    try:
        return st.secrets["firms"]["map_key"] or None
    except (KeyError, FileNotFoundError):
        return None


@st.cache_data(ttl=900, show_spinner="Mengambil titik api FIRMS ...")
def muat(hari: int, pakai_key: bool, offline: bool) -> sumber.HasilMuat:
    return sumber.muat_semua(hari=hari, key=ambil_key() if pakai_key else None, paksa_offline=offline)


@st.cache_resource
def geojson_38() -> dict:
    return wilayah.muat_geojson()


@st.cache_resource
def geojson_gfw() -> dict:
    return wilayah.gabung_provinsi(geojson_38())


def angka(n: float, desimal: int = 0) -> str:
    return f"{n:,.{desimal}f}"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

key = ambil_key()
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    mode = st.radio("Fire data source", ["Live (NASA FIRMS)", "Offline (sample data)"], index=0)
    offline = mode.startswith("Offline")
    hari_maks = 10 if key else 7
    hari = st.slider("Days of fire data", 1, hari_maks, min(7, hari_maks), help="Tanpa MAP_KEY, FIRMS hanya menyediakan berkas 7 hari terakhir. Dengan MAP_KEY, hingga 10 hari.")
    if key:
        st.caption("🔑 MAP_KEY FIRMS terpasang: data lewat API resmi.")
    else:
        st.caption("Tanpa MAP_KEY: memakai berkas CSV terbuka FIRMS (7 hari).")
    keyakinan = st.multiselect("Detection confidence", analisis.URUTAN_KEYAKINAN, default=["Nominal", "Tinggi"])
    hanya_darat = st.checkbox("Land only (inside a province)", True, help="Titik di laut umumnya sinyal palsu (kilau matahari, suar gas) atau berada di negara tetangga.")
    st.markdown("### 🗺️ Map layers")
    tampil_titik = st.checkbox("Fire points", True)
    tampil_heatmap = st.checkbox("Heatmap", False)
    tampil_batas = st.checkbox("Province borders", True)
    if st.button("🔄 Reload data", width="stretch"):
        muat.clear()
        st.rerun()
    st.markdown('<p class="catatan">Titik api disimpan 15 menit. Data kehilangan tutupan pohon bersifat tahunan dan dibaca dari berkas lokal.</p>', unsafe_allow_html=True)

hasil = muat(hari, key is not None, offline)
titik_semua = hasil.titik
titik = titik_semua[titik_semua["keyakinan"].isin(keyakinan)]
if hanya_darat:
    titik = titik[titik["provinsi"].notna()]
titik = titik.reset_index(drop=True)
tahunan, tutupan = hasil.gfw_tahunan, hasil.gfw_tutupan
tahun_semua = analisis.tahun_tersedia(tahunan)


# ---------------------------------------------------------------------------
# Judul dan status
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div class="blok-judul">
      <h1>🔥 The Burning Archipelago</h1>
      <p class="tagline">First the smoke, then the silence.</p>
      <p class="sub">Titik api satelit NASA FIRMS minggu ini dan kehilangan tutupan pohon dua dekade (Global Forest Watch / Hansen) di 38 provinsi Indonesia.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if hasil.offline:
    rincian = "; ".join(hasil.kesalahan) if hasil.kesalahan else "mode offline dipilih"
    st.warning(f"Titik api berasal dari **data contoh** ({hasil.sumber_titik}). {rincian}", icon="📦")
else:
    waktu = hasil.waktu_ambil.astimezone(timezone.utc).strftime("%d %b %Y %H:%M UTC") if hasil.waktu_ambil else "-"
    st.caption(f"Titik api langsung · {hasil.sumber_titik} · diambil {waktu}" + (f" · catatan: {' · '.join(hasil.kesalahan)}" if hasil.kesalahan else ""))

ring = analisis.ringkasan_titik(titik)
ring["di_laut"] = int(titik_semua[titik_semua["keyakinan"].isin(keyakinan)]["provinsi"].isna().sum())
per_prov = analisis.titik_per_provinsi(titik)
ring_gfw = analisis.ringkasan_gfw(tahunan, tutupan)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric(f"Titik api {min(hari, 7) if not key else hari} hari", angka(ring["jumlah"]), f"{angka(ring['per_hari'])} per hari ({ring['hari']} tanggal WIB)", delta_color="off")
k2.metric("Provinsi terpanas", ring["provinsi_teratas"], f"{angka(ring['jumlah_teratas'])} titik", delta_color="off")
k3.metric("Api terkuat", f"{angka(ring['frp_maks'], 1)} MW", f"{ring['porsi_tinggi'] * 100:.0f} % keyakinan tinggi", delta_color="off")
k4.metric(f"Hutan hilang {ring_gfw['tahun_akhir']}", f"{angka(ring_gfw['hilang_terakhir_ha'] / 1000)} rb ha", f"≈ {angka(ring_gfw['lapangan_per_hari_terakhir'])} lapangan bola/hari", delta_color="off")
k5.metric(f"Hilang {ring_gfw['tahun_awal']}–{ring_gfw['tahun_akhir']}", f"{ring_gfw['total_ha'] / 1e6:.1f} juta ha", f"{ring_gfw['persen_total']:.0f} % tutupan 2000 · {ring_gfw['setara_jakarta']:.0f}× Jakarta", delta_color="off")
k6.metric("Tahun terburuk", str(ring_gfw["tahun_puncak"]), f"{angka(ring_gfw['hilang_puncak_ha'] / 1000)} rb ha", delta_color="off")

halaman = st.segmented_control(
    "Halaman", ["🔥 Fires now", "🌳 Forest loss", "⚖️ Fire vs loss", "📋 Data & Sources", "🧭 How it works"],
    default="🔥 Fires now", label_visibility="collapsed",
) or "🔥 Fires now"


# ---------------------------------------------------------------------------
# Halaman: titik api
# ---------------------------------------------------------------------------

if halaman == "🔥 Fires now":
    if titik.empty:
        st.error("Tidak ada titik api yang lolos filter. Tambahkan tingkat keyakinan atau matikan filter daratan.")
        st.stop()
    kolom_peta, kolom_daftar = st.columns([3, 1.15])
    with kolom_daftar:
        st.markdown("#### Fokus")
        pilihan = st.selectbox("Zoom ke provinsi", ["Seluruh Indonesia"] + per_prov["provinsi"].tolist())
        st.markdown("#### Kluster terpadat")
        for r in analisis.kluster_terpadat(titik, n=6).itertuples(index=False):
            st.markdown(
                f"<div style='border-left:3px solid {peta.warna_frp(r.frp_total / max(r.jumlah, 1))};padding:2px 8px;margin:4px 0'>"
                f"<b>{r.jumlah:,} titik</b> · FRP {r.frp_total:,.0f} MW<br>"
                f"<span style='font-size:.85rem'>{r.provinsi}</span><br>"
                f"<span class='catatan'>{r.lat:.2f}, {r.lon:.2f} · kotak 0,25°</span></div>",
                unsafe_allow_html=True,
            )
        st.markdown(f"<p class='catatan'>{ring['di_laut']:,} titik lain berada di luar batas provinsi (laut atau negara tetangga)" + (" dan disembunyikan." if hanya_darat else ".") + "</p>", unsafe_allow_html=True)
    with kolom_peta:
        if pilihan != "Seluruh Indonesia":
            sub = titik[titik["provinsi"] == pilihan]
            pusat, zoom = (float(sub["lat"].median()), float(sub["lon"].median())), 7
        else:
            pusat, zoom = peta.PUSAT_INDONESIA, 5
        m = peta.peta_titik_api(titik, geojson_38(), tampil_titik, tampil_heatmap, tampil_batas, per_prov, pusat=pusat, zoom=zoom)
        st_folium(m, height=600, use_container_width=True, returned_objects=[], key="peta_api")
        st.markdown(
            '<p class="catatan">Setiap titik adalah satu piksel VIIRS 375 m yang terdeteksi lebih panas dari sekitarnya; satu kebakaran besar bisa muncul sebagai puluhan titik. '
            "Ukuran dan warna mengikuti FRP (Fire Radiative Power). Arahkan kursor untuk rincian.</p>",
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns([1.1, 1])
    c1.plotly_chart(grafik.batang_provinsi(per_prov), width="stretch")
    c2.plotly_chart(grafik.batang_kepadatan(analisis.kepadatan_provinsi(per_prov, tutupan)), width="stretch")
    c3, c4, c5 = st.columns([1.4, 1, 1])
    c3.plotly_chart(grafik.garis_harian(analisis.titik_per_hari(titik)), width="stretch")
    c4.plotly_chart(grafik.donat_keyakinan(titik), width="stretch")
    c5.plotly_chart(grafik.histogram_frp(titik), width="stretch")
    c6, c7 = st.columns([1, 1.2])
    c6.plotly_chart(grafik.batang_jam(analisis.titik_per_jam(titik)), width="stretch")
    with c7:
        st.markdown("#### Membaca angka ini")
        st.markdown(
            f"""
            - **{angka(ring['jumlah'])} titik api** dalam {ring['hari']} hari, rata-rata {angka(ring['per_hari'])} per hari. Jumlah titik bukan jumlah kebakaran:
              satu lahan gambut yang terbakar seluas 10 km² bisa menghasilkan 70 piksel sekaligus.
            - **{ring['porsi_malam'] * 100:.0f} % terdeteksi malam hari.** Deteksi malam lebih bisa dipercaya karena tidak ada pantulan matahari,
              dan api yang masih menyala tengah malam biasanya api yang serius.
            - **FRP** (megawatt) mengukur energi yang dipancarkan. Median {angka(titik['frp'].median(), 1)} MW; api di atas 40 MW biasanya kebakaran lahan terbuka atau gambut dalam.
            - Grafik per jam memperlihatkan **jadwal satelit**: NOAA-20 dan NOAA-21 melintasi Indonesia sekitar pukul 13:00–14:30 dan 01:00–02:30 WIB.
              Api yang menyala dan padam di antara dua lintasan tidak pernah tercatat.
            """
        )


# ---------------------------------------------------------------------------
# Halaman: kehilangan tutupan pohon
# ---------------------------------------------------------------------------

elif halaman == "🌳 Forest loss":
    a1, a2, a3 = st.columns([1.5, 1, 1])
    with a1:
        rentang = st.select_slider("Year range", options=tahun_semua, value=(tahun_semua[0], tahun_semua[-1]))
    with a2:
        metrik = st.selectbox("Map metric", ["hilang_ha", "persen_tutupan_2000", "emisi_mg"], format_func=lambda m: {"hilang_ha": "Hektare hilang", "persen_tutupan_2000": "% tutupan pohon 2000", "emisi_mg": "Emisi CO₂e (Mg)"}[m])
    with a3:
        st.markdown(f"<p class='catatan' style='margin-top:1.9rem'>Sumber: Hansen/UMD via Global Forest Watch, ambang kanopi {sumber.AMBANG_GFW} %, {len(tutupan)} provinsi (GADM 4.1).</p>", unsafe_allow_html=True)
    label_rentang = f"{rentang[0]}–{rentang[1]}" if rentang[0] != rentang[1] else str(rentang[0])
    hilang = analisis.hilang_per_provinsi(tahunan, tutupan, *rentang)
    label_metrik = {"hilang_ha": f"Hektare hilang {label_rentang}", "persen_tutupan_2000": f"% tutupan 2000 hilang {label_rentang}", "emisi_mg": f"Emisi Mg CO₂e {label_rentang}"}[metrik]

    kolom_peta, kolom_grafik = st.columns([3, 1.6])
    with kolom_peta:
        m = peta.peta_koroplet(geojson_gfw(), hilang, metrik, label_metrik)
        st_folium(m, height=560, use_container_width=True, returned_objects=[], key="peta_hilang")
        st.markdown(
            "<p class='catatan'>\"Tutupan pohon\" adalah semua vegetasi di atas 5 meter, termasuk perkebunan. \"Hilang\" berarti tajuk itu lenyap pada tahun tersebut, "
            "apa pun sebabnya: tebang habis, kebakaran, konversi ke sawit, atau panen hutan tanaman. Angka ini bukan definisi deforestasi resmi KLHK.</p>",
            unsafe_allow_html=True,
        )
    with kolom_grafik:
        st.plotly_chart(grafik.batang_hilang_provinsi(hilang, metrik, n=12, label_rentang=label_rentang), width="stretch")
        st.plotly_chart(grafik.batang_porsi_api(hilang), width="stretch")

    nas = analisis.hilang_nasional(tahunan)
    b1, b2 = st.columns([1.5, 1])
    b1.plotly_chart(grafik.batang_nasional(nas, tahun_sorot=ring_gfw["tahun_puncak"]), width="stretch")
    b2.plotly_chart(grafik.garis_kumulatif(nas, ring_gfw["tutupan_2000_ha"]), width="stretch")
    b3, b4 = st.columns([1.3, 1])
    b3.plotly_chart(grafik.area_pulau(analisis.hilang_per_pulau(tahunan)), width="stretch")
    with b4:
        bawaan = [p for p in ["Riau", "Kalimantan Tengah", "Papua", "Sumatera Selatan"] if p in set(tutupan["provinsi_gfw"])]
        pilih = st.multiselect("Compare provinces", sorted(tutupan["provinsi_gfw"]), default=bawaan)
        if pilih:
            st.plotly_chart(grafik.garis_provinsi(tahunan, pilih), width="stretch")

    puncak = analisis.tahun_puncak(tahunan)
    with st.expander("Membaca dua dekade kehilangan"):
        st.markdown(
            f"""
            - Indonesia kehilangan **{ring_gfw['total_ha'] / 1e6:.1f} juta hektare** tutupan pohon pada {ring_gfw['tahun_awal']}–{ring_gfw['tahun_akhir']},
              sekitar **{ring_gfw['persen_total']:.0f} %** dari tutupan tahun 2000, atau **{ring_gfw['setara_jakarta']:.0f} kali luas DKI Jakarta**.
            - Puncaknya **{ring_gfw['tahun_puncak']}** ({angka(ring_gfw['hilang_puncak_ha'])} ha), dampak kebakaran gambut 2015 yang baru tercatat satelit setelah asapnya hilang.
              Tahun terakhir, {ring_gfw['tahun_akhir']}, kehilangannya {angka(ring_gfw['hilang_terakhir_ha'])} ha; {ring_gfw['porsi_api_terakhir'] * 100:.0f} % di antaranya disebabkan kebakaran.
            - Gelombang pertama (2000-an) milik **Sumatera** (Riau, Jambi, Sumsel: sawit dan hutan tanaman industri). Gelombang kedua (2010-an) bergeser ke **Kalimantan**.
              Sekarang perhatian tertuju ke **Papua**, satu-satunya blok hutan primer besar yang tersisa.
            - Emisi gabungan {ring_gfw['tahun_awal']}–{ring_gfw['tahun_akhir']}: **{ring_gfw['emisi_total_mg'] / 1e9:.1f} miliar ton CO₂e**,
              setara kira-kira {ring_gfw['emisi_total_mg'] / analisis.MG_CO2_PER_MOBIL_TAHUN / 1e6:.0f} juta mobil berjalan setahun.
            - Provinsi dengan tahun puncak paling baru: {', '.join(f"{r.provinsi_gfw} ({r.tahun_puncak})" for r in puncak.sort_values('tahun_puncak', ascending=False).head(4).itertuples())}.
            """
        )


# ---------------------------------------------------------------------------
# Halaman: api vs kehilangan
# ---------------------------------------------------------------------------

elif halaman == "⚖️ Fire vs loss":
    rentang = st.select_slider("Loss year range", options=tahun_semua, value=(tahun_semua[0], tahun_semua[-1]), key="rentang_vs")
    gabung = analisis.gabung_api_dan_hilang(per_prov, tahunan, tutupan, *rentang)
    rho = analisis.korelasi_peringkat(gabung)
    st.plotly_chart(grafik.sebar_api_vs_hilang(gabung, rho), width="stretch")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("#### Dua peta yang tidak berhimpit")
        if rho == rho:  # bukan NaN
            kalimat = ("hampir tidak ada hubungan" if abs(rho) < 0.2 else "hubungan lemah" if abs(rho) < 0.4 else "hubungan sedang" if abs(rho) < 0.7 else "hubungan kuat")
            arah = "searah" if rho > 0 else "berlawanan arah"
            st.markdown(
                f"""
                Korelasi peringkat Spearman antara **kepadatan titik api minggu ini** dan **persentase hutan yang sudah hilang** adalah
                **ρ = {rho:.2f}**: {kalimat}, {arah}. Dua hal berbeda sedang diukur:

                - Titik api adalah **cuaca**: satu minggu, satu musim, satu El Niño. Sumatera bisa sunyi pada minggu hujan dan menyala pada minggu kering.
                - Kehilangan tutupan pohon adalah **iklim**: hasil dua dekade keputusan tata guna lahan. Riau sudah kehilangan separuh tajuknya,
                  jadi yang tersisa untuk terbakar pun lebih sedikit.
                - Provinsi di **kanan bawah** (hilang banyak, api sedikit) adalah bekas medan perang. Provinsi di **kiri atas** (hilang sedikit, api banyak)
                  adalah garis depan hari ini. Perhatikan di mana Papua berada.
                """
            )
        teratas = gabung.sort_values("titik_per_juta_ha", ascending=False).head(5)
        st.markdown("**Garis depan minggu ini** (titik api per juta ha): " + ", ".join(f"{r.provinsi_gfw} ({r.titik_per_juta_ha:,.0f})" for r in teratas.itertuples()))
        bekas = gabung.sort_values("persen_tutupan_2000", ascending=False).head(5)
        st.markdown("**Paling banyak kehilangan** (% tutupan 2000): " + ", ".join(f"{r.provinsi_gfw} ({r.persen_tutupan_2000:.0f} %)" for r in bekas.itertuples()))
    with c2:
        tabel = gabung[["provinsi_gfw", "pulau", "titik_api", "titik_per_juta_ha", "hilang_ha", "persen_tutupan_2000", "porsi_api"]].copy()
        tabel["porsi_api"] = tabel["porsi_api"] * 100
        st.dataframe(
            tabel.rename(columns={"provinsi_gfw": "Provinsi", "pulau": "Pulau", "titik_api": "Titik api", "titik_per_juta_ha": "per juta ha", "hilang_ha": "Hilang (ha)", "persen_tutupan_2000": "% tutupan 2000", "porsi_api": "% akibat api"}),
            hide_index=True, width="stretch", height=460,
            column_config={
                "Titik api": st.column_config.NumberColumn(format="%d"),
                "per juta ha": st.column_config.NumberColumn(format="%.0f"),
                "Hilang (ha)": st.column_config.NumberColumn(format="%.0f"),
                "% tutupan 2000": st.column_config.NumberColumn(format="%.1f"),
                "% akibat api": st.column_config.NumberColumn(format="%.1f"),
            },
        )


# ---------------------------------------------------------------------------
# Halaman: data dan sumber
# ---------------------------------------------------------------------------

elif halaman == "📋 Data & Sources":
    st.markdown("#### Titik api (tabel lengkap setelah filter)")
    tampil = titik[["waktu_wib", "provinsi", "lat", "lon", "frp", "kecerahan", "keyakinan", "siang_malam", "satelit", "sumber"]]
    st.dataframe(
        tampil.rename(columns={"waktu_wib": "Waktu (WIB)", "provinsi": "Provinsi", "lat": "Lintang", "lon": "Bujur", "frp": "FRP (MW)", "kecerahan": "Suhu kecerahan (K)", "keyakinan": "Keyakinan", "siang_malam": "Siang/Malam", "satelit": "Satelit", "sumber": "Sumber"}),
        hide_index=True, width="stretch", height=380,
        column_config={"Waktu (WIB)": st.column_config.DatetimeColumn(format="DD MMM YYYY HH:mm"), "FRP (MW)": st.column_config.NumberColumn(format="%.1f"), "Suhu kecerahan (K)": st.column_config.NumberColumn(format="%.0f")},
    )
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download fire points CSV", tampil.to_csv(index=False).encode("utf-8"), file_name=f"titik_api_indonesia_{datetime.now(timezone.utc):%Y%m%d}.csv", mime="text/csv")
    d2.download_button("⬇️ Download tree cover loss CSV", tahunan.to_csv(index=False).encode("utf-8"), file_name="gfw_tree_cover_loss_provinsi.csv", mime="text/csv")

    st.markdown("#### Kehilangan tutupan pohon per provinsi per tahun")
    lebar = tahunan.pivot(index="provinsi_gfw", columns="tahun", values="hilang_ha").round(0)
    st.dataframe(lebar, width="stretch", height=380, column_config={str(t): st.column_config.NumberColumn(format="%d") for t in lebar.columns})

    meta = sumber.muat_meta()
    st.markdown(
        f"""
        #### Sumber

        | Sumber | Isi | Format | Tautan |
        |---|---|---|---|
        | NASA FIRMS, VIIRS 375 m (NOAA-20, NOAA-21) | Titik api hampir seketika (NRT), 7 hari terakhir tanpa kunci, 10 hari dan arsip dengan MAP_KEY gratis | CSV | [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/) |
        | Global Forest Watch Data API, dataset `gadm__tcl__adm1_change` dan `adm1_summary` ({meta['gfw']['versi']}) | Kehilangan tutupan pohon, kehilangan akibat kebakaran, dan emisi per provinsi per tahun (Hansen/UMD, ambang kanopi 30 %) | CSV | [data-api.globalforestwatch.org](https://data-api.globalforestwatch.org/) |
        | GADM 4.1 (via GFW) | Nama 34 provinsi untuk tabel GFW | CSV | [gadm.org](https://gadm.org/) |
        | Deny Herianto, *Indonesia GeoJSON 38 Provinces* (CC BY 4.0) | Batas 38 provinsi untuk peta dan penentuan provinsi tiap titik | GeoJSON | [github.com](https://github.com/denyherianto/indonesia-geojson-topojson-maps-with-38-provinces) |

        Data contoh titik api diambil {meta['titik_api']['diambil']} ({meta['titik_api']['jumlah']:,} titik). Tabel GFW diunduh {meta['gfw']['diambil']}.

        > ⚠️ **Disclaimer.** Aplikasi ini menampilkan ulang data publik untuk tujuan edukasi dan portofolio. Ia bukan sistem pemantauan resmi,
        > tidak berafiliasi dengan NASA, Global Forest Watch, WRI, KLHK, maupun BNPB, dan tidak boleh dipakai untuk keputusan operasional.
        > Titik api adalah anomali termal yang belum diverifikasi di lapangan; "tutupan pohon" bukan padanan "hutan" menurut definisi hukum Indonesia.
        """
    )
    if hasil.kesalahan:
        st.markdown("**Catatan pengambilan data:** " + " · ".join(hasil.kesalahan))


# ---------------------------------------------------------------------------
# Halaman: cara kerja
# ---------------------------------------------------------------------------

elif halaman == "🧭 How it works":
    st.markdown(
        """
        #### Alur data

        ```
        FIRMS API (MAP_KEY) ──┐
        FIRMS CSV terbuka ────┼─► src/sumber.py ──► titik api standar ──► src/wilayah.py ──► titik + provinsi ─┐
        data/sample/*.csv.gz ─┘   (normalisasi,       (9 kolom)           (ray casting                          ├─► src/analisis.py ──► src/grafik.py (Plotly)
                                   fallback)                               38 poligon)                          │                        src/peta.py (Folium)
        GFW Data API ───────────► data/gfw_*.csv ──► kehilangan per provinsi per tahun ───────────────────────┘                        app.py (Streamlit)
        ```

        1. **Ambil.** Titik api datang sebagai CSV: satu baris per piksel panas, dengan lintang, bujur, waktu, FRP, dan tingkat keyakinan.
           Tanpa kunci, FIRMS menyediakan berkas regional Asia Tenggara 7 hari; dengan MAP_KEY gratis, API resmi melayani 1–10 hari dan arsip sejak 2012.
           Tabel kehilangan tutupan pohon diunduh dari endpoint CSV GFW Data API, yang tidak memerlukan kunci.
        2. **Normalisasi.** Semua sumber dipetakan ke kolom yang sama (`waktu_utc, lat, lon, frp, kecerahan, keyakinan, siang_malam, satelit, sumber`) dan dipotong ke kotak Indonesia.
        3. **Tentukan provinsi.** Setiap titik diuji terhadap 38 poligon provinsi dengan algoritma *ray casting* yang divektorkan numpy: sinar mendatar dari titik
           ke kanan dipotong oleh sisi poligon berapa kali? Ganjil berarti di dalam. Kotak pembatas tiap poligon memangkas pekerjaan sampai 95 %.
        4. **Samakan wilayah.** GFW memakai 34 provinsi (GADM 4.1), GeoJSON memakai 38 (BPS). Empat provinsi baru Papua digabung ke induknya dengan menyambung
           MultiPolygon, tanpa operasi geometri rumit, karena provinsi tidak pernah bertumpang tindih.
        5. **Analisis.** Jumlah dan FRP per provinsi, per hari, per jam; kepadatan per juta hektare; kluster 0,25°; kehilangan kumulatif dan persentase dari tutupan 2000;
           korelasi peringkat Spearman antara api minggu ini dan kehilangan dua dekade.
        6. **Tampil.** Folium menggambar titik dan koroplet di atas tile gelap Esri; Plotly menggambar grafik; Streamlit menyusun semuanya dan menyimpan hasil pengambilan 15 menit.

        Penjelasan panjangnya ada di `docs/BELAJAR.md`, dan latihannya di `docs/LATIHAN.md`.
        """
    )
