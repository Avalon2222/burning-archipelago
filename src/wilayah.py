"""Batas provinsi dan geometri sederhana: memuat GeoJSON 38 provinsi, menguji titik
di dalam poligon (ray casting dengan numpy), dan menggabungkan provinsi hasil
pemekaran agar cocok dengan pembagian 33/34 provinsi yang dipakai Global Forest Watch."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"

# Kotak pembatas Indonesia (barat, selatan, timur, utara) untuk menyaring umpan regional.
BBOX_INDONESIA = (94.5, -11.5, 141.5, 6.5)

# Nama provinsi di GeoJSON (38 provinsi, BPS) -> nama di tabel Global Forest Watch (GADM 4.1, 34 provinsi).
# Tiga provinsi baru di Papua (2022) dan Papua Barat Daya belum ada di GADM 4.1, sehingga digabung ke induknya.
PEMETAAN_GFW = {
    "DKI Jakarta": "Jakarta Raya",
    "Daerah Istimewa Yogyakarta": "Yogyakarta",
    "Kepulauan Bangka Belitung": "Bangka Belitung",
    "Papua Selatan": "Papua",
    "Papua Tengah": "Papua",
    "Papua Pegunungan": "Papua",
    "Papua Barat Daya": "Papua Barat",
}


def nama_gfw(provinsi: str) -> str:
    """Nama provinsi versi GFW; provinsi yang tidak dipetakan memakai namanya sendiri."""
    return PEMETAAN_GFW.get(provinsi, provinsi)


@lru_cache(maxsize=1)
def muat_geojson(path: Path | str | None = None) -> dict:
    """GeoJSON 38 provinsi, properti ``kode_bps`` dan ``provinsi``."""
    path = Path(path) if path else FOLDER_DATA / "provinsi.geojson"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def gabung_provinsi(geojson: dict, pemetaan: dict[str, str] | None = None) -> dict:
    """Menggabungkan fitur-fitur provinsi menjadi fitur baru sesuai ``pemetaan``.

    Poligon-poligon provinsi anak hanya disambung menjadi satu MultiPolygon (tanpa operasi
    geometri), yang sah karena provinsi tidak saling tumpang tindih. Properti ``provinsi`` fitur
    hasil memakai nama GFW; properti ``anggota`` menyimpan nama-nama provinsi asalnya.
    """
    pemetaan = PEMETAAN_GFW if pemetaan is None else pemetaan
    kelompok: dict[str, dict] = {}
    for fitur in geojson["features"]:
        nama = pemetaan.get(fitur["properties"]["provinsi"], fitur["properties"]["provinsi"])
        poligon = _daftar_poligon(fitur["geometry"])
        if nama not in kelompok:
            kelompok[nama] = {"type": "Feature", "properties": {"provinsi": nama, "anggota": []}, "geometry": {"type": "MultiPolygon", "coordinates": []}}
        kelompok[nama]["geometry"]["coordinates"].extend(poligon)
        kelompok[nama]["properties"]["anggota"].append(fitur["properties"]["provinsi"])
    return {"type": "FeatureCollection", "features": list(kelompok.values())}


def _daftar_poligon(geometri: dict) -> list:
    if geometri["type"] == "Polygon":
        return [copy.deepcopy(geometri["coordinates"])]
    if geometri["type"] == "MultiPolygon":
        return copy.deepcopy(geometri["coordinates"])
    raise ValueError(f"Tipe geometri tidak didukung: {geometri['type']}")


def titik_dalam_cincin(lon: np.ndarray, lat: np.ndarray, cincin: np.ndarray) -> np.ndarray:
    """Uji ray casting: untuk tiap titik, hitung berapa kali sinar mendatar ke kanan memotong
    sisi poligon. Ganjil berarti di dalam. Dihitung sekaligus untuk semua titik dengan numpy."""
    x, y = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
    x1, y1 = cincin[:, 0], cincin[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
    di_dalam = np.zeros(x.shape, dtype=bool)
    for ax, ay, bx, by in zip(x1, y1, x2, y2):
        if ay == by:
            continue  # sisi mendatar tidak pernah dipotong sinar mendatar
        melintang = (ay > y) != (by > y)
        if not melintang.any():
            continue
        x_potong = ax + (y - ay) * (bx - ax) / (by - ay)
        di_dalam ^= melintang & (x < x_potong)
    return di_dalam


class PenentuProvinsi:
    """Menentukan provinsi untuk banyak titik sekaligus.

    Setiap poligon diuji hanya pada titik yang berada di kotak pembatasnya, lalu cincin luar
    dikurangi cincin lubangnya. Titik di laut (di luar semua poligon) mendapat ``None``.
    """

    def __init__(self, geojson: dict | None = None):
        geojson = geojson or muat_geojson()
        self.poligon: list[tuple[str, np.ndarray, list[np.ndarray], tuple]] = []
        for fitur in geojson["features"]:
            nama = fitur["properties"]["provinsi"]
            for poli in _daftar_poligon(fitur["geometry"]):
                luar = np.asarray(poli[0], dtype=float)
                lubang = [np.asarray(c, dtype=float) for c in poli[1:]]
                kotak = (luar[:, 0].min(), luar[:, 1].min(), luar[:, 0].max(), luar[:, 1].max())
                self.poligon.append((nama, luar, lubang, kotak))
        self.nama_provinsi = sorted({f["properties"]["provinsi"] for f in geojson["features"]})

    def tentukan(self, lon, lat) -> np.ndarray:
        lon, lat = np.asarray(lon, dtype=float), np.asarray(lat, dtype=float)
        hasil = np.full(lon.shape, None, dtype=object)
        belum = np.ones(lon.shape, dtype=bool)
        for nama, luar, lubang, (xmin, ymin, xmax, ymax) in self.poligon:
            kandidat = belum & (lon >= xmin) & (lon <= xmax) & (lat >= ymin) & (lat <= ymax)
            if not kandidat.any():
                continue
            idx = np.flatnonzero(kandidat)
            dalam = titik_dalam_cincin(lon[idx], lat[idx], luar)
            for c in lubang:
                dalam &= ~titik_dalam_cincin(lon[idx], lat[idx], c)
            cocok = idx[dalam]
            hasil[cocok] = nama
            belum[cocok] = False
        return hasil

    def tandai(self, df: pd.DataFrame, kolom_lon: str = "lon", kolom_lat: str = "lat") -> pd.DataFrame:
        """Menambahkan kolom ``provinsi`` (None untuk titik di laut atau luar negeri)."""
        df = df.copy()
        df["provinsi"] = self.tentukan(df[kolom_lon].to_numpy(), df[kolom_lat].to_numpy()) if len(df) else []
        return df


def pusat_provinsi(geojson: dict) -> pd.DataFrame:
    """Titik tengah kasar (rata-rata simpul cincin luar terbesar) tiap provinsi, untuk label."""
    baris = []
    for fitur in geojson["features"]:
        terbesar = max(_daftar_poligon(fitur["geometry"]), key=lambda p: len(p[0]))
        arr = np.asarray(terbesar[0], dtype=float)
        baris.append({"provinsi": fitur["properties"]["provinsi"], "lon": arr[:, 0].mean(), "lat": arr[:, 1].mean()})
    return pd.DataFrame(baris)
