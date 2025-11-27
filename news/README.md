# Pulse — simple global earthquake pulse

This small project fetches earthquake data from USGS and produces a JSON feed (`pulse.json`) that a compact frontend (`pulse.html`) consumes. It displays the earthquake data on a satellite map.

## Features
- Fetches recent earthquake data from USGS.
- Produces `pulse.json` in the web root.
- Frontend shows earthquake markers on an interactive satellite map (Leaflet).
- Magnitude-filtering with markers sized by magnitude.

## Quick start

1.  Install Python dependencies (recommend a virtualenv):

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r news/requirements.txt
    ```

2.  Run the scraper (will run once and refresh every REFRESH_INTERVAL):

    ```bash
    python3 news/pulse.py
    ```

3.  Serve the web root or open `pulse.html` in your browser (access `pulse.json` from the same folder):

    ```bash
    cd /home/asher/public_html
    # quick test server
    python3 -m http.server 8000
    # then open http://localhost:8000/news/pulse.html
    ```

## Next steps / improvements
- Add a small REST API server for more dynamic controls.
- Add clustering for events and a timeline selector (e.g., day/week/month).
- Integrate zoom.earth as a basemap alternative.
