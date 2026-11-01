"""Pengujian agregasi dan analisis dengan tabel kecil buatan."""

import numpy as np
import pandas as pd
import pytest

from src import analisis


@pytest.fixture
def titik():
    waktu = pd.to_datetime(["2026-10-30 06:00", "2026-10-30 06:05", "2026-10-31 18:00", "2026-10-31 18:10", "2026-10-31 18:20"], utc=True)
    d = pd.DataFrame({
        "waktu_utc": waktu,
        "lat": [-2.2, -2.24, -0.5, -0.6, -9.8],
        "lon": [113.9, 113.95, 101.4, 101.45, 134.5],
        "frp": [10.0, 30.0, 5.0, 7.0, 3.0],
        "kecerahan": [340.0] * 5,
        "keyakinan": ["Nominal", "Tinggi", "Nominal", "Rendah", "Tinggi"],
        "siang_malam": ["Siang", "Siang", "Malam", "Malam", "Siang"],
        "satelit": ["NOAA-20"] * 5,
        "sumber": ["uji"] * 5,
        "provinsi": ["Kalimantan Tengah", "Kalimantan Tengah", "Riau", "Riau", None],
    })
    d["waktu_wib"] = d["waktu_utc"].dt.tz_convert("Asia/Jakarta")
    d["tanggal"] = d["waktu_wib"].dt.date
    return d


@pytest.fixture
def tahunan():
    baris = []
    for prov, dasar in (("Riau", 100.0), ("Kalimantan Tengah", 50.0), ("Papua", 10.0)):
        for t in range(2001, 2006):
            hilang = dasar * (3 if t == 2004 else 1)
            baris.append({"provinsi_gfw": prov, "tahun": t, "hilang_ha": hilang, "hilang_api_ha": hilang * 0.2, "emisi_mg": hilang * 100})
    return pd.DataFrame(baris)


@pytest.fixture
def tutupan():
    return pd.DataFrame({
        "provinsi_gfw": ["Riau", "Kalimantan Tengah", "Papua"],
        "luas_ha": [9e6, 15e6, 31e6],
        "tutupan_2000_ha": [1000.0, 2000.0, 4000.0],
        "tutupan_2010_ha": [900.0, 1900.0, 3950.0],
        "tumbuh_ha": [10.0, 20.0, 5.0],
    })


def test_ringkasan_titik(titik):
    r = analisis.ringkasan_titik(titik)
    assert r["jumlah"] == 5 and r["hari"] == 2 and r["per_hari"] == 2.5
    assert r["provinsi_teratas"] == "Kalimantan Tengah" and r["jumlah_teratas"] == 2
    assert r["frp_maks"] == 30.0 and r["di_laut"] == 1
    assert r["porsi_malam"] == pytest.approx(0.4)


def test_ringkasan_titik_kosong(titik):
    r = analisis.ringkasan_titik(titik.iloc[0:0])
    assert r["jumlah"] == 0 and r["provinsi_teratas"] == "-"


def test_titik_per_provinsi_mengabaikan_laut(titik):
    p = analisis.titik_per_provinsi(titik)
    assert p["provinsi"].tolist() == ["Kalimantan Tengah", "Riau"]
    assert p.iloc[0]["frp_total"] == 40.0 and p.iloc[0]["porsi_tinggi"] == 0.5


def test_titik_per_hari_mengisi_tanggal_kosong(titik):
    d = titik.copy()
    d.loc[2:, "waktu_utc"] = d.loc[2:, "waktu_utc"] + pd.Timedelta(days=2)
    d["waktu_wib"] = d["waktu_utc"].dt.tz_convert("Asia/Jakarta")
    d["tanggal"] = d["waktu_wib"].dt.date
    h = analisis.titik_per_hari(d)
    # 30 Okt, lalu tiga tanggal kosong, lalu 3 Nov (31 Okt 18:00 UTC = 1 Nov WIB, digeser dua hari).
    assert len(h) == 5
    assert h["jumlah"].tolist() == [2, 0, 0, 0, 3]


