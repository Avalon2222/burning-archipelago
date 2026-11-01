"""Memperbarui data contoh di data/sample/ dan tabel GFW di data/.

Tidak memerlukan kunci API:

    python scripts/perbarui_sample.py            # titik api 7 hari (NOAA-20 + NOAA-21) dan GFW
    python scripts/perbarui_sample.py --firms    # hanya titik api
    python scripts/perbarui_sample.py --gfw      # hanya tabel kehilangan tutupan pohon

Titik api diambil dari berkas CSV regional terbuka FIRMS (Asia Tenggara, 7 hari), disaring ke
kotak Indonesia, lalu disimpan terkompresi sebagai data/sample/titik_api_7hari.csv.gz. Tabel GFW
diunduh dari endpoint CSV terbuka GFW Data API dan disimpan ke data/gfw_tahunan.csv (kehilangan
per provinsi per tahun) dan data/gfw_tutupan.csv (luas dan tutupan pohon 2000/2010).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))

from src import sumber  # noqa: E402

FOLDER_SAMPLE = AKAR / "data" / "sample"


def perbarui_firms() -> int:
    kerangka = []
    for satelit, url in sumber.URL_CSV_TERBUKA.items():
        print(f"mengambil {satelit}: {url}")
        df = sumber.ambil_csv_terbuka(satelit)
        print(f"  {len(df):,} titik di kotak Indonesia")
        kerangka.append(df)
    semua = pd.concat(kerangka, ignore_index=True)
    semua = semua.sort_values(["waktu_utc", "satelit"]).reset_index(drop=True)
    tujuan = FOLDER_SAMPLE / "titik_api_7hari.csv.gz"
    semua.to_csv(tujuan, index=False)
    print(f"disimpan {tujuan} ({len(semua):,} baris)")
    return len(semua)


def perbarui_gfw() -> int:
    print(f"mengunduh GFW {sumber.VERSI_GFW} ...")
    tahunan, tutupan = sumber.ambil_gfw()
    tahunan.to_csv(AKAR / "data" / "gfw_tahunan.csv", index=False)
    tutupan.to_csv(AKAR / "data" / "gfw_tutupan.csv", index=False)
    print(f"disimpan data/gfw_tahunan.csv ({len(tahunan)} baris, {tahunan['tahun'].min()}-{tahunan['tahun'].max()}) "
          f"dan data/gfw_tutupan.csv ({len(tutupan)} provinsi)")
    return len(tutupan)


def tulis_meta(firms: int | None, gfw: int | None) -> None:
    path = FOLDER_SAMPLE / "meta.json"
    meta = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    sekarang = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if firms is not None:
        meta["titik_api"] = {"diambil": sekarang, "jumlah": firms, "sumber": "FIRMS CSV terbuka Asia Tenggara 7 hari (NOAA-20, NOAA-21)"}
    if gfw is not None:
        meta["gfw"] = {"diambil": sekarang, "provinsi": gfw, "versi": sumber.VERSI_GFW, "ambang_tutupan": sumber.AMBANG_GFW}
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--firms", action="store_true", help="hanya titik api")
    p.add_argument("--gfw", action="store_true", help="hanya tabel GFW")
    a = p.parse_args()
    semua = not (a.firms or a.gfw)
    FOLDER_SAMPLE.mkdir(parents=True, exist_ok=True)
    firms = perbarui_firms() if (semua or a.firms) else None
    gfw = perbarui_gfw() if (semua or a.gfw) else None
    tulis_meta(firms, gfw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
