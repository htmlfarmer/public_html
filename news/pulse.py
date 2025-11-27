import datetime
import json
import requests

# --- CONFIGURATION ---
BASE_DIR = "/home/asher/public_html"
# Save JSON where the frontend will look for it (inside /news/)
JSON_FILE = f"{BASE_DIR}/news/pulse.json"

USGS_MONTH_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson"
USGS_DAY_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"

def save_pulse_json(earthquakes=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Structure the payload
    payload = {
        "meta": {
            "updated": timestamp,
            "status": "Online"
        },
        "earthquakes": earthquakes or []
    }
    
    # Dump to JSON
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)
        
    print(f"Pulse data captured at {timestamp}")


def fetch_usgs_events(url=USGS_MONTH_URL, max_events=300):
    """Fetch USGS GeoJSON and return list of events with basic fields."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        geo = r.json()
        event_list = []
        for feat in geo.get('features', [])[:max_events]:
            props = feat.get('properties', {})
            geom = feat.get('geometry', {})
            coords = geom.get('coordinates') or []
            if not coords or len(coords) < 2:
                continue
            lon, lat = coords[0], coords[1]
            mag = props.get('mag')
            place = props.get('place')
            event_id = feat.get('id')
            time_ms = props.get('time')
            url_link = props.get('url')

            # bucket magnitude: 1.0..9+ using floor
            bucket = int(mag) if mag is not None else None
            if bucket is None:
                mag_bucket = 'unknown'
            elif bucket >= 9:
                mag_bucket = '9+'
            else:
                mag_bucket = str(bucket)

            event_list.append({
                'id': event_id,
                'mag': mag,
                'mag_bucket': mag_bucket,
                'place': place,
                'time_ms': time_ms,
                'time_iso': datetime.datetime.utcfromtimestamp(time_ms/1000).strftime('%Y-%m-%dT%H:%M:%SZ') if time_ms else None,
                'lat': lat,
                'lon': lon,
                'url': url_link,
            })

        return event_list
    except requests.exceptions.RequestException as e:
        print(f'USGS fetch failed: {e}')
        return []

# --- THE CYCLE ---
if __name__ == "__main__":
    events = fetch_usgs_events()
    save_pulse_json(earthquakes=events)
