# Kundensicht SYN001

Projektübersicht für synava/medavis zum Jour fixe: Wo steht was je Thema, was ist passiert (Termine, Mails, Tickets), wer ist als Nächstes dran.

- Öffentlich: https://360vier.github.io/syn001-dashboard/ (GitHub Pages aus diesem Repo, `main`, Datei `index.html`)
- Mitentwickeln: 360VIER-Team

## Dateien

| Datei | Inhalt | Wer pflegt |
|---|---|---|
| `kunden-stand.json` | Themen mit Stand-Satz und gesetzten nächsten Schritten, Ereignisse (Termine, Mails, Tickets), Termine, Links | von Hand |
| `regeln.json` | ClickUp-Listen, Angebotsinhalte (Tab „Angebot“), Prüfsummen für die Namensprüfung | selten |
| `erzeugen.py` | liest ClickUp und die beiden JSON-Dateien, schreibt `index.html` (öffentlich) und `kundensicht.html` (Kevins private Vorschau) | Entwicklung |
| `index.html` | erzeugt, nicht von Hand ändern | – |

Live aus ClickUp kommen: „bei euch“ aus der Liste „Eure Aufgaben“ (synava), „bei uns“ aus den Unteraufgaben der Epics mit Status doing/blocked/acceptance; „acceptance client“ erscheint als „bei euch: Abnehmen …“.

## Ablauf

```bash
export CLICKUP_TOKEN=pk_…   # eigener persönlicher Token: ClickUp > Einstellungen > Apps
python3 erzeugen.py         # nur Python-Standardbibliothek
git add -A && git commit -m "…" && git push
```

Nach dem Push ist die Seite nach etwa einer Minute live. Vorher `git pull`, damit keine Änderung des anderen verloren geht.

## Regeln für die Seite

- Kundensprache, per du. Nur dunkles Design prüfen.
- Keine Stunden, Preise, Prozent, Personentage. Keine Vornamen von Personen (synava wie 360VIER); einzige Ausnahme ist die Ansprechperson im Fuß der Seite. `erzeugen.py` bricht ab, wenn so etwas auf der Seite landet; die Namen stehen nur als Prüfsumme in `regeln.json`. Neue Person ergänzen: `python3 -c "import hashlib;print(hashlib.sha256('vorname'.lower().encode()).hexdigest())"` und unter `schutz_hashes` eintragen.
- Keine internen Inhalte (Notetaker-Transkripte, interne Docs, Zugangsdaten, Links mit Zugangsschlüssel). Das Repo ist öffentlich.
- Aussagen nur aus Terminen, Mails, Tickets oder Protokollen; Mails als Betreff nennen, nicht verlinken.
- Nichts an synava schicken: Kevin versendet.
