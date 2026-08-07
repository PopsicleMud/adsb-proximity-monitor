import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timezone

logger = logging.getLogger("DiscordNotifier")

COMPASS_DIRECTIONS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

def get_compass_direction(heading_deg):
    if heading_deg is None:
        return "N/A"
    try:
        val = int((float(heading_deg) / 22.5) + 0.5)
        return COMPASS_DIRECTIONS[val % 16]
    except Exception:
        return f"{heading_deg}°"

def fetch_planespotters_photo(registration_or_hex):
    """Fetches an aircraft thumbnail photo URL from Planespotters.net API."""
    if not registration_or_hex or len(registration_or_hex.strip()) < 2:
        return None
    
    clean_id = registration_or_hex.strip()
    url = f"https://api.planespotters.net/pub/photos/reg/{urllib.parse.quote(clean_id)}"
    headers = {"User-Agent": "ADSB-Proximity-Monitor/1.0"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                photos = data.get("photos", [])
                if photos and len(photos) > 0:
                    first = photos[0]
                    # Return large thumbnail or standard thumbnail
                    return first.get("thumbnail_large", {}).get("src") or first.get("thumbnail", {}).get("src")
    except Exception as e:
        logger.debug(f"Planespotters photo lookup skipped for {clean_id}: {e}")
    return None

def generate_flightradar24_link(callsign, hex_code):
    """Generates FlightRadar24 link for aircraft."""
    if callsign and callsign.strip():
        clean_callsign = callsign.strip().upper()
        return f"https://www.flightradar24.com/{clean_callsign}"
    elif hex_code and hex_code.strip():
        clean_hex = hex_code.strip().lower()
        return f"https://www.flightradar24.com/data/aircraft/{clean_hex}"
    return "https://www.flightradar24.com"

def generate_adsb_exchange_link(hex_code):
    if hex_code and hex_code.strip():
        return f"https://globe.adsbexchange.com/?icao={hex_code.strip().lower()}"
    return "https://globe.adsbexchange.com"

def build_discord_embed(aircraft_data, distance_km, config):
    """
    Constructs a rich Discord Embed object.
    aircraft_data dict expected keys: hex, flight, registration, type, desc, alt_baro, gs, track, squawk, dbFlags
    """
    hex_code = (aircraft_data.get("hex") or "Unknown").upper()
    callsign = (aircraft_data.get("flight") or "").strip()
    reg = (aircraft_data.get("r") or aircraft_data.get("registration") or "").strip()
    ac_type = (aircraft_data.get("t") or aircraft_data.get("type") or "").strip()
    ac_desc = (aircraft_data.get("desc") or "").strip()
    
    alt = aircraft_data.get("alt_baro", aircraft_data.get("alt_geom", "N/A"))
    if isinstance(alt, (int, float)):
        alt_str = f"{alt:,} ft"
    elif str(alt).lower() == "ground":
        alt_str = "Ground Level 🛬"
    else:
        alt_str = str(alt)
        
    gs = aircraft_data.get("gs", "N/A")
    gs_str = f"{gs} kts" if isinstance(gs, (int, float)) else str(gs)
    
    track = aircraft_data.get("track")
    compass = get_compass_direction(track)
    track_str = f"{track}° ({compass})" if track is not None else "N/A"
    
    squawk = str(aircraft_data.get("squawk", "N/A"))
    is_emergency = squawk in ("7700", "7600", "7500")
    db_flags = aircraft_data.get("dbFlags", 0)
    is_military = bool(db_flags & 1) if isinstance(db_flags, int) else False

    # Choose color badge
    if is_emergency:
        color = 0xFF0000 # Red
        title_prefix = "🚨 EMERGENCY SQUAWK ALERT: "
    elif is_military:
        color = 0x228B22 # Forest Green
        title_prefix = "🎖️ MILITARY AIRCRAFT: "
    else:
        color = 0x00A2FF # Aircraft Sky Blue
        title_prefix = "✈️ PROXIMITY ALERT: "

    display_name = callsign if callsign else (f"Tail {reg}" if reg else f"ICAO {hex_code}")
    title = f"{title_prefix}{display_name}"
    
    # Primary & Secondary Links
    fr24_url = generate_flightradar24_link(callsign, hex_code)
    adsb_url = generate_adsb_exchange_link(hex_code)

    fields = [
        {
            "name": "📏 Distance to Home",
            "value": f"**{distance_km:.2f} km** ({distance_km * 0.539957:.2f} NM)",
            "inline": True
        },
        {
            "name": "🏔️ Altitude",
            "value": f"**{alt_str}**",
            "inline": True
        },
        {
            "name": "💨 Speed & Heading",
            "value": f"{gs_str} | {track_str}",
            "inline": True
        },
        {
            "name": "🆔 Ident / Registration",
            "value": f"Callsign: **{callsign or 'N/A'}**\nTail: **{reg or 'N/A'}**\nHEX: `{hex_code}`",
            "inline": True
        },
        {
            "name": "🛩️ Aircraft Type",
            "value": f"Type: **{ac_type or 'N/A'}**\n{ac_desc or 'No description'}",
            "inline": True
        },
        {
            "name": "⚠️ Squawk Code",
            "value": f"**{squawk}**" + (" 🚨" if is_emergency else ""),
            "inline": True
        },
        {
            "name": "🔗 Flight Tracking",
            "value": f"[▶ Open on FlightRadar24]({fr24_url})\n[🌐 ADSB Exchange Globe]({adsb_url})",
            "inline": False
        }
    ]

    embed = {
        "title": title,
        "url": fr24_url,
        "color": color,
        "fields": fields,
        "footer": {
            "text": f"Receiver: {urllib.parse.urlparse(config['RECEIVER_URL']).netloc or 'pinas'} | ADSB Monitor"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Fetch thumbnail photo if enabled
    if config.get("FETCH_PHOTOS", True):
        photo_target = reg or hex_code
        photo_url = fetch_planespotters_photo(photo_target)
        if photo_url:
            embed["thumbnail"] = {"url": photo_url}

    return embed

def send_discord_webhook(webhook_url, embed_payload):
    """Sends JSON embed payload to Discord Webhook."""
    if not webhook_url or not webhook_url.strip():
        logger.warning("Discord Webhook URL is empty. Notification skipped.")
        return False, "Discord Webhook URL is not configured."

    data = {
        "username": "ADSB Flight Tracker",
        "avatar_url": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/2708.png",
        "embeds": [embed_payload]
    }
    
    try:
        req_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            webhook_url.strip(),
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ADSB-Proximity-Monitor/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status in (200, 204):
                logger.info("Successfully dispatched Discord notification.")
                return True, "Notification sent successfully!"
            else:
                resp_body = response.read().decode('utf-8')
                logger.error(f"Discord returned status {response.status}: {resp_body}")
                return False, f"Discord error {response.status}: {resp_body}"
    except Exception as e:
        logger.error(f"Failed to send Discord webhook: {e}")
        return False, str(e)
