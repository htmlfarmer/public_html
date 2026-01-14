import requests
import pandas as pd
import sys
from io import BytesIO


def download_soc_codes(out_csv: str = 'soc_codes.csv') -> bool:
    """Attempt to download a list of 6-digit SOC codes from candidate sources and save to CSV.
    Returns True on success, False otherwise."""
    candidates = [
        'https://www.bls.gov/soc/2018/soc_2018_structure.xlsx',
        'https://www.bls.gov/soc/2018/soc_2018_structure.xls',
        # community / mirror CSVs (may or may not exist)
        'https://raw.githubusercontent.com/onetcenter/ONET-SOC-Crosswalk/master/soc_2018.csv',
        'https://raw.githubusercontent.com/ProGovViz/soc/master/soc_2010_6digit.csv',
    ]

    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}

    for url in candidates:
        try:
            print(f"Trying SOC source: {url}", file=sys.stderr)
            resp = requests.get(url, timeout=30, headers=headers)
            resp.raise_for_status()
            content = resp.content

            # Try Excel first if filename suggests so
            if url.lower().endswith(('.xlsx', '.xls')):
                try:
                    df = pd.read_excel(BytesIO(content), dtype=str)
                except Exception as e:
                    print(f"Failed to parse Excel from {url}: {e}", file=sys.stderr)
                    continue
            else:
                try:
                    df = pd.read_csv(BytesIO(content), dtype=str)
                except Exception:
                    # fallback to reading from text
                    try:
                        df = pd.read_csv(pd.compat.StringIO(resp.text), dtype=str)
                    except Exception as e:
                        print(f"Failed to parse CSV from {url}: {e}", file=sys.stderr)
                        continue

            # heuristics to find code and title columns
            cols_lower = {c.lower(): c for c in df.columns}
            code_col = None
            title_col = None
            for k, v in cols_lower.items():
                if 'soc' in k and 'code' in k:
                    code_col = v
                if 'occupation' in k or 'title' in k or 'name' in k:
                    title_col = title_col or v

            if code_col is None:
                # find a column with 6-digit-like entries
                for v in df.columns:
                    sample = df[v].dropna().astype(str).head(20).tolist()
                    if len(sample) and all(len(s.strip()) >= 6 and any(ch.isdigit() for ch in s) for s in sample):
                        code_col = v
                        break

            if code_col is None:
                print(f"Could not identify SOC code column in {url}", file=sys.stderr)
                continue

            out = df[[code_col] + ([title_col] if title_col and title_col in df.columns else [])].copy()
            out.columns = ['soc_code'] + (['title'] if title_col and title_col in df.columns else [])
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


if __name__ == '__main__':
    ok = download_soc_codes()
    sys.exit(0 if ok else 2)
