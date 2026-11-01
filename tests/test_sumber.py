"""Pengujian parser dan pemuat data. Tidak memerlukan jaringan."""

import pandas as pd
import pytest

from src import sumber

CONTOH_VIIRS = pd.DataFrame({
    "latitude": [-2.2096, -9.8, 3.1390, -6.1751],
    "longitude": [113.9213, 134.5, 101.6869, 106.8272],
    "bright_ti4": [340.5, 367.0, 330.0, 335.2],
    "scan": [0.4, 0.4, 0.4, 0.4],
    "track": [0.6, 0.6, 0.6, 0.6],
    "acq_date": ["2026-10-30", "2026-10-25", "2026-10-30", "2026-10-31"],
    "acq_time": ["0632", "532", "0632", "1845"],
    "satellite": ["N20", "N20", "N21", "N21"],
    "confidence": ["nominal", "high", "low", "n"],
    "version": ["2.0NRT"] * 4,
    "bright_ti5": [295.0, 296.0, 290.0, 292.0],
    "frp": [12.34, 5.0, 1.2, 60.0],
    "daynight": ["D", "D", "D", "N"],
})

CONTOH_MODIS = pd.DataFrame({
    "latitude": [-2.0], "longitude": [114.0], "brightness": [320.0], "scan": [1.0], "track": [1.0],
    "acq_date": ["2026-10-30"], "acq_time": ["0300"], "satellite": ["Terra"], "confidence": [85],
    "version": ["6.1NRT"], "bright_t31": [290.0], "frp": [20.0], "daynight": ["D"],
})


def test_normalisasi_viirs_kolom_dan_nilai():
    d = sumber.normalisasi_firms(CONTOH_VIIRS, "uji")
    assert list(d.columns) == sumber.KOLOM_TITIK
    assert len(d) == 4  # Kuala Lumpur masih di dalam kotak Indonesia; penyaringan provinsi terjadi belakangan
    baris = d.iloc[0]
    assert baris["waktu_utc"] == pd.Timestamp("2026-10-30 06:32", tz="UTC")
    assert baris["frp"] == 12.3 and baris["kecerahan"] == 340.5
    assert baris["satelit"] == "NOAA-20" and baris["sumber"] == "uji"
    assert d["keyakinan"].tolist() == ["Nominal", "Tinggi", "Rendah", "Nominal"]
    assert d["siang_malam"].tolist() == ["Siang", "Siang", "Siang", "Malam"]


def test_normalisasi_jam_tiga_digit_dinolkan():
    d = sumber.normalisasi_firms(CONTOH_VIIRS, "uji")
    assert d.iloc[1]["waktu_utc"] == pd.Timestamp("2026-10-25 05:32", tz="UTC")


def test_normalisasi_modis_pakai_brightness_dan_angka_keyakinan():
    d = sumber.normalisasi_firms(CONTOH_MODIS, "modis")
    assert d.iloc[0]["kecerahan"] == 320.0
    assert d.iloc[0]["keyakinan"] == "Tinggi"


def test_normalisasi_membuang_titik_luar_kotak():
    luar = CONTOH_VIIRS.copy()
    luar.loc[0, "longitude"] = 150.0   # Papua Nugini timur
    d = sumber.normalisasi_firms(luar, "uji")
    assert len(d) == 3


def test_normalisasi_kosong():
    d = sumber.normalisasi_firms(pd.DataFrame(), "uji")
    assert d.empty and list(d.columns) == sumber.KOLOM_TITIK


def test_keyakinan_berbagai_bentuk():
    assert sumber._keyakinan("l") == "Rendah"
    assert sumber._keyakinan("HIGH") == "Tinggi"
    assert sumber._keyakinan(10) == "Rendah"
    assert sumber._keyakinan(50) == "Nominal"
    assert sumber._keyakinan("???") == "Nominal"


def test_ambil_api_menolak_hari_di_luar_1_10():
    with pytest.raises(ValueError):
        sumber.ambil_api("kunci", 11)


def test_tandai_provinsi_menambah_kolom_waktu():
    d = sumber.tandai_provinsi(sumber.normalisasi_firms(CONTOH_VIIRS, "uji"))
    assert d["provinsi"].iloc[0] == "Kalimantan Tengah" and d["provinsi"].iloc[3] == "DKI Jakarta"
    assert d["provinsi"].iloc[1:3].isna().all()  # laut Arafura dan Kuala Lumpur
    assert d.iloc[0]["waktu_wib"].hour == 13  # 06:32 UTC = 13:32 WIB
    assert str(d.iloc[3]["tanggal"]) == "2026-11-01"  # 31 Okt 18:45 UTC = 1 Nov 01:45 WIB


def test_rapikan_gfw():
    nama = {1: "Aceh", 25: "Riau"}
    tahunan = pd.DataFrame({"adm1": [1, 1, 25], "umd_tree_cover_loss__year": [2001, 2002, 2001], "hilang_ha": [10.55, 20.0, 5.0], "hilang_api_ha": [1.0, 2.0, 0.5], "emisi_mg": [100.4, 200.0, 50.0]})
    t = sumber.rapikan_gfw_tahunan(tahunan, nama)
    assert t["provinsi_gfw"].tolist() == ["Aceh", "Aceh", "Riau"]
    assert t.iloc[0]["hilang_ha"] == 10.6 and t.iloc[0]["emisi_mg"] == 100
    tutupan = pd.DataFrame({"adm1": [25, 99], "tutupan_2000_ha": [7.8e6, 1.0], "tutupan_2010_ha": [7.6e6, 1.0], "luas_ha": [9e6, 1.0], "tumbuh_ha": [1e5, 0.0]})
    u = sumber.rapikan_gfw_tutupan(tutupan, nama)
    assert u["provinsi_gfw"].tolist() == ["Riau"]  # adm1 tanpa nama dibuang


def test_potong_hari():
    d = sumber.normalisasi_firms(CONTOH_VIIRS, "uji")
    assert len(sumber.potong_hari(d, 7)) == 4
    assert len(sumber.potong_hari(d, 2)) == 3  # 30 dan 31 Okt saja


def test_data_contoh_terbaca_dan_konsisten():
    titik, meta = sumber.muat_sample()
    assert len(titik) == meta["titik_api"]["jumlah"] > 1000
    assert titik["waktu_utc"].dt.tz is not None
    tahunan, tutupan = sumber.muat_gfw()
    assert len(tutupan) == 34
    assert set(tahunan["provinsi_gfw"]) == set(tutupan["provinsi_gfw"])
    assert tahunan["tahun"].min() == 2001 and tahunan["tahun"].max() >= 2024
    assert (tahunan["hilang_api_ha"] <= tahunan["hilang_ha"] + 1).all()


def test_muat_semua_offline_tanpa_jaringan():
    h = sumber.muat_semua(hari=3, paksa_offline=True)
    assert h.offline and h.sumber_titik.startswith("data contoh")
    assert {"provinsi", "waktu_wib", "tanggal"} <= set(h.titik.columns)
    assert h.titik["tanggal"].nunique() <= 3
    assert h.titik["provinsi"].notna().sum() > 0
