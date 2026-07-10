# Europa-Park Hotel-Verfügbarkeits-Monitor

Prüft alle 5 Minuten via GitHub Actions, ob eines der Europa-Park Hotels für
**18.07.2026 → 19.07.2026, 2 Personen** wieder Zimmer frei hat, und schickt
bei einer neuen Verfügbarkeit eine E-Mail.

## Setup (einmalig, ca. 10 Minuten)

### 1. Repository erstellen
Lade diesen Ordner als neues **privates** GitHub-Repository hoch (z.B. via
GitHub Desktop, `gh repo create`, oder Web-Upload).

```bash
cd europapark-monitor
git init
git add .
git commit -m "Initial commit"
gh repo create europapark-monitor --private --source=. --push
```

### 2. Telegram-Bot erstellen (über BotFather)

1. In Telegram nach **@BotFather** suchen und einen Chat starten
2. `/newbot` senden, einen Namen und Username vergeben (z.B. `EuropaParkWatcherBot`)
3. BotFather gibt dir einen **Token** zurück, z.B. `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   → das ist dein `TELEGRAM_BOT_TOKEN`
4. Öffne einen Chat mit deinem neuen Bot und schick ihm eine beliebige Nachricht (z.B. "Hi"),
   damit er dich "kennt" — Bots dürfen sonst nicht von sich aus schreiben
5. Deine **Chat-ID** herausfinden: öffne im Browser
   `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates`
   (Token einsetzen), dort im JSON nach `"chat":{"id": ...}` suchen —
   das ist deine `TELEGRAM_CHAT_ID` (eine Zahl, ggf. negativ bei Gruppen)

### 3. GitHub Secrets hinterlegen

Im Repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name          | Wert                                      |
|-----------------------|--------------------------------------------|
| `TELEGRAM_BOT_TOKEN`  | der Token von BotFather                    |
| `TELEGRAM_CHAT_ID`    | deine Chat-ID (Zahl, aus getUpdates)       |

### 4. Fertig!

Der Workflow läuft automatisch alle 15 Minuten (siehe
`.github/workflows/monitor.yml`). Du kannst ihn auch manuell testen unter
**Actions → Europa-Park Verfügbarkeits-Check → Run workflow**.

## Anpassungen

- **Datum/Personenzahl ändern:** in `check_availability.py` ganz oben
  `START_DATE`, `END_DATE`, `ADULTS` anpassen.
- **Check-Intervall ändern:** in `.github/workflows/monitor.yml` den
  `cron`-Ausdruck anpassen (GitHub Actions erlaubt minimal ca. 5 Minuten,
  ist aber bei "*/5" oft ungenau/verzögert — 15 Minuten ist ein guter
  Kompromiss).
- **Bestimmte Unterkünfte ignorieren** (z.B. Camping/Caravaning, falls dir
  nur "richtige" Hotelzimmer wichtig sind): in `check_availability.py`
  `IGNORE_SEGMENT_CODES` z.B. auf `{"CP", "CN"}` setzen.

## Wie es technisch funktioniert

Das Skript ruft direkt den internen API-Endpunkt auf, den die Buchungsseite
selbst nutzt (`POST https://hotelapi.europapark.de/api/hotelavailabilities`),
und liest daraus pro Hotel das Feld `isAvailable`. Der zuletzt bekannte Stand
wird in `state.json` gespeichert und bei jedem Lauf commitet — so wird nur
bei einer **neuen** Verfügbarkeit eine Telegram-Nachricht verschickt, nicht
bei jedem Check erneut.
