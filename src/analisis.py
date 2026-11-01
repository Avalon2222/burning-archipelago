"""Agregasi dan analisis: titik api per provinsi, per hari, per jam; kehilangan tutupan
pohon per tahun; dan pertemuan keduanya (di mana api sekarang vs di mana hutan hilang)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.wilayah import nama_gfw

URUTAN_KEYAKINAN = ["Rendah", "Nominal", "Tinggi"]
HA_PER_LAPANGAN_BOLA = 0.714          # lapangan sepak bola FIFA 105 x 68 m
HA_JAKARTA = 66_150                    # luas daratan DKI Jakarta (BPS), ~661,5 km2
MG_CO2_PER_MOBIL_TAHUN = 4.6           # emisi rata-rata satu mobil penumpang per tahun (US EPA), ton CO2e


# ---------------------------------------------------------------------------
# Titik api
# ---------------------------------------------------------------------------

def ringkasan_titik(titik: pd.DataFrame) -> dict:
    if titik.empty:
        return {"jumlah": 0, "frp_total": 0.0, "frp_maks": 0.0, "provinsi_teratas": "-", "jumlah_teratas": 0,
                "hari": 0, "per_hari": 0.0, "porsi_malam": 0.0, "porsi_tinggi": 0.0, "di_laut": 0}
    per_prov = titik_per_provinsi(titik)
    hari = titik["tanggal"].nunique()
    return {
        "jumlah": int(len(titik)),
        "frp_total": float(titik["frp"].sum()),
        "frp_maks": float(titik["frp"].max()),
        "provinsi_teratas": per_prov.iloc[0]["provinsi"] if not per_prov.empty else "-",
        "jumlah_teratas": int(per_prov.iloc[0]["jumlah"]) if not per_prov.empty else 0,
        "hari": int(hari),
        "per_hari": len(titik) / max(hari, 1),
        "porsi_malam": float((titik["siang_malam"] == "Malam").mean()),
        "porsi_tinggi": float((titik["keyakinan"] == "Tinggi").mean()),
        "di_laut": int(titik["provinsi"].isna().sum()),
    }


def titik_per_provinsi(titik: pd.DataFrame) -> pd.DataFrame:
    """Jumlah titik, total dan median FRP per provinsi, diurutkan dari yang terbanyak."""
    d = titik.dropna(subset=["provinsi"])
    if d.empty:
        return pd.DataFrame(columns=["provinsi", "jumlah", "frp_total", "frp_median", "porsi_tinggi"])
    g = d.groupby("provinsi", sort=False).agg(
        jumlah=("lat", "size"), frp_total=("frp", "sum"), frp_median=("frp", "median"),
        porsi_tinggi=("keyakinan", lambda s: float((s == "Tinggi").mean())),
    ).reset_index()
    return g.sort_values("jumlah", ascending=False).reset_index(drop=True)


def titik_per_hari(titik: pd.DataFrame) -> pd.DataFrame:
    """Jumlah titik per tanggal WIB, dengan tanggal kosong diisi nol agar garis tidak melompat."""
    if titik.empty:
        return pd.DataFrame(columns=["tanggal", "jumlah", "frp_total"])
    g = titik.groupby("tanggal").agg(jumlah=("lat", "size"), frp_total=("frp", "sum"))
    semua = pd.date_range(min(g.index), max(g.index), freq="D").date
    g = g.reindex(semua, fill_value=0)
    return g.rename_axis("tanggal").reset_index()


def titik_per_jam(titik: pd.DataFrame) -> pd.DataFrame:
    """Jumlah titik per jam WIB. Satelit polar lewat di jam tertentu saja, sehingga grafik ini
    memperlihatkan jadwal lintasan satelit lebih dari perilaku api."""
    if titik.empty:
        return pd.DataFrame({"jam": range(24), "jumlah": 0})
    g = titik["waktu_wib"].dt.hour.value_counts().reindex(range(24), fill_value=0).sort_index()
    return g.rename_axis("jam").reset_index(name="jumlah")


def kepadatan_provinsi(per_prov: pd.DataFrame, tutupan: pd.DataFrame) -> pd.DataFrame:
    """Titik api per 10.000 km2 (1 juta ha) agar provinsi kecil bisa dibandingkan dengan yang besar."""
    luas = tutupan.set_index("provinsi_gfw")["luas_ha"]
    d = per_prov.copy()
    d["provinsi_gfw"] = d["provinsi"].map(nama_gfw)
    d["luas_ha"] = d["provinsi_gfw"].map(luas)
    d["per_juta_ha"] = d["jumlah"] / d["luas_ha"] * 1_000_000
    return d


def kluster_terpadat(titik: pd.DataFrame, ukuran_derajat: float = 0.25, n: int = 8) -> pd.DataFrame:
    """Kotak ukuran_derajat x ukuran_derajat (0,25 derajat ~ 28 km) dengan titik api terbanyak."""
    if titik.empty:
        return pd.DataFrame(columns=["lat", "lon", "jumlah", "frp_total", "provinsi"])
    d = titik.copy()
    d["lat_k"] = (np.floor(d["lat"] / ukuran_derajat) + 0.5) * ukuran_derajat
    d["lon_k"] = (np.floor(d["lon"] / ukuran_derajat) + 0.5) * ukuran_derajat
    g = d.groupby(["lat_k", "lon_k"]).agg(
        jumlah=("lat", "size"), frp_total=("frp", "sum"),
        provinsi=("provinsi", lambda s: s.dropna().mode().iloc[0] if s.notna().any() else "laut/luar negeri"),
    ).reset_index().rename(columns={"lat_k": "lat", "lon_k": "lon"})
    return g.sort_values("jumlah", ascending=False).head(n).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Kehilangan tutupan pohon (GFW / Hansen)
# ---------------------------------------------------------------------------

def tahun_tersedia(tahunan: pd.DataFrame) -> list[int]:
    return sorted(tahunan["tahun"].unique().tolist())


def hilang_nasional(tahunan: pd.DataFrame) -> pd.DataFrame:
    g = tahunan.groupby("tahun", as_index=False).agg(hilang_ha=("hilang_ha", "sum"), hilang_api_ha=("hilang_api_ha", "sum"), emisi_mg=("emisi_mg", "sum"))
    g["porsi_api"] = g["hilang_api_ha"] / g["hilang_ha"].replace(0, np.nan)
    g["kumulatif_ha"] = g["hilang_ha"].cumsum()
    return g


def hilang_per_provinsi(tahunan: pd.DataFrame, tutupan: pd.DataFrame, tahun_awal: int, tahun_akhir: int) -> pd.DataFrame:
    """Total kehilangan pada rentang tahun per provinsi, beserta persentase dari tutupan pohon 2000."""
    d = tahunan[(tahunan["tahun"] >= tahun_awal) & (tahunan["tahun"] <= tahun_akhir)]
    g = d.groupby("provinsi_gfw", as_index=False).agg(hilang_ha=("hilang_ha", "sum"), hilang_api_ha=("hilang_api_ha", "sum"), emisi_mg=("emisi_mg", "sum"))
    g = g.merge(tutupan, on="provinsi_gfw", how="right").fillna({"hilang_ha": 0.0, "hilang_api_ha": 0.0, "emisi_mg": 0.0})
    g["persen_tutupan_2000"] = g["hilang_ha"] / g["tutupan_2000_ha"].replace(0, np.nan) * 100
    g["porsi_api"] = g["hilang_api_ha"] / g["hilang_ha"].replace(0, np.nan)
    return g.sort_values("hilang_ha", ascending=False).reset_index(drop=True)


def tahun_puncak(tahunan: pd.DataFrame) -> pd.DataFrame:
    """Tahun dengan kehilangan terbesar untuk tiap provinsi."""
    idx = tahunan.groupby("provinsi_gfw")["hilang_ha"].idxmax()
    return tahunan.loc[idx, ["provinsi_gfw", "tahun", "hilang_ha"]].rename(columns={"tahun": "tahun_puncak", "hilang_ha": "hilang_puncak_ha"}).reset_index(drop=True)


def ringkasan_gfw(tahunan: pd.DataFrame, tutupan: pd.DataFrame) -> dict:
    nas = hilang_nasional(tahunan)
    terakhir = nas.iloc[-1]
    puncak = nas.loc[nas["hilang_ha"].idxmax()]
    total = float(nas["hilang_ha"].sum())
    tutupan_2000 = float(tutupan["tutupan_2000_ha"].sum())
    return {
        "tahun_awal": int(nas["tahun"].min()),
        "tahun_akhir": int(terakhir["tahun"]),
        "hilang_terakhir_ha": float(terakhir["hilang_ha"]),
        "hilang_api_terakhir_ha": float(terakhir["hilang_api_ha"]),
        "tahun_puncak": int(puncak["tahun"]),
        "hilang_puncak_ha": float(puncak["hilang_ha"]),
        "total_ha": total,
        "tutupan_2000_ha": tutupan_2000,
        "persen_total": total / tutupan_2000 * 100 if tutupan_2000 else float("nan"),
        "emisi_total_mg": float(nas["emisi_mg"].sum()),
        "setara_jakarta": total / HA_JAKARTA,
        "lapangan_per_hari_terakhir": float(terakhir["hilang_ha"]) / HA_PER_LAPANGAN_BOLA / 365,
        "porsi_api_terakhir": float(terakhir["porsi_api"]) if pd.notna(terakhir["porsi_api"]) else float("nan"),
    }


# ---------------------------------------------------------------------------
# Api hari ini vs hutan yang hilang
# ---------------------------------------------------------------------------

def gabung_api_dan_hilang(per_prov: pd.DataFrame, tahunan: pd.DataFrame, tutupan: pd.DataFrame, tahun_awal: int, tahun_akhir: int) -> pd.DataFrame:
    """Satu baris per provinsi GFW: titik api minggu ini (dijumlah ke 34 provinsi) dan kehilangan
    kumulatif pada rentang tahun, keduanya dinormalkan terhadap luas atau tutupan 2000."""
    api = per_prov.copy()
    api["provinsi_gfw"] = api["provinsi"].map(nama_gfw)
    api = api.groupby("provinsi_gfw", as_index=False).agg(titik_api=("jumlah", "sum"), frp_total=("frp_total", "sum"))
    hilang = hilang_per_provinsi(tahunan, tutupan, tahun_awal, tahun_akhir)
    d = hilang.merge(api, on="provinsi_gfw", how="left").fillna({"titik_api": 0, "frp_total": 0.0})
    d["titik_per_juta_ha"] = d["titik_api"] / d["luas_ha"] * 1_000_000
    d["pulau"] = d["provinsi_gfw"].map(pulau)
    return d


def korelasi_peringkat(d: pd.DataFrame, a: str = "titik_per_juta_ha", b: str = "persen_tutupan_2000") -> float:
    """Korelasi Spearman antara dua kolom; NaN bila kurang dari 3 provinsi."""
    x = d[[a, b]].dropna()
    if len(x) < 3:
        return float("nan")
    return float(x[a].rank().corr(x[b].rank()))


PULAU = {
    "Sumatera": ["Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Jambi", "Sumatera Selatan", "Bengkulu", "Lampung", "Bangka Belitung", "Kepulauan Riau"],
    "Jawa": ["Jakarta Raya", "Jawa Barat", "Jawa Tengah", "Yogyakarta", "Jawa Timur", "Banten"],
    "Kalimantan": ["Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur", "Kalimantan Utara"],
    "Sulawesi": ["Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan", "Sulawesi Tenggara", "Gorontalo", "Sulawesi Barat"],
    "Bali & Nusa Tenggara": ["Bali", "Nusa Tenggara Barat", "Nusa Tenggara Timur"],
    "Maluku": ["Maluku", "Maluku Utara"],
    "Papua": ["Papua", "Papua Barat"],
}
_PROVINSI_KE_PULAU = {p: pulau_ for pulau_, daftar in PULAU.items() for p in daftar}


def pulau(provinsi_gfw: str) -> str:
    return _PROVINSI_KE_PULAU.get(provinsi_gfw, "Lainnya")


def hilang_per_pulau(tahunan: pd.DataFrame) -> pd.DataFrame:
    d = tahunan.copy()
    d["pulau"] = d["provinsi_gfw"].map(pulau)
    return d.groupby(["tahun", "pulau"], as_index=False)["hilang_ha"].sum()
