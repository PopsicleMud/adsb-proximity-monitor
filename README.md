# ✈️ ADSB Proximity Monitor & Discord Notifier

A Docker application that monitors your local ADSB receiver (`dump1090`, `readsb`, `tar1090`, etc.), detects aircraft flying within a specified geofence radius (default **2.0 km**) and altitude ceiling (default **under 10,000 ft**), and dispatches rich **Discord Webhook notifications** with direct links to **FlightRadar24** and live aircraft photo thumbnails.

Includes a live **Dark-Mode Web Control Panel** with an interactive map showing your home position, geofence circle, active tracked aircraft, and a "Send Test Discord Alert" button.

---

## 🌟 Key Features

- **Automatic Receiver Endpoint Discovery**: Polling feed from `http://pinas/tar1090/data/aircraft.json` (and automatically checks alternative endpoints if needed).
- **Proximity & Altitude Geofencing**: Computes real-time great-circle distance using Haversine math. Filters aircraft within **2.0 km** and below **10,000 feet**.
- **FlightRadar24 Direct Links**: Direct clickable links in Discord notifications to view the live flight on FlightRadar24 (`https://www.flightradar24.com/<callsign>` or by ICAO hex).
- **Aircraft Photo Lookup**: Automatically pulls live high-res aircraft photos from Planespotters.net API.
- **Smart Cooldown & Emergency Badging**: Prevents Discord webhook spam with configurable per-aircraft cooldown timer. Highlights emergency squawks (7700, 7600, 7500) and military flights.
- **Live Web Dashboard & Interactive Map**: Visualizes home location, 2km geofence radius circle, active aircraft positions, and recent alert history on Leaflet dark map.

---

## 🚀 Quick Start with Docker Compose

### 1. Clone & Setup Environment

Copy `.env.example` to `.env` and set your home location and Discord Webhook URL:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Receiver Host (defaults to pinas)
RECEIVER_URL=http://pinas/tar1090/data/aircraft.json

# Your Home Coordinates (Latitude & Longitude)
HOME_LAT=37.7749
HOME_LON=-122.4194

# Notification Criteria (2 km radius, under 10,000 ft altitude)
ALERT_RADIUS_KM=2.0
MAX_ALTITUDE_FT=10000

# Discord Webhook URL
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

### 2. Run Container

```bash
docker compose up -d
```

Access the Web Dashboard at: **`http://localhost:8000`** (or `http://<your-server-ip>:8000`).

---

## 🛠️ Web Control Panel Features

1. **Interactive Map**: Drag the Home marker or click anywhere on the map to visually set your home position and update the geofence circle.
2. **Settings Manager**: Change receiver hostname/URL, radius, altitude ceiling, or webhook URL live without restarting containers.
3. **Send Test Discord Alert**: Test your Discord webhook integration instantly with realistic mock flight data.
4. **Recent Alert History**: Table displaying past alerts dispatched with direct FlightRadar24 buttons.

---

## 📁 Project Structure

```
ADSB/
├── app.py                # Flask Web UI server & background worker manager
├── adsb_monitor.py       # Haversine distance engine & aircraft state tracker
├── discord_notifier.py   # Discord embed builder & Planespotters photo fetcher
├── config.py             # Configuration loader (.env & dynamic JSON)
├── templates/
│   └── index.html        # Web UI dashboard template
├── static/
│   └── style.css         # Dark glassmorphism stylesheet
├── tests/
│   └── test_adsb.py      # Unit test suite
├── Dockerfile            # Container definition
├── docker-compose.yml    # Docker deployment manifest
├── requirements.txt      # Dependencies
└── README.md             # Documentation
```

---

## 🧪 Running Unit Tests

```bash
python -m unittest discover tests
```
