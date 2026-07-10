#!/usr/bin/env python3
"""
Europa-Park Hotel-Verfügbarkeits-Checker
==========================================
Fragt die interne API der Europa-Park Buchungsseite ab und prüft, ob für den
konfigurierten Zeitraum (STARTDATE -> ENDDATE) und die Personenzahl (ADULTS)
eines der Hotels wieder Zimmer frei hat.

Bei einer NEUEN Verfügbarkeit (Hotel war vorher ausgebucht, ist jetzt frei)
wird eine Telegram-Nachricht verschickt. Der letzte bekannte Stand wird in
state.json gespeichert, damit nicht bei jedem Lauf erneut benachrichtigt wird.
"""

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
    """
    Fragt die Europa-Park API genau so ab, wie es der Browser tut.

    Wichtig: Die Seite ist hinter einem Anti-Bot-System (F5/BIG-IP) geschützt,
    das Session-Cookies erwartet. Deshalb besuchen wir zuerst