def test_titik_per_jam_24_baris(titik):
    j = analisis.titik_per_jam(titik)
    assert len(j) == 24 and j["jumlah"].sum() == 5
    assert j.loc[j["jam"] == 13, "jumlah"].item() == 2  # 06:00 UTC = 13:00 WIB


def test_kepadatan_provinsi(titik, tutupan):
    k = analisis.kepadatan_provinsi(analisis.titik_per_provinsi(titik), tutupan)
    riau = k[k["provinsi"] == "Riau"].iloc[0]
    assert riau["per_juta_ha"] == pytest.approx(2 / 9e6 * 1e6)


def test_kluster_terpadat(titik):
    k = analisis.kluster_terpadat(titik, ukuran_derajat=0.25, n=3)
    assert k.iloc[0]["jumlah"] == 2 and k.iloc[0]["provinsi"] in {"Kalimantan Tengah", "Riau"}
    assert "laut/luar negeri" in set(k["provinsi"])


def test_hilang_nasional(tahunan):
    n = analisis.hilang_nasional(tahunan)
    assert n["tahun"].tolist() == [2001, 2002, 2003, 2004, 2005]
    assert n.loc[n["tahun"] == 2004, "hilang_ha"].item() == 480.0
    assert n["kumulatif_ha"].iloc[-1] == 160.0 * 4 + 480.0
    assert n["porsi_api"].iloc[0] == pytest.approx(0.2)


def test_hilang_per_provinsi_rentang_dan_persen(tahunan, tutupan):
    h = analisis.hilang_per_provinsi(tahunan, tutupan, 2001, 2003)
    assert h["provinsi_gfw"].tolist() == ["Riau", "Kalimantan Tengah", "Papua"]
    riau = h.iloc[0]
    assert riau["hilang_ha"] == 300.0 and riau["persen_tutupan_2000"] == pytest.approx(30.0)
    h1 = analisis.hilang_per_provinsi(tahunan, tutupan, 2004, 2004)
    assert h1.iloc[0]["hilang_ha"] == 300.0


def test_tahun_puncak(tahunan):
    p = analisis.tahun_puncak(tahunan)
    assert set(p["tahun_puncak"]) == {2004}


def test_ringkasan_gfw(tahunan, tutupan):
    r = analisis.ringkasan_gfw(tahunan, tutupan)
    assert r["tahun_awal"] == 2001 and r["tahun_akhir"] == 2005 and r["tahun_puncak"] == 2004
    assert r["total_ha"] == 1120.0 and r["persen_total"] == pytest.approx(16.0)
    assert r["porsi_api_terakhir"] == pytest.approx(0.2)


def test_gabung_api_dan_hilang(titik, tahunan, tutupan):
    g = analisis.gabung_api_dan_hilang(analisis.titik_per_provinsi(titik), tahunan, tutupan, 2001, 2005)
    assert len(g) == 3
    papua = g[g["provinsi_gfw"] == "Papua"].iloc[0]
    assert papua["titik_api"] == 0 and papua["pulau"] == "Papua"
    riau = g[g["provinsi_gfw"] == "Riau"].iloc[0]
    assert riau["titik_api"] == 2 and riau["titik_per_juta_ha"] == pytest.approx(2 / 9)


def test_korelasi_peringkat():
    d = pd.DataFrame({"a": [1, 2, 3, 4], "b": [10, 20, 30, 40]})
    assert analisis.korelasi_peringkat(d, "a", "b") == pytest.approx(1.0)
    d["b"] = [40, 30, 20, 10]
    assert analisis.korelasi_peringkat(d, "a", "b") == pytest.approx(-1.0)
    assert np.isnan(analisis.korelasi_peringkat(d.head(2), "a", "b"))


def test_pulau_lengkap_untuk_34_provinsi():
    from src import sumber
    _, tutupan = sumber.muat_gfw()
    assert all(analisis.pulau(p) != "Lainnya" for p in tutupan["provinsi_gfw"])


def test_hilang_per_pulau(tahunan):
    p = analisis.hilang_per_pulau(tahunan)
    assert set(p["pulau"]) == {"Sumatera", "Kalimantan", "Papua"}
    assert p.loc[(p["tahun"] == 2001) & (p["pulau"] == "Sumatera"), "hilang_ha"].item() == 100.0
