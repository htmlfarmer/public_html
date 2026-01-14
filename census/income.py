import requests
import pandas as pd
import folium
import branca
import time
import zipfile
from io import BytesIO


# -----------------------------
# CONFIG
# -----------------------------
API_KEY = "9d4c29e072ec00a326361a8146c792f465d49186"
YEAR = "2022"

# Seattle-area ZIP codes
ZIP_CODES = [
    "98101", "98102", "98103", "98104", "98105", "98106", "98107", "98108",
    "98109", "98112", "98115", "98116", "98117", "98118", "98119", "98121",
    "98122", "98125", "98126", "98133", "98134", "98136", "98144", "98146",
    "98154", "98155", "98166", "98168", "98177", "98178", "98188", "98199"
]


# -----------------------------
# Helper: fetch ACS for ZIPs
# -----------------------------
def fetch_zip_metrics(zip_codes, year=YEAR, api_key=API_KEY):
    """Return DataFrame with columns zip,population,median_income for given ZIP codes."""
    if api_key == "YOUR_CENSUS_API_KEY":
        raise SystemExit("Please set API_KEY in the script.")
    url = f"https://api.census.gov/data/{year}/acs/acs5"
    variables = ["B01003_001E", "B19013_001E"]
    rows = []
    for z in zip_codes:
        params = {"get": ",".join(variables), "for": f"zip code tabulation area:{z}", "key": api_key}
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) >= 2:
                vals = data[1]
                pop = pd.to_numeric(vals[0], errors="coerce")
                med = pd.to_numeric(vals[1], errors="coerce")
                rows.append({"zip": z, "population": int(pop) if not pd.isna(pop) else 0, "median_income": int(med) if not pd.isna(med) else None})
            else:
                print(f"Warning: unexpected response for {z}: {data}")
        except Exception as e:
            print(f"Warning: failed for {z}: {e}")
    return pd.DataFrame(rows)


# -----------------------------
# Seattle map (points)
# -----------------------------
def build_seattle_map(df, out_name="income_map_seattle.html"):
    """Geocode ZIPs and build a folium map where color=income, size=population."""
    geocode_url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "income.py (example)"}
    coords = {}
    for z in df["zip"]:
        try:
            gresp = requests.get(geocode_url, params={"q": f"{z}, USA", "format": "json", "limit": 1}, headers=headers, timeout=10)
            gresp.raise_for_status()
            gres = gresp.json()
            if isinstance(gres, list) and len(gres) > 0:
                coords[z] = (float(gres[0]["lat"]), float(gres[0]["lon"]))
        except Exception:
            coords[z] = (39.50, -98.35)
        time.sleep(1)

    # center map on average
    lat0 = sum(c[0] for c in coords.values()) / len(coords)
    lon0 = sum(c[1] for c in coords.values()) / len(coords)
    m = folium.Map(location=[lat0, lon0], zoom_start=10)

    # color scale
    valid_inc = df["median_income"].dropna()
    inc_min = int(valid_inc.min()) if len(valid_inc) > 0 else 0
    inc_max = int(valid_inc.max()) if len(valid_inc) > 0 else 1
    cmap = branca.colormap.linear.YlGnBu_09.scale(inc_min, inc_max)

    pop_min = int(df["population"].min()) if len(df) > 0 else 0
    pop_max = int(df["population"].max()) if len(df) > 0 else 1
    pop_range = pop_max - pop_min if pop_max > pop_min else 1

    for _, row in df.iterrows():
        z = row["zip"]
        lat, lon = coords.get(z, (39.50, -98.35))
        inc = row["median_income"]
        pop = int(row["population"] or 0)
        color = cmap(int(inc)) if pd.notna(inc) else "gray"
        if pop <= 0:
            radius = 4
        else:
            radius = 4 + (pop - pop_min) / pop_range * (20 - 4)
            radius = max(4, min(20, int(radius)))
        popup = folium.Popup(f"ZIP {z}<br>Population: {pop:,}<br>Median income: {('$'+format(int(inc),',d')) if pd.notna(inc) else 'N/A'}", max_width=300)
        folium.CircleMarker(location=[lat, lon], radius=radius, color=color, fill=True, fill_opacity=0.8, popup=popup).add_to(m)

    cmap.caption = "Median household income"
    cmap.add_to(m)
    m.save(out_name)
    print(f"Saved Seattle map to: {out_name}")


