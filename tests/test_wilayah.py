"""Pengujian geometri: titik di dalam poligon, penentuan provinsi, penggabungan provinsi."""

import numpy as np
import pandas as pd
import pytest

from src import wilayah

# Beberapa kota dengan provinsi yang pasti (lon, lat).
KOTA = {
    "Jakarta": (106.8272, -6.1751, "DKI Jakarta"),
    "Pontianak": (109.3425, -0.0263, "Kalimantan Barat"),
    "Palangka Raya": (113.9213, -2.2096, "Kalimantan Tengah"),
    "Pekanbaru": (101.4478, 0.5071, "Riau"),
    "Sentani": (140.5160, -2.5667, "Papua"),
    "Merauke": (140.4018, -8.4932, "Papua Selatan"),
    "Kupang": (123.6070, -10.1718, "Nusa Tenggara Timur"),
    "Tarakan": (117.5903, 3.3002, "Kalimantan Utara"),
}


@pytest.fixture(scope="module")
def penentu():
    return wilayah.PenentuProvinsi(wilayah.muat_geojson())


def test_geojson_38_provinsi():
    g = wilayah.muat_geojson()
    nama = [f["properties"]["provinsi"] for f in g["features"]]
    assert len(nama) == 38 and len(set(nama)) == 38
    assert "Papua Barat Daya" in nama and "Kalimantan Utara" in nama


def test_ray_casting_persegi():
    persegi = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]])
    lon = np.array([5.0, 15.0, -1.0, 9.99, 5.0])
    lat = np.array([5.0, 5.0, 5.0, 9.99, 15.0])
    hasil = wilayah.titik_dalam_cincin(lon, lat, persegi)
    assert hasil.tolist() == [True, False, False, True, False]


def test_ray_casting_poligon_cekung():
    # Bentuk "C": titik di rongga harus di luar meski kotak pembatasnya masuk.
    c = np.array([[0, 0], [10, 0], [10, 3], [3, 3], [3, 7], [10, 7], [10, 10], [0, 10], [0, 0]], dtype=float)
    hasil = wilayah.titik_dalam_cincin(np.array([6.0, 1.5]), np.array([5.0, 5.0]), c)
    assert hasil.tolist() == [False, True]


def test_kota_mendapat_provinsi_benar(penentu):
    lon = np.array([k[0] for k in KOTA.values()])
    lat = np.array([k[1] for k in KOTA.values()])
    hasil = penentu.tentukan(lon, lat)
    for (nama, (_, _, prov)), h in zip(KOTA.items(), hasil):
        assert h == prov, f"{nama}: {h} != {prov}"


def test_titik_di_laut_dan_luar_negeri_none(penentu):
    # Laut Jawa, Samudra Hindia, Kuala Lumpur (Malaysia), Dili (Timor-Leste).
    hasil = penentu.tentukan(np.array([109.0, 100.0, 101.6869, 125.5736]), np.array([-5.0, -8.0, 3.1390, -8.5586]))
    assert all(h is None for h in hasil)


def test_tandai_dataframe_kosong(penentu):
    df = pd.DataFrame(columns=["lon", "lat"])
    assert "provinsi" in penentu.tandai(df).columns


def test_gabung_provinsi_menjadi_34():
    g = wilayah.gabung_provinsi(wilayah.muat_geojson())
    nama = {f["properties"]["provinsi"] for f in g["features"]}
    assert len(nama) == 34
    assert {"Jakarta Raya", "Yogyakarta", "Bangka Belitung", "Papua", "Papua Barat"} <= nama
    assert not {"Papua Selatan", "Papua Barat Daya", "DKI Jakarta"} & nama
    papua = next(f for f in g["features"] if f["properties"]["provinsi"] == "Papua")
    assert sorted(papua["properties"]["anggota"]) == ["Papua", "Papua Pegunungan", "Papua Selatan", "Papua Tengah"]
    assert papua["geometry"]["type"] == "MultiPolygon"


def test_gabung_tidak_mengubah_jumlah_poligon():
    asli = wilayah.muat_geojson()
    jumlah_asli = sum(len(wilayah._daftar_poligon(f["geometry"])) for f in asli["features"])
    gabung = wilayah.gabung_provinsi(asli)
    assert sum(len(f["geometry"]["coordinates"]) for f in gabung["features"]) == jumlah_asli


def test_nama_gfw():
    assert wilayah.nama_gfw("DKI Jakarta") == "Jakarta Raya"
    assert wilayah.nama_gfw("Papua Tengah") == "Papua"
    assert wilayah.nama_gfw("Riau") == "Riau"


def test_pusat_provinsi_di_dalam_kotak_indonesia():
    pusat = wilayah.pusat_provinsi(wilayah.muat_geojson())
    barat, selatan, timur, utara = wilayah.BBOX_INDONESIA
    assert len(pusat) == 38
    assert pusat["lon"].between(barat, timur).all() and pusat["lat"].between(selatan, utara).all()
