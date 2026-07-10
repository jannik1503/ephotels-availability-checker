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
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
    )

    # Schritt 1: normale Seite besuchen, um Session-/Anti-Bot-Cookies zu bekommen
    initial_resp = session.get(RESERVATIONS_PAGE, timeout=30)
    print(f"[Debug] Erster Seitenaufruf: Status {initial_resp.status_code}", file=sys.stderr)
    print(f"[Debug] Erhaltene Cookies: {list(session.cookies.keys())}", file=sys.stderr)

    payload = {
        "travelData": {
            "lang": "de",
            "queryId": None,
            "dates": {"start": START_DATE, "end": END_DATE},
            "persons": {"adults": ADULTS, "seniors": 0, "children": 0, "babys": 0},
            "accessible": False,
            "dateFromBestPriceCalender": "0001-01-01",
            "guestCameThroughBestPriceCalendar": False,
            "selectedPackagesDataSet": {},
            "babyBedSelected": False,
            "aepSelected": False,
            "logisPrice": 0,
            "activeTicketNotifyMeMailingCodes": [],
            "isComingFromHotelApp": False,
            "appliedRedeemables": [],
            "includedDiscounts": [],
            "hotel": None,
            "selectedHotel": None,
            "selectedRoomType": None,
            "selectedRate": None,
            "selectedAepRulanticaDate": "",
            "reservationDetails": None,
            "promotion": None,
            "specialOffer": None,
            "waitingList": None,
            "dateFromBestPriceCalendar": False,
        },
        "language": "de",
        "employeeOfferData": None,
    }

    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://reservations.europapark.de",
        "Referer": RESERVATIONS_PAGE,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Schritt 2: eigentlicher API-Call, jetzt MIT den gesammelten Cookies
    # WICHTIG: Der Server erwartet hier PUT, nicht POST!
    resp = session.put(API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_available_hotels(data: dict) -> dict[str, dict]:
    # Extrahiert alle Hotels, die fuer den Zeitraum/Personenzahl aktuell
    # verfuegbar sind. Rueckgabe: {segmentCode: {name, price, room_types}}
    available = {}
    for entry in data.get("hotelAvailabilities", []):
        cfg = entry.get("hotelConfiguration", {})
        segment_code = cfg.get("segmentCode", "unknown")

        if segment_code in IGNORE_SEGMENT_CODES:
            continue

        if entry.get("isAvailable"):
            available[segment_code] = {
                "name": cfg.get("hotelName", segment_code),
                "price": entry.get("cheapestPrice"),
                "room_types": entry.get("availableRoomTypeTitles", []),
            }
    return available


def load_previous_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"available_hotels": {}}


def save_state(available_hotels: dict) -> None:
    STATE_FILE.write_text(
        json.dumps({"available_hotels": available_hotels}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def send_telegram_message(text: str) -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=15,
    )
    resp.raise_for_status()


def build_message(new_hotels: dict, changed_hotels: dict) -> str:
    lines = []

    if new_hotels:
        lines.append(f"🎉 *Neue Verfügbarkeit gefunden!*")
        lines.append(f"📅 {START_DATE} → {END_DATE}, {ADULTS} Personen")
        lines.append("")
        for code, info in new_hotels.items():
            lines.append(f"🏨 *{info['name']}*")
            if info.get("price") is not None:
                lines.append(f"   ab {info['price']:.2f} €")
            if info.get("room_types"):
                lines.append("   " + ", ".join(info["room_types"]))
            lines.append("")

    if changed_hotels:
        lines.append("💰 *Preisänderung bei bereits verfügbaren Hotels:*")
        lines.append("")
        for code, change in changed_hotels.items():
            lines.append(f"🏨 *{change['name']}*")
            lines.append(f"   {change['old_price']:.2f} € → {change['new_price']:.2f} €")
            lines.append("")

    lines.append("👉 [Jetzt buchen](https://reservations.europapark.de/selecthotel/)")
    return "\n".join(lines)


def main() -> None:
    try:
        data = fetch_availability()
    except requests.exceptions.HTTPError as exc:
        print(f"Fehler beim Abrufen der API: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(f"Status-Code: {exc.response.status_code}", file=sys.stderr)
            print(f"Antwort (erste 500 Zeichen): {exc.response.text[:500]}", file=sys.stderr)
            print(f"Response-Headers: {dict(exc.response.headers)}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"Fehler beim Abrufen der API: {exc}", file=sys.stderr)
        sys.exit(1)

    current = extract_available_hotels(data)
    previous = load_previous_state().get("available_hotels", {})

    # Neue Verfuegbarkeiten = Hotels, die jetzt da sind, aber vorher nicht
    new_hotels = {code: info for code, info in current.items() if code not in previous}

    # Preisaenderungen = Hotels, die schon vorher UND jetzt verfuegbar sind,
    # aber zu einem anderen Preis
    changed_hotels = {}
    for code, info in current.items():
        if code in previous:
            old_price = previous[code].get("price")
            new_price = info.get("price")
            if old_price is not None and new_price is not None and old_price != new_price:
                changed_hotels[code] = {
                    "name": info["name"],
                    "old_price": old_price,
                    "new_price": new_price,
                }

    if current:
        print("Aktuell verfügbar:")
        for code, info in current.items():
            print(f"  - {info['name']} ({code}) ab {info.get('price')}")
    else:
        print("Aktuell ist kein Hotel für diesen Zeitraum verfügbar.")

    if new_hotels or changed_hotels:
        print(f"\n{len(new_hotels)} neue Verfügbarkeit(en), {len(changed_hotels)} Preisänderung(en) entdeckt!")
        send_telegram_message(build_message(new_hotels, changed_hotels))
    else:
        print("Keine Änderungen seit dem letzten Check.")

    save_state(current)


if __name__ == "__main__":
    main()
