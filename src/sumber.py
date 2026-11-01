"""Pengambilan dan normalisasi data: titik api NASA FIRMS (API dengan MAP_KEY atau CSV
regional terbuka) dan kehilangan tutupan pohon Global Forest Watch / Hansen (unduhan CSV
terbuka dari GFW Data API), dengan data contoh sebagai cadangan saat jaringan gagal."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from src.wilayah import BBOX_INDONESIA, PenentuProvinsi

FOLDER_DATA = Path(__file__).resolve().parent.parent / "data"
FOLDER_SAMPLE = FOLDER_DATA / "sample"
WAKTU_TUNGGU = 30
AGEN = {"User-Agent": "burning-archipelago/1.0 (portofolio; data publik)"}

# CSV regional terbuka FIRMS (tanpa kunci): Asia Tenggara, 7 hari terakhir, VIIRS 375 m.
URL_CSV_TERBUKA = {
    "NOAA-20": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_SouthEast_Asia_7d.csv",
    "NOAA-21": "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-21-viirs-c2/csv/J2_VIIRS_C2_SouthEast_Asia_7d.csv",
}

# API FIRMS dengan MAP_KEY: {key}/{sumber}/{negara}/{hari}[/{tanggal}]; hari 1-10, tanggal YYYY-MM-DD.
URL_API_NEGARA = "https://firms.modaps.eosdis.nasa.gov/api/country/csv/{key}/{sumber}/IDN/{hari}{tanggal}"
SUMBER_API = {"NOAA-20": "VIIRS_NOAA20_NRT", "NOAA-21": "VIIRS_NOAA21_NRT"}
SUMBER_API_ARSIP = {"NOAA-20": "VIIRS_NOAA20_SP", "SNPP": "VIIRS_SNPP_SP"}
URL_STATUS_KEY = "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={key}"

# Global Forest Watch Data API: endpoint unduhan CSV tidak memerlukan kunci.
URL_GFW_UNDUH = "https://data-api.globalforestwatch.org/dataset/{dataset}/{versi}/download/csv"
VERSI_GFW = "v20260424"          # rilis data Hansen/UMD sampai tahun kehilangan 2025
VERSI_GADM = "v4.1"
AMBANG_GFW = 30                  # ambang tutupan kanopi 30 %, standar yang dipakai situs GFW
SQL_GFW_TAHUNAN = (
    "SELECT adm1, umd_tree_cover_loss__year, SUM(umd_tree_cover_loss__ha) AS hilang_ha, "
    "SUM(umd_tree_cover_loss_from_fires__ha) AS hilang_api_ha, "
    'SUM("gfw_gross_emissions_co2e_all_gases__Mg") AS emisi_mg '
    f"FROM data WHERE iso='IDN' AND umd_tree_cover_density_2000__threshold={AMBANG_GFW} "
    "GROUP BY adm1, umd_tree_cover_loss__year"
)
SQL_GFW_TUTUPAN = (
    "SELECT adm1, SUM(umd_tree_cover_extent_2000__ha) AS tutupan_2000_ha, SUM(umd_tree_cover_extent_2010__ha) AS tutupan_2010_ha, "
    "SUM(area__ha) AS luas_ha, SUM(umd_tree_cover_gain__ha) AS tumbuh_ha "
    f"FROM data WHERE iso='IDN' AND umd_tree_cover_density_2000__threshold={AMBANG_GFW} GROUP BY adm1"
)
SQL_GADM_NAMA = "SELECT gid_1, name_1 FROM data WHERE gid_0='IDN' AND adm_level='1'"

KODE_SATELIT = {"N": "SNPP", "N20": "NOAA-20", "N21": "NOAA-21", "1": "NOAA-20", "2": "NOAA-21"}
KOLOM_TITIK = ["waktu_utc", "lat", "lon", "frp", "kecerahan", "keyakinan", "siang_malam", "satelit", "sumber"]


@dataclass
class HasilMuat:
    titik: pd.DataFrame          # titik api dengan kolom provinsi, waktu_wib, tanggal
    gfw_tahunan: pd.DataFrame    # provinsi_gfw, tahun, hilang_ha, hilang_api_ha, emisi_mg
    gfw_tutupan: pd.DataFrame    # provinsi_gfw, luas_ha, tutupan_2000_ha, tutupan_2010_ha, tumbuh_ha
    sumber_titik: str
    offline: bool
    hari: int
    kesalahan: list[str] = field(default_factory=list)
    waktu_ambil: datetime | None = None


# ---------------------------------------------------------------------------
# Titik api FIRMS
# ---------------------------------------------------------------------------

def _ambil_teks(url: str, params: dict | None = None, timeout: int = WAKTU_TUNGGU) -> str:
    r = requests.get(url, params=params, timeout=timeout, headers=AGEN)
    r.raise_for_status()
    return r.text


def normalisasi_firms(df: pd.DataFrame, label_sumber: str) -> pd.DataFrame:
    """CSV FIRMS (VIIRS atau MODIS) -> kolom standar ``KOLOM_TITIK``, disaring ke kotak Indonesia."""
    if df.empty or "latitude" not in df.columns:
        return pd.DataFrame(columns=KOLOM_TITIK)
    d = pd.DataFrame()
    jam = df["acq_time"].astype(str).str.zfill(4)
    d["waktu_utc"] = pd.to_datetime(df["acq_date"].astype(str) + " " + jam.str[:2] + ":" + jam.str[2:], utc=True, errors="coerce")
    d["lat"] = pd.to_numeric(df["latitude"], errors="coerce").round(4)
    d["lon"] = pd.to_numeric(df["longitude"], errors="coerce").round(4)
    d["frp"] = pd.to_numeric(df["frp"], errors="coerce").round(1)
    kolom_terang = "bright_ti4" if "bright_ti4" in df else "brightness"
    d["kecerahan"] = pd.to_numeric(df[kolom_terang], errors="coerce").round(1)
    d["keyakinan"] = df["confidence"].map(_keyakinan)
    d["siang_malam"] = df["daynight"].map({"D": "Siang", "N": "Malam"}).fillna("Siang")
    d["satelit"] = df["satellite"].astype(str).map(lambda s: KODE_SATELIT.get(s, s))
    d["sumber"] = label_sumber
    d = d.dropna(subset=["waktu_utc", "lat", "lon"])
    barat, selatan, timur, utara = BBOX_INDONESIA
    d = d[d["lon"].between(barat, timur) & d["lat"].between(selatan, utara)]
    return d[KOLOM_TITIK].reset_index(drop=True)


def _keyakinan(nilai) -> str:
    """VIIRS memberi low/nominal/high (atau l/n/h); MODIS memberi angka 0-100."""
    s = str(nilai).strip().lower()
    if s in ("low", "l"):
        return "Rendah"
    if s in ("high", "h"):
        return "Tinggi"
    if s in ("nominal", "n"):
        return "Nominal"
    try:
        angka = float(s)
    except ValueError:
        return "Nominal"
    return "Rendah" if angka < 30 else ("Tinggi" if angka >= 80 else "Nominal")


def ambil_csv_terbuka(satelit: str) -> pd.DataFrame:
    teks = _ambil_teks(URL_CSV_TERBUKA[satelit])
    return normalisasi_firms(pd.read_csv(io.StringIO(teks)), f"CSV terbuka {satelit}")


def ambil_api(key: str, hari: int, satelit: str = "NOAA-20", tanggal: str | None = None, arsip: bool = False) -> pd.DataFrame:
    """Memanggil API FIRMS. ``hari`` 1-10; ``tanggal`` opsional (YYYY-MM-DD) untuk mundur ke masa lalu."""
    if not 1 <= hari <= 10:
        raise ValueError("FIRMS hanya melayani 1-10 hari per permintaan")
    kode = (SUMBER_API_ARSIP if arsip else SUMBER_API)[satelit]
    url = URL_API_NEGARA.format(key=key, sumber=kode, hari=hari, tanggal=f"/{tanggal}" if tanggal else "")
    teks = _ambil_teks(url, timeout=90)
    if "," not in teks[:300]:  # FIRMS mengirim kalimat kesalahan (bukan CSV) bila key salah atau kuota habis
        raise RuntimeError(f"FIRMS menolak permintaan: {teks.strip()[:120]}")
    return normalisasi_firms(pd.read_csv(io.StringIO(teks)), f"API {satelit}")


def status_key(key: str) -> dict:
    """Sisa kuota transaksi MAP_KEY (FIRMS membatasi 5000 transaksi per 10 menit)."""
    r = requests.get(URL_STATUS_KEY.format(key=key), timeout=WAKTU_TUNGGU, headers=AGEN)
    r.raise_for_status()
    return r.json()


def tandai_provinsi(titik: pd.DataFrame, penentu: PenentuProvinsi | None = None) -> pd.DataFrame:
    penentu = penentu or PenentuProvinsi()
    d = penentu.tandai(titik)
    d["waktu_wib"] = d["waktu_utc"].dt.tz_convert("Asia/Jakarta")
    d["tanggal"] = d["waktu_wib"].dt.date
    return d


# ---------------------------------------------------------------------------
# Global Forest Watch (Hansen/UMD tree cover loss per provinsi)
# ---------------------------------------------------------------------------

def _unduh_gfw(dataset: str, versi: str, sql: str) -> pd.DataFrame:
    teks = _ambil_teks(URL_GFW_UNDUH.format(dataset=dataset, versi=versi), params={"sql": sql}, timeout=180)
    return pd.read_csv(io.StringIO(teks))


def ambil_nama_gadm() -> dict[int, str]:
    """Peta nomor adm1 GADM 4.1 -> nama provinsi, misalnya 7 -> 'Jakarta Raya'."""
    d = _unduh_gfw("gadm_administrative_boundaries", VERSI_GADM, SQL_GADM_NAMA)
    nomor = d["gid_1"].astype(str).str.extract(r"IDN\.(\d+)_1")[0].astype(int)
    return dict(zip(nomor, d["name_1"].astype(str).str.strip()))


def ambil_gfw() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Mengunduh tabel tahunan dan tabel tutupan dari GFW Data API lalu memberi nama provinsi."""
    nama = ambil_nama_gadm()
    tahunan = _unduh_gfw("gadm__tcl__adm1_change", VERSI_GFW, SQL_GFW_TAHUNAN)
    tutupan = _unduh_gfw("gadm__tcl__adm1_summary", VERSI_GFW, SQL_GFW_TUTUPAN)
    return rapikan_gfw_tahunan(tahunan, nama), rapikan_gfw_tutupan(tutupan, nama)


