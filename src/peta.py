"""Peta Folium: titik api (lingkaran berwarna FRP), heatmap, dan koroplet kehilangan
tutupan pohon per provinsi."""

from __future__ import annotations

import copy

import folium
import numpy as np
import pandas as pd
from branca.colormap import LinearColormap
from branca.element import MacroElement, Template
from folium.plugins import HeatMap

from src.grafik import SKALA_HILANG

PUSAT_INDONESIA = (-2.3, 118.0)
MAKS_TITIK_PETA = 6000   # di atas ini titik diambil sampelnya agar peta tetap ringan di browser

WARNA_FRP = [(0, "#ffd166"), (5, "#ff9b3d"), (15, "#ff5d1a"), (40, "#e01b1b"), (100, "#8a0b2d")]


def warna_frp(frp: float) -> str:
    """Kuning untuk api kecil, merah tua untuk api sangat kuat (FRP dalam megawatt)."""
    hasil = WARNA_FRP[0][1]
    for ambang, warna in WARNA_FRP:
        if frp >= ambang:
            hasil = warna
    return hasil


def _peta_dasar(pusat=PUSAT_INDONESIA, zoom: int = 5) -> folium.Map:
    m = folium.Map(location=pusat, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ", name="Gelap (Esri)", max_zoom=16,
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics", name="Citra satelit (Esri)", show=False,
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)
    return m


def _sampel(titik: pd.DataFrame, maks: int) -> pd.DataFrame:
    if len(titik) <= maks:
        return titik
    # Pertahankan semua api kuat, ambil sampel acak (tetap) dari sisanya.
    kuat = titik[titik["frp"] >= 15]
    sisa = titik.drop(kuat.index)
    return pd.concat([kuat, sisa.sample(n=max(0, maks - len(kuat)), random_state=7)])


def peta_titik_api(
    titik: pd.DataFrame,
    geojson: dict,
    tampil_titik: bool = True,
    tampil_heatmap: bool = False,
    tampil_batas: bool = True,
    per_prov: pd.DataFrame | None = None,
    pusat=PUSAT_INDONESIA,
    zoom: int = 5,
    maks_titik: int = MAKS_TITIK_PETA,
) -> folium.Map:
    m = _peta_dasar(pusat, zoom)

    if tampil_batas:
        hitung = per_prov.set_index("provinsi")["jumlah"].to_dict() if per_prov is not None else {}
        g = copy.deepcopy(geojson)
        for f in g["features"]:
            f["properties"]["titik"] = int(hitung.get(f["properties"]["provinsi"], 0))
        folium.GeoJson(
            g, name="Batas provinsi",
            style_function=lambda f: {"color": "#9aa0a6", "weight": 0.8, "fillOpacity": 0.0},
            highlight_function=lambda f: {"color": "#ffffff", "weight": 1.6, "fillOpacity": 0.05},
            tooltip=folium.GeoJsonTooltip(fields=["provinsi", "titik"], aliases=["Provinsi", "Titik api"], localize=True),
        ).add_to(m)

    if tampil_heatmap and not titik.empty:
        fg = folium.FeatureGroup(name="Heatmap", show=True)
        HeatMap(titik[["lat", "lon", "frp"]].to_numpy().tolist(), radius=14, blur=16, min_opacity=0.25, max_val=float(titik["frp"].quantile(0.95) or 1)).add_to(fg)
        fg.add_to(m)

    if tampil_titik and not titik.empty:
        fg = folium.FeatureGroup(name="Titik api", show=True)
        d = _sampel(titik, maks_titik).sort_values("frp")
        for r in d.itertuples(index=False):
            waktu = r.waktu_wib.strftime("%d %b %H:%M") if pd.notna(r.waktu_wib) else ""
            prov = r.provinsi if isinstance(r.provinsi, str) else "laut / luar provinsi"
            folium.CircleMarker(
                location=(r.lat, r.lon), radius=2.2 + min(float(r.frp), 100) ** 0.5 * 0.55,
                color=warna_frp(r.frp), weight=0.6, fill=True, fill_color=warna_frp(r.frp), fill_opacity=0.75,
                tooltip=f"FRP {r.frp:.1f} MW · {prov} · {waktu} WIB · {r.satelit} · {r.keyakinan}",
            ).add_to(fg)
        fg.add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    m.get_root().add_child(_legenda_api(len(titik), min(len(titik), maks_titik)))
    return m


