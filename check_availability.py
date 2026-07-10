#!/usr/bin/env python3
# Europa-Park Hotel-Verfuegbarkeits-Checker
# ==========================================
# Fragt die interne API der Europa-Park Buchungsseite ab und prueft, ob fuer den
# konfigurierten Zeitraum (START_DATE -> END_DATE) und die Personenzahl (ADULTS)
# eines der Hotels wieder Zimmer frei hat.
#
# Bei einer NEUEN Verfuegbarkeit (Hotel war vorher ausgebucht, ist jetzt frei)
# wird eine Telegram-Nachricht verschickt. Der letzte bekannte Stand wird in
# state.json gespeichert, damit nicht bei jedem Lauf erneut benachrichtigt wird.

import json
import os
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# KONFIGURATION - hier ggf. Datum/Personenzahl anpassen
# ---------------------------------------------------------------------------
START_DATE = "2026-07-18"
END_DATE = "2026-07-19"
ADULTS = 2

API_URL = "https://hotelapi.europapark.de/api/hotelavailabilities"
STATE_FILE = Path(__file__).parent / "state.json"

# Diese "Hotels" sind keine echten Zimmer (Zeltplatz/Camping/Caravaning) -
# falls gewünscht, hier den segmentCode eintragen, um sie zu ignorieren.
IGNORE_SEGMENT_CODES: set[str] = set()  # z.B. {"CP", "CN"} um Camping/Caravaning zu ignorieren


RESERVATIONS_PAGE = "https://reservations.europapark.de/selecthotel/"


def fetch_availability() -> dict:
    # Wichtig: Die Seite ist hinter einem Anti-Bot-System (F5/BIG-IP) geschuetzt,
    # das Session-Cookies erwartet. Deshalb besuchen wir zuerst die normale
    # Buchungsseite (wie ein Browser das tun wuerde), sammeln die dabei
    # gesetzten Cookies ein, und nutzen diese dann fuer den eigentlichen API-Call.
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