def rapikan_gfw_tahunan(mentah: pd.DataFrame, nama: dict[int, str]) -> pd.DataFrame:
    d = pd.DataFrame({
        "provinsi_gfw": mentah["adm1"].astype(int).map(nama),
        "tahun": mentah["umd_tree_cover_loss__year"].astype(int),
        "hilang_ha": mentah["hilang_ha"].astype(float).round(1),
        "hilang_api_ha": mentah["hilang_api_ha"].astype(float).round(1),
        "emisi_mg": mentah["emisi_mg"].astype(float).round(0),
    })
    d = d.dropna(subset=["provinsi_gfw"])
    return d.sort_values(["provinsi_gfw", "tahun"]).reset_index(drop=True)


def rapikan_gfw_tutupan(mentah: pd.DataFrame, nama: dict[int, str]) -> pd.DataFrame:
    d = pd.DataFrame({
        "provinsi_gfw": mentah["adm1"].astype(int).map(nama),
        "luas_ha": mentah["luas_ha"].astype(float).round(0),
        "tutupan_2000_ha": mentah["tutupan_2000_ha"].astype(float).round(0),
        "tutupan_2010_ha": mentah["tutupan_2010_ha"].astype(float).round(0),
        "tumbuh_ha": mentah["tumbuh_ha"].astype(float).round(0),
    })
    d = d.dropna(subset=["provinsi_gfw"])
    return d.sort_values("provinsi_gfw").reset_index(drop=True)


