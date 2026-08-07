import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Logger setup
logger = logging.getLogger("ADSBConfig")

# Base directory for dynamic data persistence
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "RECEIVER_URL": os.getenv("RECEIVER_URL", "http://adsb/tar1090/data/aircraft.json"),
    "HOME_LAT": float(os.getenv("HOME_LAT", "34.5678")),
    "HOME_LON": float(os.getenv("HOME_LON", "-123.4567")),
    "ALERT_RADIUS_KM": float(os.getenv("ALERT_RADIUS_KM", "2.0")),
    "MAX_ALTITUDE_FT": float(os.getenv("MAX_ALTITUDE_FT", "10000")),
    "DISCORD_WEBHOOK_URL": os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/YOUR_DISCORD_WEBHOOK"),
    "POLL_INTERVAL_SEC": float(os.getenv("POLL_INTERVAL_SEC", "5")),
    "COOLDOWN_MINUTES": int(os.getenv("COOLDOWN_MINUTES", "15")),
    "FETCH_PHOTOS": os.getenv("FETCH_PHOTOS", "true").lower() in ("true", "1", "yes"),
    "PRIMARY_LINK": os.getenv("PRIMARY_LINK", "flightradar24"),
    "NOTIFY_EMERGENCY": os.getenv("NOTIFY_EMERGENCY", "true").lower() in ("true", "1", "yes"),
}

class ConfigManager:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Loads configuration from JSON file if exists, overriding default/env vars."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved_config = json.load(f)
                    self._config.update(saved_config)
                logger.info(f"Loaded dynamic runtime configuration from {CONFIG_FILE}")
            except Exception as e:
                logger.error(f"Failed to read {CONFIG_FILE}: {e}")

    def save(self):
        """Saves current runtime configuration to JSON file."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Saved runtime configuration to {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to save {CONFIG_FILE}: {e}")

    def get_all(self):
        return self._config.copy()

    def update(self, new_settings: dict):
        for key, val in new_settings.items():
            if key in DEFAULT_CONFIG:
                # Type conversions
                if isinstance(DEFAULT_CONFIG[key], float):
                    self._config[key] = float(val)
                elif isinstance(DEFAULT_CONFIG[key], int):
                    self._config[key] = int(val)
                elif isinstance(DEFAULT_CONFIG[key], bool):
                    if isinstance(val, str):
                        self._config[key] = val.lower() in ("true", "1", "yes")
                    else:
                        self._config[key] = bool(val)
                else:
                    self._config[key] = str(val)
        self.save()

    def __getitem__(self, item):
        return self._config.get(item, DEFAULT_CONFIG.get(item))

config_mgr = ConfigManager()