def _legenda_api(jumlah: int, ditampilkan: int) -> MacroElement:
    baris = "".join(
        f'<div><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{w};margin-right:6px"></span>FRP ≥ {a} MW</div>'
        for a, w in WARNA_FRP
    )
    catatan = f"<div style='color:#aaa;margin-top:4px'>{ditampilkan:,} dari {jumlah:,} titik digambar</div>" if ditampilkan < jumlah else ""
    html = f"""
    {{% macro html(this, kwargs) %}}
    <div style="position:fixed;bottom:24px;left:12px;z-index:9999;background:rgba(13,15,14,0.88);color:#eee;
                padding:10px 12px;border-radius:8px;font:12px/1.6 Inter,Segoe UI,sans-serif;border:1px solid #333">
      <div style="font-weight:600;margin-bottom:2px">Titik api · ukuran &amp; warna = FRP</div>{baris}{catatan}
    </div>
    {{% endmacro %}}
    """
    macro = MacroElement()
    macro._template = Template(html)
    return macro


def peta_koroplet(
    geojson_gfw: dict,
    hilang: pd.DataFrame,
    metrik: str = "hilang_ha",
    label: str = "Hektare hilang",
    pusat=PUSAT_INDONESIA,
    zoom: int = 5,
) -> folium.Map:
    """Koroplet 34 provinsi GFW. ``hilang`` dari ``analisis.hilang_per_provinsi``."""
    m = _peta_dasar(pusat, zoom)
    nilai = hilang.set_index("provinsi_gfw")
    g = copy.deepcopy(geojson_gfw)
    for f in g["features"]:
        p = f["properties"]
        baris = nilai.loc[p["provinsi"]] if p["provinsi"] in nilai.index else None
        p["nilai"] = float(baris[metrik]) if baris is not None and pd.notna(baris[metrik]) else None
        p["hilang_ha"] = f"{baris['hilang_ha']:,.0f}" if baris is not None else "-"
        p["persen"] = f"{baris['persen_tutupan_2000']:.1f} %" if baris is not None and pd.notna(baris["persen_tutupan_2000"]) else "-"
        p["api"] = f"{baris['porsi_api'] * 100:.1f} %" if baris is not None and pd.notna(baris["porsi_api"]) else "-"
        p["anggota_teks"] = ", ".join(p.get("anggota", [])) if len(p.get("anggota", [])) > 1 else ""

    semua = np.array([f["properties"]["nilai"] for f in g["features"] if f["properties"]["nilai"] is not None], dtype=float)
    vmaks = float(np.nanpercentile(semua, 98)) if semua.size else 1.0
    skala = LinearColormap(SKALA_HILANG, vmin=0, vmax=max(vmaks, 1e-9))
    skala.caption = label

    def gaya(f):
        v = f["properties"]["nilai"]
        return {"fillColor": skala(min(v, vmaks)) if v is not None else "#333", "color": "#0d0f0e", "weight": 0.8, "fillOpacity": 0.82 if v is not None else 0.3}

    folium.GeoJson(
        g, name="Kehilangan tutupan pohon", style_function=gaya,
        highlight_function=lambda f: {"weight": 2, "color": "#ffffff", "fillOpacity": 0.95},
        tooltip=folium.GeoJsonTooltip(
            fields=["provinsi", "hilang_ha", "persen", "api", "anggota_teks"],
            aliases=["Provinsi (GFW)", "Hilang (ha)", "% tutupan 2000", "Porsi akibat kebakaran", "Gabungan"],
        ),
    ).add_to(m)
    skala.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m