def muat_gfw(folder: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    folder = folder or FOLDER_DATA
    return pd.read_csv(folder / "gfw_tahunan.csv"), pd.read_csv(folder / "gfw_tutupan.csv")


# ---------------------------------------------------------------------------
# Data contoh dan pemuat utama
# ---------------------------------------------------------------------------

def muat_meta() -> dict:
    return json.loads((FOLDER_SAMPLE / "meta.json").read_text(encoding="utf-8"))


def muat_sample() -> tuple[pd.DataFrame, dict]:
    titik = pd.read_csv(FOLDER_SAMPLE / "titik_api_7hari.csv.gz")
    titik["waktu_utc"] = pd.to_datetime(titik["waktu_utc"], utc=True)
    return titik, muat_meta()


def muat_titik_api(hari: int = 7, key: str | None = None, paksa_offline: bool = False) -> tuple[pd.DataFrame, str, bool, list[str]]:
    """Urutan: API FIRMS (bila ada key) -> CSV terbuka 7 hari -> data contoh.

    Mengembalikan (titik, label sumber, offline?, daftar kesalahan).
    """
    kesalahan: list[str] = []
    if not paksa_offline:
        if key:
            kerangka = []
            for satelit in SUMBER_API:
                try:
                    kerangka.append(ambil_api(key, hari, satelit))
                except Exception as exc:  # noqa: BLE001 - satu satelit gagal tidak boleh menghentikan yang lain
                    kesalahan.append(f"API {satelit}: {type(exc).__name__}: {str(exc)[:80]}")
            if kerangka and sum(len(k) for k in kerangka) > 0:
                return pd.concat(kerangka, ignore_index=True), f"FIRMS API, {hari} hari terakhir ({', '.join(SUMBER_API)})", False, kesalahan
        kerangka = []
        for satelit in URL_CSV_TERBUKA:
            try:
                kerangka.append(ambil_csv_terbuka(satelit))
            except Exception as exc:  # noqa: BLE001
                kesalahan.append(f"CSV {satelit}: {type(exc).__name__}: {str(exc)[:80]}")
        if kerangka:
            titik = pd.concat(kerangka, ignore_index=True)
            return potong_hari(titik, hari), f"FIRMS CSV terbuka, {min(hari, 7)} hari terakhir ({', '.join(URL_CSV_TERBUKA)})", False, kesalahan
    titik, meta = muat_sample()
    return potong_hari(titik, hari), f"data contoh ({meta['titik_api']['diambil']})", True, kesalahan


def potong_hari(titik: pd.DataFrame, hari: int) -> pd.DataFrame:
    """Menyisakan ``hari`` tanggal terakhir yang ada di tabel (berkas terbuka selalu 7 hari)."""
    if titik.empty or hari >= 7:
        return titik.reset_index(drop=True)
    batas = titik["waktu_utc"].max().normalize() - pd.Timedelta(days=hari - 1)
    return titik[titik["waktu_utc"] >= batas].reset_index(drop=True)


def muat_semua(hari: int = 7, key: str | None = None, paksa_offline: bool = False) -> HasilMuat:
    titik, label, offline, kesalahan = muat_titik_api(hari, key, paksa_offline)
    titik = tandai_provinsi(titik)
    tahunan, tutupan = muat_gfw()
    return HasilMuat(titik=titik, gfw_tahunan=tahunan, gfw_tutupan=tutupan, sumber_titik=label, offline=offline, hari=hari, kesalahan=kesalahan, waktu_ambil=datetime.now(timezone.utc))
