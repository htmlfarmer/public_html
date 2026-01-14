import requests
import pandas as pd
import sys
import math
from typing import List

API_KEY = "b01e3890d44f4456820f88b2fd6e5351"

# Occupational SOC / parameter (default)
SOC_CODE = "112011"  # Advertising and Promotions Managers

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def download_soc_codes(out_csv: str = 'soc_codes.csv') -> bool:
    """Attempt to download a list of 6-digit SOC codes from several candidate sources and save to CSV.
    Returns True on success, False otherwise."""
    candidates = [
        # BLS SOC structure (Excel) - common location
        'https://www.bls.gov/soc/2018/soc_2018_structure.xlsx',
        # alternative BLS path
        'https://www.bls.gov/soc/2018/soc_2018_structure.xls',
        # GitHub mirrors (fallbacks)
        'https://raw.githubusercontent.com/ProGovViz/soc/master/soc_2010_6digit.csv',
        'https://raw.githubusercontent.com/txopio/soc-2010/master/soc_2010.csv',
    ]

    for url in candidates:
        try:
            print(f"Trying SOC source: {url}", file=sys.stderr)
            if url.lower().endswith('.xlsx') or url.lower().endswith('.xls'):
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                try:
                    # read excel from bytes
                    df = pd.read_excel(BytesIO(resp.content), dtype=str)
                except Exception as e:
                    print(f"Failed to parse Excel from {url}: {e}", file=sys.stderr)
                    continue
            else:
                # try CSV/plain text
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                try:
                    df = pd.read_csv(BytesIO(resp.content), dtype=str)
                except Exception as e:
                    # last resort: try read_csv from text
                    try:
                        df = pd.read_csv(pd.compat.StringIO(resp.text), dtype=str)
                    except Exception as e2:
                        print(f"Failed to parse CSV from {url}: {e}; {e2}", file=sys.stderr)
                        continue

            # Normalize column names to find code and title
            colmap = {c.lower(): c for c in df.columns}
            code_col = None
            title_col = None
            for k, v in colmap.items():
                if 'code' in k and (k.endswith('soc') or k.endswith('soc_code') or 'soc' in k):
                    code_col = v
                if 'occupation' in k or 'title' in k or 'name' in k:
                    title_col = title_col or v
            # fallback heuristics
            if code_col is None:
                # look for 6-digit numeric-like columns
                for v in df.columns:
                    sample = df[v].dropna().astype(str).head(10).tolist()
                    if all(len(s.strip()) >= 6 and any(ch.isdigit() for ch in s) for s in sample):
                        code_col = v
                        break

            if code_col is None:
                print(f"Could not find SOC code column in {url}", file=sys.stderr)
                continue

            out = df[[code_col] + ([title_col] if title_col and title_col in df.columns else [])].copy()
            out.columns = ['soc_code'] + (['title'] if title_col and title_col in df.columns else [])
            # standardize codes to 6-digit (strip punctuation)
            out['soc_code'] = out['soc_code'].astype(str).str.extract(r'([0-9]{6})')[0]
            out = out.dropna(subset=['soc_code']).drop_duplicates(subset=['soc_code']).reset_index(drop=True)
            out.to_csv(out_csv, index=False)
            print(f"Saved SOC codes to: {out_csv}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"SOC source {url} failed: {e}", file=sys.stderr)
            continue

    print("All SOC download attempts failed.", file=sys.stderr)
    return False



def fetch_all_metro_area_codes() -> List[str]:
    """Download BLS OE area codes and return all metropolitan area codes (prefix 'MT')."""
    # Try multiple candidate URLs with a browser user-agent to avoid simple blocking
    candidates = [
        "https://download.bls.gov/pub/time.series/oe/oe.area",
        "https://download.bls.gov/pub/time.series/oe/oe.area.txt",
        "https://download.bls.gov/pub/time.series/oe/oe.area?raw=true",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0 Safari/537.36"}
    r = None
    for url in candidates:
        try:
            r = requests.get(url, timeout=30, headers=headers)
            r.raise_for_status()
            break
        except Exception:
            r = None
            continue

    if r is None:
        print("Failed to download area codes from known endpoints.", file=sys.stderr)
        return []

    lines = r.text.splitlines()
    codes = []
    for ln in lines:
        if not ln.strip() or ln.startswith('#'):
            continue
        parts = ln.split('\t') if '\t' in ln else ln.split()
        if len(parts) >= 1:
            code = parts[0].strip()
            if code.upper().startswith('MT'):
                codes.append(code)
    return codes


def chunked(iterable, n):
    """Yield successive n-sized chunks from iterable."""
    l = list(iterable)
    for i in range(0, len(l), n):
        yield l[i:i + n]


def build_series_ids(area_codes: List[str], soc_code: str) -> List[str]:
    return [f"OEUM{ac}{soc_code}" for ac in area_codes]


def query_bls_series(series_ids: List[str], startyear: str = "2023", endyear: str = "2023") -> List[dict]:
    """Query BLS API for the provided series_ids (handles batching). Returns rows of dicts."""
    rows = []
    for batch in chunked(series_ids, 50):
        payload = {"seriesid": batch, "startyear": startyear, "endyear": endyear, "registrationkey": API_KEY}
        try:
            resp = requests.post(BLS_API_URL, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"BLS request failed for batch: {e}", file=sys.stderr)
            continue

        results = data.get('Results', {}).get('series', [])
        for series in results:
            sid = series.get('seriesID')
            for item in series.get('data', []):
                rows.append({
                    'series_id': sid,
                    'year': item.get('year'),
                    'period': item.get('period'),
                    'value': item.get('value'),
                    'footnotes': item.get('footnotes')
                })
    return rows


def main():
    # 1) fetch metro area codes
    area_codes = fetch_all_metro_area_codes()
    if not area_codes:
        print("No metro area codes found; aborting.", file=sys.stderr)
        return
    print(f"Found {len(area_codes)} metro area codes; building series IDs...", file=sys.stderr)

    # 2) build series ids for the chosen SOC_CODE
    series_ids = build_series_ids(area_codes, SOC_CODE)

    # 3) query BLS in batches
    print(f"Querying BLS for {len(series_ids)} series (batched)", file=sys.stderr)
    rows = query_bls_series(series_ids)

    # 4) output CSV to stdout
    df = pd.DataFrame(rows)
    # ensure stable column order
    cols = [c for c in ['series_id', 'year', 'period', 'value', 'footnotes'] if c in df.columns]
    df.to_csv(sys.stdout, index=False, columns=cols)


if __name__ == '__main__':
    main()