# -----------------------------
# Nationwide maps and CSV
# -----------------------------
def build_national_maps(year=YEAR, api_key=API_KEY):
    # 1) Fetch ACS median income and population for all ZCTAs
    print("Fetching ACS median household income and population for all ZCTAs...")
    acs_url = f"https://api.census.gov/data/{year}/acs/acs5"
    params = {"get": "B19013_001E,B01003_001E", "for": "zip code tabulation area:*", "key": api_key}
    resp = requests.get(acs_url, params=params, timeout=60)
    resp.raise_for_status()
    acs_data = resp.json()

    income_map = {}
    pop_map = {}
    for r in acs_data[1:]:
        med = pd.to_numeric(r[0], errors="coerce")
        pop = pd.to_numeric(r[1], errors="coerce").fillna(0).astype(int)
        z = r[2]
        income_map[z] = int(med) if not pd.isna(med) and int(med) > 0 else None
        pop_map[z] = int(pop)

    # 2) Download Gazetteer centroids
    print("Downloading Gazetteer ZCTA centroids...")
    gaz_url = (
        "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/"
        "2020_Gaz_zcta_national.zip"
    )
    gz = requests.get(gaz_url, timeout=60).content
    with zipfile.ZipFile(BytesIO(gz)) as zf:
        txtname = None
        for name in zf.namelist():
            if name.lower().endswith('.txt') and 'zcta' in name.lower():
                txtname = name
                break
        if txtname is None:
            raise RuntimeError('Gazetteer TXT not found in ZIP')
        with zf.open(txtname) as tf:
            gaz = pd.read_csv(tf, sep='\t', dtype=str)
    gaz.columns = [c.strip() for c in gaz.columns]
    lc = {c.lower(): c for c in gaz.columns}
    geo_col = lc.get('geoid') or lc.get('zcta5')
    lat_col = None
    lon_col = None
    for k, v in lc.items():
        if 'intptlat' in k:
            lat_col = v
        if 'intptlong' in k or 'intptlon' in k:
            lon_col = v
    if not geo_col or not lat_col or not lon_col:
        raise RuntimeError('Could not find required columns in Gazetteer file')
    gaz = gaz[[geo_col, lat_col, lon_col]].rename(columns={geo_col: 'ZCTA5CE20', lat_col: 'lat', lon_col: 'lon'})
    gaz['lat'] = pd.to_numeric(gaz['lat'], errors='coerce')
    gaz['lon'] = pd.to_numeric(gaz['lon'], errors='coerce')

    # build points DataFrame and save national CSV
    pts = []
    for _, row in gaz.iterrows():
        z = str(row['ZCTA5CE20']).zfill(5)
        lat = row['lat']
        lon = row['lon']
        if pd.isna(lat) or pd.isna(lon):
            continue
        pts.append({'ZCTA5CE20': z, 'lat': lat, 'lon': lon, 'median_income': income_map.get(z), 'population': pop_map.get(z, 0)})
    pts_df = pd.DataFrame(pts)
    pts_df.to_csv('national.csv', index=False)
    print('Saved national CSV to: national.csv')

    # 3) Try polygon choropleth
    print('Attempting to download ZCTA GeoJSON for polygon choropleth...')
    try:
        mapserver_root = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Boundaries/MapServer?f=json'
        rootr = requests.get(mapserver_root, timeout=30)
        rootr.raise_for_status()
        rootj = rootr.json()
        layer_id = None
        for layer in rootj.get('layers', []):
            name = layer.get('name', '').lower()
            if 'zcta' in name or 'zip' in name:
                layer_id = layer.get('id')
                break
        if layer_id is None:
            raise RuntimeError('ZCTA layer not found on TIGERweb')
        tiger_url = (
            f"https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Boundaries/MapServer/{layer_id}/query?where=1=1&outFields=ZCTA5CE20&f=geojson"
        )
        r = requests.get(tiger_url, timeout=120)
        r.raise_for_status()
        gj = r.json()
        # attach incomes
        for feat in gj.get('features', []):
            z = feat.get('properties', {}).get('ZCTA5CE20')
            feat['properties']['median_income'] = income_map.get(z)

        df_income = pts_df[pts_df['median_income'].notna()][['ZCTA5CE20', 'median_income']]
        if len(df_income) == 0:
            raise RuntimeError('No income data for choropleth')

        m_poly = folium.Map(location=[39.50, -98.35], zoom_start=4, tiles='cartodbpositron')
        folium.Choropleth(
            geo_data=gj,
            name='Median Income',
            data=df_income,
            columns=['ZCTA5CE20', 'median_income'],
            key_on='feature.properties.ZCTA5CE20',
            fill_color='YlGnBu',
            fill_opacity=0.7,
            line_opacity=0.1,
            nan_fill_color='lightgray',
            legend_name='Median household income (USD)',
        ).add_to(m_poly)
        folium.GeoJson(
            gj,
            name='ZCTAs',
            style_function=lambda feature: {'fillOpacity': 0, 'color': '#000000', 'weight': 0.1},
            tooltip=folium.GeoJsonTooltip(fields=['ZCTA5CE20', 'median_income'], aliases=['ZCTA', 'Median income'], localize=True),
        ).add_to(m_poly)
        out_poly = 'income_map_usa.html'
        m_poly.save(out_poly)
        print(f'Saved nationwide choropleth to: {out_poly}')
        return
    except Exception as e:
        print(f'Polygon choropleth unavailable: {e}')

    # 4) Fallback: detailed heatmap + points
    print('Building detailed heatmap + points fallback...')
    from folium.plugins import HeatMap

    m3 = folium.Map(location=[39.50, -98.35], zoom_start=4, tiles='cartodbpositron')

    incomes = [v for v in pts_df['median_income'] if pd.notna(v)]
    max_income = max(incomes) if len(incomes) > 0 else 1
    pops = [v for v in pts_df['population'] if pd.notna(v)]
    max_pop = max(pops) if len(pops) > 0 else 1

    heat_income = [[r['lat'], r['lon'], float(r['median_income']) / float(max_income)] for _, r in pts_df.dropna(subset=['median_income']).iterrows()]
    heat_pop = [[r['lat'], r['lon'], float(r['population']) / float(max_pop)] for _, r in pts_df[pts_df['population'] > 0].iterrows()]

    gradient = {0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 0.8: 'orange', 1.0: 'red'}

    fg_income = folium.FeatureGroup(name='Income heat (median)')
    HeatMap(heat_income, radius=8, blur=12, max_zoom=12, gradient=gradient).add_to(fg_income)
    fg_income.add_to(m3)

    fg_pop = folium.FeatureGroup(name='Population heat')
    HeatMap(heat_pop, radius=8, blur=12, max_zoom=12, gradient={0.2: '#ffffb2', 0.6: '#fecc5c', 1.0: '#fd8d3c'}).add_to(fg_pop)
    fg_pop.add_to(m3)

    valid_inc = pts_df[pts_df['median_income'].notna()]['median_income']
    inc_min = int(valid_inc.min()) if len(valid_inc) > 0 else 0
    inc_max = int(valid_inc.max()) if len(valid_inc) > 0 else 1
    inc_colormap = branca.colormap.linear.YlGnBu_09.scale(inc_min, inc_max)

    pop_min = int(pts_df['population'].min()) if len(pts_df) > 0 else 0
    pop_max = int(pts_df['population'].max()) if len(pts_df) > 0 else 1
    pop_range = pop_max - pop_min if pop_max > pop_min else 1

    fg_points = folium.FeatureGroup(name='ZCTA points (income=color, pop=size)')
    for _, prow in pts_df.iterrows():
        inc = prow['median_income']
        p = int(prow['population'] or 0)
        lat = prow['lat']
        lon = prow['lon']
        color = inc_colormap(int(inc)) if pd.notna(inc) else 'gray'
        if p <= 0:
            radius = 2
        else:
            radius = 2 + (p - pop_min) / pop_range * (14 - 2)
            radius = max(2, min(14, int(radius)))
        popup = folium.Popup(f"ZIP {prow['ZCTA5CE20']}<br>Pop: {p:,}<br>Income: {('$'+format(int(inc),',d')) if pd.notna(inc) else 'N/A'}", max_width=250)
        folium.CircleMarker(location=[lat, lon], radius=radius, color=color, fill=True, fill_opacity=0.8, popup=popup).add_to(fg_points)
    fg_points.add_to(m3)

    folium.LayerControl(collapsed=False).add_to(m3)
    out = 'income_map_usa_heat_detailed.html'
    m3.save(out)
    print(f"Saved nationwide heatmap to: {out}")


if __name__ == '__main__':
    # Build Seattle map
    seattle_df = fetch_zip_metrics(ZIP_CODES)
    if len(seattle_df) > 0:
        build_seattle_map(seattle_df)

    # Build national maps and CSV
    build_national_maps()
