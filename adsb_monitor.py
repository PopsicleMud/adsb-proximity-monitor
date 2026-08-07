import math
import time
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("ADSBEngine")

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two points in kilometers using Haversine formula."""
    R = 6371.0  # Earth's mean radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2

    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

class ADSBMonitorEngine:
    def __init__(self, config_mgr):
        self.config_mgr = config_mgr
        self.active_aircraft: Dict[str, dict] = {}  # hex -> aircraft info + tracking stats
        self.alert_history: List[dict] = []         # recent alerts list for web UI
        self.last_fetch_status: dict = {
            "success": False,
            "message": "Initializing...",
            "last_check": None,
            "count": 0,
            "active_url": ""
        }
        self._working_url: Optional[str] = None

    def _discover_and_fetch_aircraft_json(self, primary_url: str) -> Tuple[Optional[dict], str]:
        """Attempts to fetch aircraft.json from primary_url, falling back to standard receiver endpoints if needed."""
        urls_to_try = [primary_url]
        
        # Build candidate fallback endpoints if primary fails
        if primary_url:
            parsed = urllib.parse.urlparse(primary_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            fallbacks = [
                f"{base}/tar1090/data/aircraft.json",
                f"{base}/data/aircraft.json",
                f"{base}:8080/data/aircraft.json",
                f"{base}/dump1090-fa/data/aircraft.json",
                f"{base}/readsb/data/aircraft.json"
            ]
            for fb in fallbacks:
                if fb not in urls_to_try:
                    urls_to_try.append(fb)

        # If we previously found a working URL, prioritize it
        if self._working_url and self._working_url in urls_to_try:
            urls_to_try.remove(self._working_url)
            urls_to_try.insert(0, self._working_url)

        headers = {"User-Agent": "ADSB-Proximity-Monitor/1.0"}
        last_error = "Unknown error"

        for url in urls_to_try:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=4) as response:
                    if response.status == 200:
                        content = response.read().decode('utf-8')
                        data = json.loads(content)
                        self._working_url = url
                        return data, url
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code} on {url}"
            except Exception as e:
                last_error = f"Error reaching {url}: {e}"

        return None, last_error

    def process_cycle(self, notifier_func=None) -> dict:
        """Runs one fetch & proximity evaluation cycle."""
        config = self.config_mgr.get_all()
        primary_url = config.get("RECEIVER_URL", "http://pinas/tar1090/data/aircraft.json")
        home_lat = config.get("HOME_LAT", 37.7749)
        home_lon = config.get("HOME_LON", -122.4194)
        radius_km = config.get("ALERT_RADIUS_KM", 2.0)
        max_alt_ft = config.get("MAX_ALTITUDE_FT", 10000.0)
        cooldown_mins = config.get("COOLDOWN_MINUTES", 15)

        raw_data, status_msg = self._discover_and_fetch_aircraft_json(primary_url)
        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()

        if not raw_data or "aircraft" not in raw_data:
            self.last_fetch_status = {
                "success": False,
                "message": f"Failed to fetch data: {status_msg}",
                "last_check": now.isoformat(),
                "count": 0,
                "active_url": self._working_url or primary_url
            }
            logger.warning(self.last_fetch_status["message"])
            return self.last_fetch_status

        aircraft_list = raw_data.get("aircraft", [])
        self.last_fetch_status = {
            "success": True,
            "message": f"Successfully parsed {len(aircraft_list)} aircraft from feed.",
            "last_check": now.isoformat(),
            "count": len(aircraft_list),
            "active_url": self._working_url
        }

        current_in_range_hexes = set()

        for ac in aircraft_list:
            hex_code = (ac.get("hex") or "").strip().upper()
            if not hex_code:
                continue

            lat = ac.get("lat")
            lon = ac.get("lon")

            # Check if lat/lon available
            if lat is None or lon is None:
                continue

            # Altitude calculation (handling ground vs numeric)
            raw_alt = ac.get("alt_baro", ac.get("alt_geom", 0))
            if str(raw_alt).lower() == "ground":
                alt_ft = 0.0
            else:
                try:
                    alt_ft = float(raw_alt)
                except (ValueError, TypeError):
                    alt_ft = 0.0

            # Proximity calculation
            dist_km = haversine_distance_km(home_lat, home_lon, lat, lon)

            # Check if aircraft meets radius and altitude criteria
            in_geofence = (dist_km <= radius_km) and (alt_ft <= max_alt_ft)

            if in_geofence:
                current_in_range_hexes.add(hex_code)
                
                # Check active tracking state
                if hex_code not in self.active_aircraft:
                    # New aircraft entering geofence
                    self.active_aircraft[hex_code] = {
                        "hex": hex_code,
                        "data": ac,
                        "distance_km": dist_km,
                        "min_distance_km": dist_km,
                        "first_seen": now_ts,
                        "last_seen": now_ts,
                        "alert_sent": False,
                        "cooldown_until": 0
                    }
                else:
                    # Update existing aircraft
                    tracker = self.active_aircraft[hex_code]
                    tracker["data"] = ac
                    tracker["distance_km"] = dist_km
                    tracker["last_seen"] = now_ts
                    if dist_km < tracker["min_distance_km"]:
                        tracker["min_distance_km"] = dist_km

                tracker = self.active_aircraft[hex_code]

                # Check if we should trigger Discord alert
                if not tracker["alert_sent"] and now_ts >= tracker["cooldown_until"]:
                    logger.info(f"Triggering alert for aircraft {hex_code} ({ac.get('flight', 'N/A')}) at {dist_km:.2f} km, {alt_ft} ft!")
                    
                    if notifier_func:
                        success, resp = notifier_func(ac, dist_km, config)
                        if success:
                            tracker["alert_sent"] = True
                            tracker["cooldown_until"] = now_ts + (cooldown_mins * 60)
                            
                            # Record in alert history
                            history_entry = {
                                "timestamp": now.isoformat(),
                                "hex": hex_code,
                                "flight": (ac.get("flight") or "").strip(),
                                "registration": (ac.get("r") or "").strip(),
                                "type": (ac.get("t") or "").strip(),
                                "distance_km": round(dist_km, 2),
                                "altitude_ft": alt_ft,
                                "squawk": str(ac.get("squawk", "N/A")),
                                "status": "Sent"
                            }
                            self.alert_history.insert(0, history_entry)
                            if len(self.alert_history) > 50:
                                self.alert_history.pop()

        # Clean up stale aircraft that left range or haven't been updated for > 2 minutes
        stale_cutoff = now_ts - 120
        stale_hexes = [
            h for h, tr in self.active_aircraft.items()
            if h not in current_in_range_hexes or tr["last_seen"] < stale_cutoff
        ]
        for h in stale_hexes:
            del self.active_aircraft[h]

        return self.last_fetch_status
