import requests
import pandas as pd
import sys
from io import BytesIO


def download_metro_codes(out_csv: str = 'metro_codes.csv') -> bool:
    """Attempt to download BLS OE area codes (MTxxxxx). If BLS is blocked, try Census CBSA list and convert to MT codes.
    Saves CSV with columns area_code,name (when available). Returns True on success."""
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

    # Primary: BLS OE area file
    candidates = [
        'https://download.bls.gov/pub/time.series/oe/oe.area',
        'https://download.bls.gov/pub/time.series/oe/oe.area.txt',
    ]

    for url in candidates:
        try:
            print(f"Trying OE area source: {url}", file=sys.stderr)
            r = requests.get(url, timeout=30, headers=headers)
            r.raise_for_status()
            lines = r.text.splitlines()
            rows = []
            for ln in lines:
                if not ln.strip() or ln.startswith('#'):
                    continue
                parts = ln.split('\t') if '\t' in ln else ln.split()
                if len(parts) >= 2:
                    code = parts[0].strip()
                    name = parts[1].strip()
                    if code.upper().startswith('MT'):
                        rows.append({'area_code': code, 'name': name})
            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(out_csv, index=False)
                print(f"Saved metro area codes to: {out_csv}", file=sys.stderr)
                return True
        except Exception as e:
            print(f"OE area source {url} failed: {e}", file=sys.stderr)
            continue

    # Fallback: Census CBSA list -> MT + cbsa
    cbsa_candidates = [
        'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2020/delineation-files/list1.xls',
        'https://www2.census.gov/programs-surveys/metro-micro/geographies/reference-files/2019/delineation-files/list1.xls',
    ]
    for url in cbsa_candidates:
        try:
            print(f"Trying Census CBSA source: {url}", file=sys.stderr)
            r = requests.get(url, timeout=30, headers=headers)
            r.raise_for_status()
            df = pd.read_excel(BytesIO(r.content), dtype=str)
            # Common column names: 'CBSA Code' or 'CBSA'
            cols = {c.lower(): c for c in df.columns}
            cbsa_col = cols.get('cbsa code') or cols.get('cbsa') or next((v for k, v in cols.items() if 'cbsa' in k), None)
            title_col = next((v for k, v in cols.items() if 'title' in k or 'name' in k or 'name' in k), None)
            if not cbsa_col:
                print(f"No CBSA column found in {url}", file=sys.stderr)
                continue
            rows = []
            for _, row in df.iterrows():
                code = str(row[cbsa_col]).zfill(5)
                area_code = f"MT{code}"
                name = row[title_col] if title_col and title_col in df.columns else ''
                rows.append({'area_code': area_code, 'name': name})
            if rows:
                outdf = pd.DataFrame(rows).drop_duplicates(subset=['area_code']).reset_index(drop=True)
                outdf.to_csv(out_csv, index=False)
                print(f"Saved metro area codes (from CBSA) to: {out_csv}", file=sys.stderr)
                return True
        except Exception as e:
            print(f"Census CBSA source {url} failed: {e}", file=sys.stderr)
            continue

    print("All metro code download attempts failed.", file=sys.stderr)
    return False


if __name__ == '__main__':
    ok = download_metro_codes()
    sys.exit(0 if ok else 2)
