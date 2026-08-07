import unittest
from adsb_monitor import haversine_distance_km, ADSBMonitorEngine
from discord_notifier import build_discord_embed, generate_flightradar24_link

class TestADSBMonitor(unittest.TestCase):
    
    def test_haversine_distance(self):
        # Distance between SFO (37.6213, -122.3790) and OAK (37.7213, -122.2207) ~ 17.5 km
        dist = haversine_distance_km(37.6213, -122.3790, 37.7213, -122.2207)
        self.assertAlmostEqual(dist, 17.5, delta=1.5)

        # Distance to same point should be 0.0
        self.assertEqual(haversine_distance_km(37.0, -122.0, 37.0, -122.0), 0.0)

    def test_flightradar24_link(self):
        # Callsign present
        link1 = generate_flightradar24_link("AAL123", "A1B2C3")
        self.assertEqual(link1, "https://www.flightradar24.com/AAL123")

        # No callsign, hex present
        link2 = generate_flightradar24_link("", "A1B2C3")
        self.assertEqual(link2, "https://www.flightradar24.com/data/aircraft/a1b2c3")

    def test_discord_embed_structure(self):
        mock_ac = {
            "hex": "A1B2C3",
            "flight": "DAL456",
            "r": "N456DL",
            "t": "A320",
            "desc": "Airbus A320",
            "alt_baro": 4500,
            "gs": 240,
            "track": 90,
            "squawk": "1200"
        }
        mock_config = {
            "RECEIVER_URL": "http://pinas/tar1090/data/aircraft.json",
            "FETCH_PHOTOS": False
        }
        embed = build_discord_embed(mock_ac, 1.45, mock_config)
        
        self.assertIn("DAL456", embed["title"])
        self.assertEqual(embed["url"], "https://www.flightradar24.com/DAL456")
        self.assertEqual(len(embed["fields"]), 7)
        self.assertIn("1.45 km", embed["fields"][0]["value"])
        self.assertIn("4,500 ft", embed["fields"][1]["value"])

if __name__ == '__main__':
    unittest.main()
