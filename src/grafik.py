"""Grafik Plotly dengan satu gaya gelap yang konsisten."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src import analisis

WARNA_API = "#ff7a1a"
WARNA_API_GELAP = "#b8411a"
WARNA_HUTAN = "#5fbf6b"
WARNA_HILANG = "#e0b24c"
WARNA_ABU = "#8b8f87"
WARNA_KEYAKINAN = {"Rendah": "#6b6f68", "Nominal": "#ff9b3d", "Tinggi": "#ff3d1a"}
WARNA_PULAU = {
    "Sumatera": "#ff7a1a", "Kalimantan": "#e0b24c", "Papua": "#5fbf6b", "Sulawesi": "#4fb3d9",
    "Jawa": "#c77dff", "Bali & Nusa Tenggara": "#ff5d8f", "Maluku": "#9fd356", "Lainnya": "#8b8f87",
}
SKALA_HILANG = ["#1d2b1f", "#4b4a1e", "#8a5a1b", "#c96a16", "#ff7a1a", "#ffc46b"]

TATA_LETAK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, sans-serif", color="#e8e6df", size=12),
    margin=dict(l=10, r=10, t=48, b=10),
    hoverlabel=dict(bgcolor="#1b1e1c", font_size=12),
    legend=dict(orientation="h", y=-0.18, x=0),
)


def _rapikan(fig: go.Figure, judul: str, tinggi: int = 340) -> go.Figure:
    fig.update_layout(title=dict(text=judul, x=0, font=dict(size=15)), height=tinggi, **TATA_LETAK)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)", zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# Titik api
# ---------------------------------------------------------------------------

def batang_provinsi(per_prov: pd.DataFrame, n: int = 12) -> go.Figure:
    d = per_prov.head(n).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["jumlah"], y=d["provinsi"], orientation="h", marker_color=WARNA_API,
        customdata=d[["frp_total", "frp_median"]].to_numpy(),
        hovertemplate="<b>%{y}</b><br>%{x:,} titik api<br>FRP total %{customdata[0]:,.0f} MW · median %{customdata[1]:.1f} MW<extra></extra>",
    ))
    fig.update_layout(xaxis_title="Titik api", yaxis_title=None)
    return _rapikan(fig, f"{n} provinsi dengan titik api terbanyak", tinggi=max(300, 26 * len(d) + 80))


def garis_harian(per_hari: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=per_hari["tanggal"], y=per_hari["jumlah"], marker_color=WARNA_API, name="Titik api",
                hovertemplate="%{x|%d %b}<br>%{y:,} titik api<extra></extra>")
    fig.add_scatter(x=per_hari["tanggal"], y=per_hari["frp_total"], yaxis="y2", mode="lines+markers", name="FRP total (MW)",
                    line=dict(color=WARNA_HILANG, width=2), hovertemplate="%{x|%d %b}<br>FRP total %{y:,.0f} MW<extra></extra>")
    fig.update_layout(yaxis=dict(title="Titik api"), yaxis2=dict(title="FRP (MW)", overlaying="y", side="right", showgrid=False), bargap=0.25)
    return _rapikan(fig, "Titik api per hari (WIB)")


def batang_jam(per_jam: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Bar(x=per_jam["jam"], y=per_jam["jumlah"], marker_color=WARNA_API_GELAP,
                           hovertemplate="%{x:02d}:00 WIB<br>%{y:,} titik<extra></extra>"))
    fig.update_layout(xaxis=dict(title="Jam WIB", dtick=2), yaxis_title="Titik api")
    return _rapikan(fig, "Jam deteksi: jadwal lintasan satelit, bukan jam kebakaran")


def donat_keyakinan(titik: pd.DataFrame) -> go.Figure:
    hitung = titik["keyakinan"].value_counts().reindex(analisis.URUTAN_KEYAKINAN, fill_value=0)
    fig = go.Figure(go.Pie(labels=hitung.index, values=hitung.values, hole=0.6, sort=False,
                           marker=dict(colors=[WARNA_KEYAKINAN[k] for k in hitung.index]),
                           hovertemplate="%{label}: %{value:,} titik (%{percent})<extra></extra>"))
    fig.update_layout(showlegend=True)
    return _rapikan(fig, "Tingkat keyakinan deteksi", tinggi=300)


def histogram_frp(titik: pd.DataFrame) -> go.Figure:
    d = titik["frp"].clip(upper=60)
    fig = go.Figure(go.Histogram(x=d, xbins=dict(start=0, end=62, size=2), marker_color=WARNA_API, hovertemplate="FRP %{x} MW<br>%{y:,} titik<extra></extra>"))
    fig.update_layout(xaxis_title="Fire Radiative Power (MW, dipotong di 60)", yaxis_title="Titik api", bargap=0.05)
    return _rapikan(fig, "Sebaran kekuatan api (FRP)", tinggi=300)


def batang_kepadatan(kepadatan: pd.DataFrame, n: int = 12) -> go.Figure:
    d = kepadatan.dropna(subset=["per_juta_ha"]).sort_values("per_juta_ha", ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(x=d["per_juta_ha"], y=d["provinsi"], orientation="h", marker_color=WARNA_HILANG,
                           customdata=d[["jumlah"]].to_numpy(),
                           hovertemplate="<b>%{y}</b><br>%{x:,.0f} titik per juta ha<br>%{customdata[0]:,} titik<extra></extra>"))
    fig.update_layout(xaxis_title="Titik api per juta hektare", yaxis_title=None)
    return _rapikan(fig, "Kepadatan titik api (dibagi luas provinsi)", tinggi=max(300, 26 * len(d) + 80))


# ---------------------------------------------------------------------------
# Kehilangan tutupan pohon
# ---------------------------------------------------------------------------

def batang_nasional(nas: pd.DataFrame, tahun_sorot: int | None = None) -> go.Figure:
    warna = [WARNA_API if t == tahun_sorot else WARNA_HILANG for t in nas["tahun"]]
    fig = go.Figure()
    fig.add_bar(x=nas["tahun"], y=nas["hilang_ha"] - nas["hilang_api_ha"], name="Kehilangan lain", marker_color=warna, opacity=0.9,
                customdata=nas[["hilang_ha"]].to_numpy(), hovertemplate="%{x}<br>Total %{customdata[0]:,.0f} ha<extra></extra>")
    fig.add_bar(x=nas["tahun"], y=nas["hilang_api_ha"], name="Kehilangan akibat kebakaran", marker_color="#ff3d1a",
                hovertemplate="%{x}<br>Akibat kebakaran %{y:,.0f} ha<extra></extra>")
    fig.update_layout(barmode="stack", xaxis=dict(dtick=2), yaxis_title="Hektare per tahun")
    return _rapikan(fig, "Kehilangan tutupan pohon Indonesia per tahun (ambang kanopi 30 %)", tinggi=360)


def garis_kumulatif(nas: pd.DataFrame, tutupan_2000_ha: float) -> go.Figure:
    persen = nas["kumulatif_ha"] / tutupan_2000_ha * 100
    fig = go.Figure(go.Scatter(x=nas["tahun"], y=persen, mode="lines+markers", fill="tozeroy",
                               line=dict(color=WARNA_HILANG, width=2.5), fillcolor="rgba(224,178,76,0.18)",
                               customdata=nas[["kumulatif_ha"]].to_numpy(),
                               hovertemplate="%{x}<br>%{y:.1f} % dari tutupan 2000<br>%{customdata[0]:,.0f} ha kumulatif<extra></extra>"))
    fig.update_layout(yaxis_title="% tutupan pohon 2000 yang hilang", xaxis=dict(dtick=2))
    return _rapikan(fig, "Kumulatif: berapa persen tutupan pohon tahun 2000 yang sudah hilang", tinggi=320)


def batang_hilang_provinsi(hilang: pd.DataFrame, metrik: str, n: int = 12, label_rentang: str = "") -> go.Figure:
    kolom = {"hilang_ha": ("Hektare hilang", "%{x:,.0f} ha"), "persen_tutupan_2000": ("% tutupan 2000", "%{x:.1f} %"), "emisi_mg": ("Emisi (Mg CO2e)", "%{x:,.0f} Mg CO2e")}[metrik]
    d = hilang.dropna(subset=[metrik]).sort_values(metrik, ascending=False).head(n).iloc[::-1]
    d = d.assign(pulau=d["provinsi_gfw"].map(analisis.pulau))
    fig = go.Figure(go.Bar(x=d[metrik], y=d["provinsi_gfw"], orientation="h",
                           marker_color=[WARNA_PULAU[p] for p in d["pulau"]],
                           customdata=d[["pulau", "hilang_api_ha"]].to_numpy(),
                           hovertemplate="<b>%{y}</b> (%{customdata[0]})<br>" + kolom[1] + "<br>akibat kebakaran %{customdata[1]:,.0f} ha<extra></extra>"))
    fig.update_layout(xaxis_title=kolom[0], yaxis_title=None)
    return _rapikan(fig, f"{n} provinsi teratas{(' · ' + label_rentang) if label_rentang else ''}", tinggi=max(300, 26 * len(d) + 80))


def area_pulau(per_pulau: pd.DataFrame) -> go.Figure:
    urutan = [p for p in analisis.PULAU if p in set(per_pulau["pulau"])]
    fig = px.area(per_pulau, x="tahun", y="hilang_ha", color="pulau", category_orders={"pulau": urutan}, color_discrete_map=WARNA_PULAU)
    fig.update_traces(hovertemplate="%{x} · %{y:,.0f} ha")
    fig.update_layout(xaxis=dict(dtick=2, title=None), yaxis_title="Hektare per tahun", legend_title=None, hovermode="x unified")
    return _rapikan(fig, "Kehilangan per pulau: siapa yang menanggung tiap gelombang", tinggi=360)


def garis_provinsi(tahunan: pd.DataFrame, pilihan: list[str]) -> go.Figure:
    d = tahunan[tahunan["provinsi_gfw"].isin(pilihan)]
    fig = px.line(d, x="tahun", y="hilang_ha", color="provinsi_gfw", markers=True)
    fig.update_traces(hovertemplate="%{x} · %{y:,.0f} ha")
    fig.update_layout(xaxis=dict(dtick=2, title=None), yaxis_title="Hektare per tahun", legend_title=None, hovermode="x unified")
    return _rapikan(fig, "Perbandingan provinsi per tahun", tinggi=360)


# ---------------------------------------------------------------------------
# Api hari ini vs hutan yang hilang
# ---------------------------------------------------------------------------

def sebar_api_vs_hilang(gabung: pd.DataFrame, rho: float) -> go.Figure:
    d = gabung.dropna(subset=["persen_tutupan_2000"]).copy()
    d["ukuran"] = d["tutupan_2000_ha"].clip(lower=1) ** 0.5
    fig = px.scatter(
        d, x="persen_tutupan_2000", y="titik_per_juta_ha", color="pulau", size="ukuran", size_max=38, text="provinsi_gfw",
        color_discrete_map=WARNA_PULAU, hover_name="provinsi_gfw",
        hover_data={"persen_tutupan_2000": ":.1f", "titik_per_juta_ha": ":.0f", "titik_api": ":,", "hilang_ha": ":,.0f", "ukuran": False, "provinsi_gfw": False},
    )
    fig.update_traces(textposition="top center", textfont=dict(size=10, color="#cfcdc5"), marker=dict(opacity=0.85, line=dict(width=0.5, color="#000")))
    fig.update_layout(
        xaxis_title="% tutupan pohon 2000 yang hilang (kumulatif)", yaxis_title="Titik api per juta ha (minggu ini)", legend_title=None,
        annotations=[dict(x=0.99, y=0.98, xref="paper", yref="paper", showarrow=False, align="right", font=dict(size=11, color="#cfcdc5"),
                          text=f"Korelasi peringkat (Spearman) ρ = {rho:.2f}" if rho == rho else "")],
    )
    return _rapikan(fig, "Di mana api menyala minggu ini vs di mana hutan sudah hilang", tinggi=460)


def batang_porsi_api(hilang: pd.DataFrame, n: int = 12) -> go.Figure:
    d = hilang[hilang["hilang_ha"] > 50_000].dropna(subset=["porsi_api"]).sort_values("porsi_api", ascending=False).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(x=d["porsi_api"] * 100, y=d["provinsi_gfw"], orientation="h", marker_color="#ff3d1a",
                           customdata=d[["hilang_api_ha", "hilang_ha"]].to_numpy(),
                           hovertemplate="<b>%{y}</b><br>%{x:.1f} % kehilangan akibat kebakaran<br>%{customdata[0]:,.0f} dari %{customdata[1]:,.0f} ha<extra></extra>"))
    fig.update_layout(xaxis_title="% kehilangan tutupan pohon yang disebabkan kebakaran", yaxis_title=None)
    return _rapikan(fig, "Provinsi yang hutannya paling banyak hilang karena api", tinggi=max(300, 26 * len(d) + 80))
