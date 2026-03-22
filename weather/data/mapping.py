"""Location and market mapping data."""

from typing import Dict

from weather.core.types import Location

LOCATIONS: Dict[str, Location] = {
    "nyc": Location("nyc", "New York City", "KLGA", 40.7772, -73.8726, "F", "us"),
    "chicago": Location("chicago", "Chicago", "KORD", 41.9742, -87.9073, "F", "us"),
    "miami": Location("miami", "Miami", "KMIA", 25.7959, -80.2870, "F", "us"),
    "dallas": Location("dallas", "Dallas", "KDAL", 32.8471, -96.8518, "F", "us"),
    "seattle": Location("seattle", "Seattle", "KSEA", 47.4502, -122.3088, "F", "us"),
    "atlanta": Location("atlanta", "Atlanta", "KATL", 33.6407, -84.4277, "F", "us"),
    "london": Location("london", "London", "EGLC", 51.5048, 0.0495, "C", "eu"),
    "paris": Location("paris", "Paris", "LFPG", 48.9962, 2.5979, "C", "eu"),
    "munich": Location("munich", "Munich", "EDDM", 48.3537, 11.7750, "C", "eu"),
    "ankara": Location("ankara", "Ankara", "LTAC", 40.1281, 32.9951, "C", "eu"),
    "seoul": Location("seoul", "Seoul", "RKSI", 37.4691, 126.4505, "C", "asia"),
    "tokyo": Location("tokyo", "Tokyo", "RJTT", 35.7647, 140.3864, "C", "asia"),
    "shanghai": Location("shanghai", "Shanghai", "ZSPD", 31.1443, 121.8083, "C", "asia"),
    "singapore": Location("singapore", "Singapore", "WSSS", 1.3502, 103.9940, "C", "asia"),
    "lucknow": Location("lucknow", "Lucknow", "VILK", 26.7606, 80.8893, "C", "asia"),
    "tel-aviv": Location("tel-aviv", "Tel Aviv", "LLBG", 32.0114, 34.8867, "C", "asia"),
    "toronto": Location("toronto", "Toronto", "CYYZ", 43.6772, -79.6306, "C", "ca"),
    "sao-paulo": Location("sao-paulo", "Sao Paulo", "SBGR", -23.4356, -46.4731, "C", "sa"),
    "buenos-aires": Location("buenos-aires", "Buenos Aires", "SAEZ", -34.8222, -58.5358, "C", "sa"),
    "wellington": Location("wellington", "Wellington", "NZWN", -41.3272, 174.8052, "C", "oc"),
}

TIMEZONES = {
    "nyc": "America/New_York",
    "chicago": "America/Chicago",
    "miami": "America/New_York",
    "dallas": "America/Chicago",
    "seattle": "America/Los_Angeles",
    "atlanta": "America/New_York",
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "munich": "Europe/Berlin",
    "ankara": "Europe/Istanbul",
    "seoul": "Asia/Seoul",
    "tokyo": "Asia/Tokyo",
    "shanghai": "Asia/Shanghai",
    "singapore": "Asia/Singapore",
    "lucknow": "Asia/Kolkata",
    "tel-aviv": "Asia/Jerusalem",
    "toronto": "America/Toronto",
    "sao-paulo": "America/Sao_Paulo",
    "buenos-aires": "America/Argentina/Buenos_Aires",
    "wellington": "Pacific/Auckland",
}

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def get_location(city_slug: str) -> Location:
    return LOCATIONS[city_slug]

