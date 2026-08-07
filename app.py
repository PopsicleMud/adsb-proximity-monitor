import time
import logging
import threading
from flask import Flask, render_template, request, jsonify

from config import config_mgr
from adsb_monitor import ADSBMonitorEngine
from discord_notifier import build_discord_embed, send_discord_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ADSBApp")

app = Flask(__name__)
engine = ADSBMonitorEngine(config_mgr)

def notification_dispatcher(ac_data, dist_km, config):
    """Wrapper function passed to engine to handle Discord notifications."""
    webhook_url = config.get("DISCORD_WEBHOOK_URL", "")
    embed = build_discord_embed(ac_data, dist_km, config)
    return send_discord_webhook(webhook_url, embed)

def background_monitor_thread():
    """Continuous background thread running ADSB fetch & filter cycles."""
    logger.info("Background ADSB monitoring thread started.")
    while True:
        try:
            engine.process_cycle(notifier_func=notification_dispatcher)
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}", exc_info=True)
        
        poll_interval = config_mgr.get_all().get("POLL_INTERVAL_SEC", 5)
        time.sleep(max(2, poll_interval))

# Start background thread on launch
monitor_thread = threading.Thread(target=background_monitor_thread, daemon=True)
monitor_thread.start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    config = config_mgr.get_all()
    active_aircraft = [
        {
            "hex": hex_code,
            "flight": (item["data"].get("flight") or "").strip(),
            "registration": (item["data"].get("r") or "").strip(),
            "type": (item["data"].get("t") or "").strip(),
            "desc": (item["data"].get("desc") or "").strip(),
            "distance_km": round(item["distance_km"], 2),
            "alt_ft": item["data"].get("alt_baro", item["data"].get("alt_geom", 0)),
            "gs": item["data"].get("gs", 0),
            "track": item["data"].get("track", 0),
            "lat": item["data"].get("lat"),
            "lon": item["data"].get("lon"),
            "squawk": str(item["data"].get("squawk", "N/A")),
            "alert_sent": item["alert_sent"]
        }
        for hex_code, item in engine.active_aircraft.items()
    ]

    return jsonify({
        "fetch_status": engine.last_fetch_status,
        "active_count": len(active_aircraft),
        "active_aircraft": active_aircraft,
        "config": {
            "HOME_LAT": config["HOME_LAT"],
            "HOME_LON": config["HOME_LON"],
            "ALERT_RADIUS_KM": config["ALERT_RADIUS_KM"],
            "MAX_ALTITUDE_FT": config["MAX_ALTITUDE_FT"],
            "RECEIVER_URL": config["RECEIVER_URL"],
            "DISCORD_CONFIGURED": bool(config.get("DISCORD_WEBHOOK_URL")),
        }
    })

@app.route("/api/config", methods=["GET", "POST"])
def handle_config():
    if request.method == "GET":
        return jsonify(config_mgr.get_all())
    
    data = request.json or {}
    config_mgr.update(data)
    logger.info("Configuration updated via API.")
    return jsonify({"success": True, "config": config_mgr.get_all()})

@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(engine.alert_history)

@app.route("/api/test-alert", methods=["POST"])
def send_test_alert():
    data = request.json or {}
    webhook_url = data.get("webhook_url") or config_mgr["DISCORD_WEBHOOK_URL"]
    
    if not webhook_url:
        return jsonify({"success": False, "message": "No Discord Webhook URL provided."}), 400

    test_ac = {
        "hex": "A1B2C3",
        "flight": "TEST789",
        "r": "N789TS",
        "t": "B738",
        "desc": "Boeing 737-800 (Test Flight)",
        "alt_baro": 3500,
        "gs": 210,
        "track": 180,
        "squawk": "1200",
        "lat": config_mgr["HOME_LAT"] + 0.005,
        "lon": config_mgr["HOME_LON"] + 0.005
    }
    
    embed = build_discord_embed(test_ac, 0.75, config_mgr.get_all())
    success, msg = send_discord_webhook(webhook_url, embed)
    return jsonify({"success": success, "message": msg})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
