#!/usr/bin/env python3
"""Kundensicht SYN001 (Projektübersicht für den Jour fixe) aus ClickUp.
Nur Epics vom Typ Epic, Status in Kundensprache, keine Stunden, keine Beschreibungen,
keine Teamnamen. Regeln: regeln.json. Ausgabe: kundensicht.html (Artefakt-Seite ohne Skeleton) und index.html (öffentliche Seite)."""
import json, subprocess, urllib.request, datetime as dt, html, pathlib
HERE = pathlib.Path(__file__).parent
R = json.load(open(HERE / "regeln.json"))
API = "https://api.clickup.com/api/v2"
E = html.escape
def token():
    import os
    if os.environ.get("CLICKUP_TOKEN"): return os.environ["CLICKUP_TOKEN"].strip()
    try:
        return subprocess.run(["security", "find-generic-password", "-s", "greenhouse-meister-clickup", "-w"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        raise SystemExit("Kein ClickUp-Schlüssel: CLICKUP_TOKEN setzen (persönlicher API-Token aus ClickUp, Einstellungen > Apps).")
def get(path, tok):
    req = urllib.request.Request(API + path, headers={"Authorization": tok})
    return json.load(urllib.request.urlopen(req, timeout=60))
def tasks(list_id, tok):
    out, page = [], 0
    while True:
        d = get(f"/list/{list_id}/task?include_closed=true&subtasks=true&page={page}", tok)
        out += d.get("tasks", [])
        if d.get("last_page", True) or not d.get("tasks"): break
        page += 1
    return out
def kstatus(st, nr):
    if str(nr) in R["wartet_auf_kunde"] and st not in ("acceptance client", "done"): return "wartet auf euch"
    for k, vs in R["status_text"].items():
        if st in vs: return k
    return "in Arbeit"
def d(s): return dt.date.fromisoformat(s)
def dd(ms): return dt.datetime.fromtimestamp(int(ms) / 1000).strftime("%d.%m.") if ms else "–"
tok = token()
epics = {}
ALLE = {}
for lid in R["listen_epics"] + [R.get("liste_pm", "1201260000003429")]:
    for t in tasks(lid, tok):
        ALLE[t["id"]] = t
        if lid not in R["listen_epics"]: continue
        if t.get("custom_item_id") == R["epic_typ_id"] and not t.get("parent"):
            nr = int(t["name"].split("·")[0].strip())
            epics[nr] = {"nr": nr, "name": t["name"].split("·", 1)[1].strip(), "st": t["status"]["status"], "abgabe": dd(t.get("due_date")), "url": t.get("url") or "https://app.clickup.com/t/" + t["id"], "id": t["id"]}
for e in epics.values(): e["k"] = kstatus(e["st"], e["nr"])
import re as _re
bei_euch = []
for t in tasks(R.get("liste_synava", "1201260000004980"), tok):
    if t.get("parent") or t["status"]["status"] in ("done", "closed") or t["status"].get("type") == "closed": continue
    if "Anreise" in t["name"]: continue
    bei_euch.append({"wer": "synava", "name": _re.sub(r"\s*·.*$", "", t["name"]).strip(), "bis": dd(t.get("due_date")) if t.get("due_date") else "", "url": t.get("url") or "https://app.clickup.com/t/" + t["id"]})
bei_euch.sort(key=lambda x: (x["bis"] == "", x["bis"][3:5] + x["bis"][:2] if x["bis"] else ""))
KS = json.loads((HERE / "kunden-stand.json").read_text()) if (HERE / "kunden-stand.json").exists() else None
dl = [t for t in tasks(R["liste_decision_log"], tok) if t["status"]["status"] in R["entscheidungen_status_sichtbar"]]
heute = dt.date.today(); stand = dt.datetime.now().strftime("%d.%m.%Y")
chip = {"offen": "c-offen", "in Arbeit": "c-arbeit", "wartet auf euch": "c-wartet", "zur Abnahme bei euch": "c-abnahme", "abgenommen": "c-fertig"}
# Zeitstrahl
Z = R["zeitstrahl"]; t0, t1 = d(Z["start"]), d(Z["ende"]); span = (t1 - t0).days
def pct(day): return max(0, min(100, (d(day) - t0).days / span * 100))
def phase_status(ph):
    ks = [epics[n]["k"] for n in ph["epics"] if n in epics]
    if ks and all(k == "abgenommen" for k in ks): return "fertig"
    if any(k in ("in Arbeit", "wartet auf euch", "zur Abnahme bei euch") for k in ks): return "aktiv"
    return "geplant"
monate = []
m = dt.date(t0.year, t0.month, 1)
while m <= t1:
    monate.append(m); m = dt.date(m.year + (m.month == 12), (m.month % 12) + 1, 1)
mon_html = "".join(f'<span style="left:{pct(max(m, t0).isoformat()):.1f}%">{m.strftime("%b")}</span>' for m in monate if m >= t0 or (m.month, m.year) == (t0.month, t0.year))
ph_html = ""
for ph in Z["phasen"]:
    l, r = pct(ph["von"]), pct(ph["bis"])
    ph_html += f'<div class="ph ph-{phase_status(ph)}" style="left:{l:.1f}%;width:{r-l:.1f}%" title="{E(ph["name"])}: {ph["von"][8:]}.{ph["von"][5:7]}. bis {ph["bis"][8:]}.{ph["bis"][5:7]}."><span>{E(ph["name"])}</span></div>'
ms_html = "".join(f'<div class="ms{" ms-done" if ms.get("erledigt") else ""}{" ms-alt" if i % 2 else ""}" style="left:{pct(ms["datum"]):.1f}%"><i></i><span>{E(ms["text"])}<br><b>{d(ms["datum"]).strftime("%d.%m.")}</b></span></div>' for i, ms in enumerate(Z["meilensteine"]))
heute_html = f'<div class="now" style="left:{pct(heute.isoformat()):.1f}%"><span>heute</span></div>' if t0 <= heute <= t1 else ""
# Ergebnisse je Phase
erg_html = ""
for ph in Z["phasen"]:
    erg_html += f'<h2>{E(ph["name"])}</h2>'
    for n in ph["epics"]:
        e = epics.get(n)
        if not e: continue
        hint = R["hinweis"].get(str(n), "")
        erg_html += (f'<div class="r"><div class="t">{E(R["ergebnis"].get(str(n), e["name"]))}' + (f'<div class="hint">{E(hint)}</div>' if hint else "") + '</div>'
                     f'<span class="c {chip[e["k"]]}">{E(e["k"])}</span><span class="d">{E(e["abgabe"])}</span></div>')
scope_html = "".join(f'<div class="r r2"><div class="t"><span class="nr">{n}</span>{E(epics[n]["name"])}<div class="hint">{E(R["scope"].get(str(n), ""))}</div></div><span class="c {chip[epics[n]["k"]]}">{E(epics[n]["k"])}</span></div>' for n in sorted(epics))
li = lambda items: "".join(f'<li><span>{E(a)}</span><span>{E(b)}</span></li>' for a, b in items)
next_html = li([(x["datum"], x["text"]) for x in R["naechste_schritte"]])
mitw_html = li([(x["wann"], x["text"]) for x in R["mitwirkung"]])
term_html = li([(x["datum"], x["text"]) for x in R["termine"]])
ents_html = li([(t["name"].split("·")[0].strip(), t["name"].split("·", 1)[1].strip()) for t in sorted(dl, key=lambda x: x["name"])]) if dl else f'<li><span></span><span class="muted">{E(R["entscheidungen_fallback"])}</span></li>'
n_fertig = sum(e["k"] == "abgenommen" for e in epics.values()); n_aktiv = sum(e["k"] in ("in Arbeit", "wartet auf euch", "zur Abnahme bei euch") for e in epics.values())

_ag = R.get("agenda")
agenda_html = ""
if _ag and d(_ag["datum"]) >= dt.date.today():
    agenda_html = f'<h2>{E(_ag["titel"])}</h2><div class="ag"><ul>' + "".join(
        f'<li><span>{i}</span><span><b>{E(p["t"])}</b><div class="hint">{E(p["h"])}</div></span></li>' for i, p in enumerate(_ag["punkte"], 1)) + "</ul></div>"

_li = R.get("leitidee"); _le = R.get("leistung")
leit_html = ""
if _li:
    leit_html = f'<h2>{E(_li["titel"])}</h2><p class="lsub">{E(_li["quelle"])}</p><div class="li3">' + "".join(f'<div><b>{E(p["t"])}</b><span>{E(p["h"])}</span></div>' for p in _li["punkte"]) + "</div>"
leist_html = ""
if _le:
    parts = [f'<h2>{E(_le["titel"])}</h2><p class="lsub">{E(_le["sub"])}</p>']
    for bname, nrs in _le["bloecke"]:
        cards = []
        for n in nrs:
            p = _le["pos"][str(n)]; e = epics.get(n)
            meta = f'<span class="c {chip[e["k"]]}">{E(e["k"])}</span><span class="d">{E(e["abgabe"])}</span>' if e else ""
            cards.append(f'<div class="cd"><div class="top"><h3><i>{n}</i>{E(p["e"])}</h3><div class="meta">{meta}</div></div><div class="lst">{E(p["l"])}</div><div class="sk">{E(p["s"])}</div><div class="kl"><small>Gemeinsam klären</small>{E(p["k"])}</div></div>')
        parts.append(f'<div class="bl">{E(bname)}</div><div class="cards">{"".join(cards)}</div>')
    leist_html = "".join(parts)

_k = R["kompakt"]; _le = R["leistung"]
fr = "".join(f'<div><b>{E(t)}</b><ul>' + "".join(f"<li>{E(q)}</li>" for q in qs) + "</ul></div>" for t, qs in _k["fragen"])
mt = '<div class="row"><span>Meilenstein</span><span>Laut Angebot</span><span>Ergebnisse</span><span>Euer Wunsch (Fragebogen 03.11.)</span></div>' + "".join(
    f'<div class="row"><b>{E(x["m"])}</b><span>{E(x["a"])}</span><span>{E(x["e"])}</span><span class="w">{E(x["w"])}</span></div>' for x in _k["meilensteine"])
neu_je_nr = {}
ep = ""
for bname, nrs in _le["bloecke"]:
    ep += f'<div class="gh">{E(bname)}</div>'
    for n in nrs:
        p = _le["pos"][str(n)]; e = epics.get(n)
        chipx = f'<span class="c {chip[e["k"]]}">{E(e["k"])}</span>' if e else ""
        nx = neu_je_nr.get(n) if KS else None
        neu = f'<em class="neu">Neu {E(d(nx["datum"]).strftime("%d.%m."))}: {E(nx["text"].split(":")[0])}</em>' if nx else ""
        _tt = f'<a href="{E(e["url"])}" target="_blank" rel="noopener">{E(p["e"])}</a>' if e else E(p["e"])
        ep += f'<div class="row"><span class="n">{n}</span><div class="t"><b>{_tt}</b><span>{E(p["l"])}</span>{neu}</div>{chipx}</div>'
_w = _k["weg"]; _cls = {"erledigt": "f-done", "jetzt": "f-now", "Ziel": "f-goal"}
flow = '<div class="ar">→</div>'.join(f'<div class="st {_cls.get(x["s"], "")}"><em>{E(x["s"]) if x["s"] else "&nbsp;"}</em><b>{E(x["t"])}</b><span>{E(x["h"])}</span></div>' for x in _w["schritte"])
AKTIV = {"doing": "in Arbeit", "blocked": "blockiert", "acceptance internal": "in Prüfung bei uns", "deployment": "in Arbeit", "acceptance client": "zur Abnahme bei euch"}
_epic_nr = {e["id"]: e["nr"] for e in epics.values()}
def _sauber(n):
    n = _re.sub(r"^\s*\d+(?:\.\d+)?\s*·\s*", "", n)
    return _re.sub(r"^(?:IA|UX|Delivery|PM)\s*•\s*", "", n).strip()
arbeit = {}
for t in ALLE.values():
    nr = _epic_nr.get(t.get("parent"))
    st = t["status"]["status"]
    if nr and st in AKTIV:
        arbeit.setdefault(nr, []).append({"name": _sauber(t["name"]), "st": AKTIV[st], "url": t.get("url") or "https://app.clickup.com/t/" + t["id"], "bei_euch": st == "acceptance client"})
# Wo steht was: je Thema Stand, Zuletzt (Termine, Mails, Tickets), Als Nächstes (live aus ClickUp + gesetzt)
TH = KS["themen"]; EV = sorted(KS["ereignisse"], key=lambda x: x["datum"], reverse=True)
TNAME = {t["id"]: t["titel"] for t in TH}
SRC = {"termin": "Termin", "mail": "Mail", "ticket": "Ticket"}
WER = {"euch": ("bei euch", "w-syn"), "uns": ("bei uns", "w-360"), "gemeinsam": ("gemeinsam", "w-gem")}
def _thema_fuer(name):
    for t in TH:
        if any(_re.search(r"\b" + _re.escape(w) + r"\b", name) for w in t["stichworte"]): return t["id"]
    return TH[0]["id"]
def _tag(s): return d(s).strftime("%d.%m.")
def _links(x):
    o = ""
    if x.get("link"): o += f' <a href="{E(x["link"])}" target="_blank" rel="noopener">{E(x.get("link_text") or "ansehen")} ↗</a>'
    if x.get("ticket"): o += f' <a href="https://app.clickup.com/t/{E(x["ticket"])}" target="_blank" rel="noopener">Ticket ↗</a>'
    if x.get("mail"): o += f' <span class="mail">· {E(x["mail"])}</span>'
    return o
nx = {t["id"]: [] for t in TH}
for x in bei_euch: nx[_thema_fuer(x["name"])].append({"wer": "euch", "text": x["name"], "bis": x["bis"], "url": x["url"]})
_nr_thema = {n: t["id"] for t in TH for n in t["epics"]}
for n, xs in arbeit.items():
    for x in xs:
        nx[_nr_thema.get(n, TH[0]["id"])].append({"wer": "euch" if x["bei_euch"] else "uns", "text": ("Abnehmen: " if x["bei_euch"] else "") + x["name"], "bis": "", "url": x["url"], "st": None if x["bei_euch"] else x["st"]})
for t in TH:
    for x in t.get("naechstes", []): nx[t["id"]].append({"wer": x["wer"], "text": x["text"], "bis": x.get("bis", ""), "url": x.get("url")})
_wo = {"euch": 0, "gemeinsam": 1, "uns": 2}
def _row_n(x):
    w, c = WER[x["wer"]]
    tk = f'<a href="{E(x["url"])}" target="_blank" rel="noopener">Ticket ↗</a>' if x.get("url") else '<span class="mut2">ohne Ticket</span>'
    bis = f'<span class="d">bis {E(x["bis"])}</span>' if x.get("bis") else ('<span class="d">' + E(x["st"]) + '</span>' if x.get("st") else '<span class="d"></span>')
    return f'<li class="nx"><span class="who {c}">{w}</span><span class="tx">{E(x["text"])}</span>{bis}{tk}</li>'
cards = ""
n_euch = sum(1 for xs in nx.values() for x in xs if x["wer"] == "euch")
n_uns = sum(1 for xs in nx.values() for x in xs if x["wer"] == "uns")
for t in TH:
    evs = [x for x in EV if x["thema"] == t["id"]]
    zul = "".join(f'<li><span>{E(_tag(x["datum"]))}</span><span><em class="src s-{x["typ"]}">{SRC[x["typ"]]}</em> {E(x["text"])}{_links(x)}</span></li>' for x in evs[:3])
    xs = sorted(nx[t["id"]], key=lambda x: (_wo[x["wer"]], x["bis"] == "", x["bis"][3:5] + x["bis"][:2] if x["bis"] else ""))
    nxt = "".join(_row_n(x) for x in xs) or '<li class="nx"><span class="tx mut2">Gerade nichts offen.</span></li>'
    last = f'<span class="zl">zuletzt {E(_tag(evs[0]["datum"]))}</span>' if evs else ""
    cards += (f'<div class="th"><div class="thh"><b>{E(t["titel"])}</b>{last}</div><p class="stand">{E(t["stand"])}</p>'
              + f'<div class="lbl">Als Nächstes</div><ul class="nxl">{nxt}</ul>'
              + (f'<details class="zud"><summary class="lbl">Zuletzt passiert <span class="zn">{min(len(evs), 3)}</span></summary><ul class="zu">{zul}</ul></details>' if zul else "") + '</div>')
# Termine: nächste Jour fixe + gesetzte Termine
_jf = KS["jour_fixe"]; _j0 = d(_jf["erster"])
_kom = []
_k = _j0
while len(_kom) < 3:
    if _k >= heute: _kom.append({"datum": _k.isoformat(), "wann": ("heute" if _k == heute else _k.strftime("%d.%m.")) + " · " + _jf["zeit"], "text": f'{_jf["titel"]} {(_k - _j0).days // 7 + 1}'})
    _k += dt.timedelta(days=7)
_kom += [x for x in KS["termine"] if not x["datum"] or d(x["datum"]) >= heute]
_kom = sorted(_kom, key=lambda x: (x["datum"] == "", x["datum"]))
term_html = '<div class="tm">' + "".join(f'<div class="tmi"><b>{E(x["wann"])}</b><span>{E(x["text"])}</span></div>' for x in _kom) + "</div>"
seit = d(KS["seit"]); n_seit = sum(1 for x in EV if d(x["datum"]) >= seit)
kpi = (f'<div class="kpi"><div class="k"><small>Bei euch offen</small><b>{n_euch}</b><span>Aufgaben und Abnahmen</span></div>'
       f'<div class="k"><small>Bei uns in Arbeit</small><b>{n_uns}</b><span>Tickets und Zusagen</span></div>'
       f'<div class="k"><small>Seit dem {E(seit.strftime("%d.%m."))}</small><b>{n_seit}</b><span>Termine, Mails, Tickets</span></div></div>')
# Verlauf
_flt = '<div class="flt" role="group" aria-label="Quelle">' + "".join(f'<button type="button" data-f="{k}" aria-pressed="{str(k == "alle").lower()}">{v}</button>' for k, v in [("alle", "Alle"), ("termin", "Termine"), ("mail", "Mails"), ("ticket", "Tickets")]) + "</div>"
_vl = ""; _grp = None
for x in EV:
    g = "Seit dem letzten Termin am " + seit.strftime("%d.%m.") if d(x["datum"]) >= seit else "Davor"
    if g != _grp: _vl += f'<li class="vg">{E(g)}</li>'; _grp = g
    _vl += f'<li data-typ="{x["typ"]}"><span>{E(_tag(x["datum"]))}</span><span><em class="src s-{x["typ"]}">{SRC[x["typ"]]}</em> {E(x["text"])}{_links(x)} <span class="tn">· {E(TNAME.get(x["thema"], ""))}</span></span></li>'
verlauf_html = f'<section class="sec"><h2>Verlauf</h2><p class="lsub">Alles, was passiert ist, neueste zuerst. Mails nennen wir mit Betreff, sie liegen in euren Postfächern.</p>{_flt}<ul class="seit vl">{_vl}</ul></section>'
_lg = {}
for x in (KS or {}).get("links", []): _lg.setdefault(x["gruppe"], []).append(x)
links_html = "".join(f'<section class="sec"><h2>{E(g)}</h2><ul class="lk">' + "".join(f'<li><a href="{E(x["link"])}" target="_blank" rel="noopener">{E(x["titel"])} ↗</a></li>' for x in xs) + "</ul></section>" for g, xs in _lg.items())
komp_html = (kpi + f'<section class="sec"><h2>Nächste Termine</h2>{term_html}</section>'
    f'<section class="sec"><h2>Wo steht was</h2><p class="lsub">Je Thema der Stand, was zuletzt passiert ist und wer als Nächstes dran ist.</p><div class="ths">{cards}</div></section>')
angebot_html = (f'<section class="sec"><h2>{E(_w["titel"])}</h2><p class="lsub">{E(_w["sub"])}</p><div class="flow">{flow}</div></section>'
    f'<section class="sec"><h2>Gemeinsam zu klären</h2><p class="lsub">Umfang der Ergebnisse, den wir mit euch festziehen.</p><div class="fq">{fr}</div></section>'
    f'<section class="sec"><h2>Termine und Lieferungen laut Angebot</h2><p class="lsub">Zum Abgleich mit euren Terminwünschen.</p><div class="mt">{mt}</div></section>'
    f'<section class="sec"><h2>Die neun Ergebnisse aus dem Angebot</h2><p class="lsub">So haben wir das Angebot in unserer Planung abgebildet.</p><div class="ep">{ep}</div></section>')
page = f'''<title>Projektstand synava medavis</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap">
<style>
/* Layout: Zeitstrahl als Kopf, dann zwei kurze Listen, dann Ergebnisse je Phase, Scope aufklappbar */
:root{{--bg:#f7f6f2;--fg:#1c1b18;--fg2:#5c5a52;--mut:#8a887f;--line:#e2dfd6;--card:#ffffff;--acc:#0f5c8c;--now:#c2410c;
--ph-plan:#e6e3da;--ph-aktiv:#cfe0ee;--ph-fertig:#d6ead9;--ph-fg:#2b2a26;
--of-bg:#ecebe6;--of-fg:#6b6961;--ar-bg:#e3eef7;--ar-fg:#0f4f7a;--wa-bg:#fbeedc;--wa-fg:#8a5410;--ab-bg:#ece6f7;--ab-fg:#4f3a8a;--fe-bg:#e2f1e4;--fe-fg:#1f6b33;
--font:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161614;--fg:#ecebe6;--fg2:#b9b7ae;--mut:#85837a;--line:#2b2b28;--card:#1f1f1c;--acc:#7fb6dc;--now:#f59e6b;
--ph-plan:#2a2a27;--ph-aktiv:#1e3a52;--ph-fertig:#1f3b25;--ph-fg:#ecebe6;
--of-bg:#2a2a27;--of-fg:#a19f96;--ar-bg:#1b3246;--ar-fg:#9cc7e8;--wa-bg:#3d2c14;--wa-fg:#f0b865;--ab-bg:#2d2544;--ab-fg:#bfaeea;--fe-bg:#1b3421;--fe-fg:#8fd29e;color-scheme:dark}}}}
:root[data-theme="dark"]{{--bg:#161614;--fg:#ecebe6;--fg2:#b9b7ae;--mut:#85837a;--line:#2b2b28;--card:#1f1f1c;--acc:#7fb6dc;--now:#f59e6b;
--ph-plan:#2a2a27;--ph-aktiv:#1e3a52;--ph-fertig:#1f3b25;--ph-fg:#ecebe6;
--of-bg:#2a2a27;--of-fg:#a19f96;--ar-bg:#1b3246;--ar-fg:#9cc7e8;--wa-bg:#3d2c14;--wa-fg:#f0b865;--ab-bg:#2d2544;--ab-fg:#bfaeea;--fe-bg:#1b3421;--fe-fg:#8fd29e;color-scheme:dark}}
body{{background:var(--bg);color:var(--fg);font-family:var(--font);font-size:15px;line-height:1.5;padding-block:32px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}}
main{{max-width:900px;margin:0 auto}}
h1{{font-size:24px;font-weight:600;margin:0 0 4px;letter-spacing:-.01em;text-wrap:balance}}
.sub{{color:var(--mut);font-size:13px;margin:0 0 20px}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:0 0 26px}}
.k{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;min-width:0}}
.k small{{display:block;color:var(--mut);font-size:12px;letter-spacing:.02em;text-transform:uppercase}}
.k b{{display:block;font-size:22px;font-weight:600;margin:2px 0}}.k span{{color:var(--fg2);font-size:13px}}
h2{{font-size:12px;font-weight:600;color:var(--mut);letter-spacing:.06em;text-transform:uppercase;margin:24px 0 6px}}
.tl{{position:relative;height:250px;margin:8px 0 10px;overflow:hidden}}
.mon{{position:absolute;left:0;right:0;top:0;height:18px;border-bottom:1px solid var(--line);font-size:11px;color:var(--mut)}}
.mon span{{position:absolute;top:0;padding-left:4px;border-left:1px solid var(--line);height:18px}}
.ph{{position:absolute;top:28px;height:26px;border-radius:6px;background:var(--ph-plan);color:var(--ph-fg);font-size:12px;line-height:26px;padding:0 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ph-aktiv{{background:var(--ph-aktiv)}}.ph-fertig{{background:var(--ph-fertig)}}
.ph:nth-child(n+4){{top:60px}}.ph:nth-child(n+5){{top:92px}}.ph:nth-child(n+6){{top:124px}}.ph:nth-child(n+7){{top:60px}}
.ms{{position:absolute;top:156px;transform:translateX(-50%);text-align:center;font-size:11px;color:var(--fg2);width:110px;line-height:1.25}}
.ms i{{display:block;width:10px;height:10px;margin:0 auto 4px;background:var(--acc);transform:rotate(45deg);border-radius:2px}}
.ms-done i{{background:var(--fe-fg)}}.ms-alt{{top:200px}}.ms-alt i{{margin-bottom:4px}}.ms b{{font-weight:500;color:var(--mut)}}
.now{{position:absolute;top:18px;bottom:96px;border-left:2px dashed var(--now)}}
.now span{{position:absolute;top:-2px;left:4px;font-size:11px;color:var(--now);font-weight:500}}
.r{{display:grid;grid-template-columns:minmax(0,1fr) 150px 56px;gap:12px;align-items:start;padding:9px 0;border-bottom:1px solid var(--line)}}
.r2{{grid-template-columns:minmax(0,1fr) 150px}}
.t{{min-width:0;font-size:14px}}.nr{{color:var(--mut);margin-right:8px;font-variant-numeric:tabular-nums}}
.hint{{color:var(--mut);font-size:12px;margin-top:2px}}
.c{{display:inline-block;font-size:12px;font-weight:500;padding:3px 10px;border-radius:999px;white-space:nowrap;justify-self:start}}
.c-offen{{background:var(--of-bg);color:var(--of-fg)}}.c-arbeit{{background:var(--ar-bg);color:var(--ar-fg)}}.c-wartet{{background:var(--wa-bg);color:var(--wa-fg)}}.c-abnahme{{background:var(--ab-bg);color:var(--ab-fg)}}.c-fertig{{background:var(--fe-bg);color:var(--fe-fg)}}
.d{{text-align:right;font-variant-numeric:tabular-nums;color:var(--fg2);font-size:14px}}
ul{{list-style:none;margin:0;padding:0}}li{{display:flex;gap:14px;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px}}
li span:first-child{{color:var(--mut);min-width:96px;font-size:13px;flex:none}}
.muted{{color:var(--mut)}}
details{{margin-top:18px;border-top:1px solid var(--line)}}summary{{cursor:pointer;padding:12px 0;font-size:14px;font-weight:500;color:var(--acc)}}
.foot{{color:var(--mut);font-size:12px;margin-top:28px}}
.flow{{display:flex;align-items:stretch;gap:0;margin-top:10px}}.flow .st{{flex:1;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}}.flow .st b{{display:block;font-size:15px;font-weight:600}}.flow .st span{{color:var(--fg2);font-size:13px}}.flow .st em{{display:inline-block;font-style:normal;font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-bottom:6px;color:var(--mut)}}
.flow .ar{{flex:none;width:28px;display:flex;align-items:center;justify-content:center;color:var(--mut);font-size:18px}}
.flow .st.f-done{{opacity:.75}}.flow .st.f-done em{{color:var(--fe-fg)}}.flow .st.f-now{{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}}.flow .st.f-now em{{color:var(--acc)}}.flow .st.f-goal{{background:var(--ar-bg)}}.flow .st.f-goal em{{color:var(--ar-fg)}}
@media (max-width:700px){{.flow{{flex-direction:column}}.flow .ar{{width:auto;height:22px;transform:rotate(90deg)}}}}
.sec{{margin-top:28px}}.sec h2{{font-size:13px;margin:0 0 4px}}.sec .lsub{{margin-bottom:10px}}
.fq{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}.fq div{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}.fq b{{display:block;font-size:15px;font-weight:600;margin-bottom:6px}}.fq ul li{{border:0;padding:4px 0;font-size:14px;color:var(--fg2)}}.fq ul li{{align-items:flex-start;gap:10px}}.fq ul li:before{{content:"";flex:none;width:6px;height:6px;border-radius:50%;background:var(--acc);margin-top:8px}}
.mt{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}.mt .row{{display:grid;grid-template-columns:1.1fr .8fr 1.8fr 1.2fr;gap:14px;padding:11px 16px;border-top:1px solid var(--line);font-size:14px}}.mt .row:first-child{{border-top:0;font-size:11px;font-weight:600;color:var(--mut);letter-spacing:.05em;text-transform:uppercase}}.mt .row b{{font-weight:600}}.mt .w{{color:var(--acc)}}
.ep{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}.ep .row{{display:grid;grid-template-columns:28px minmax(0,1fr) 140px;gap:12px;align-items:center;padding:10px 16px;border-top:1px solid var(--line)}}.ep .row:first-child{{border-top:0}}.ep .gh{{background:var(--bg);font-size:12px;font-weight:600;color:var(--acc);padding:8px 16px}}.ep .n{{color:var(--mut);font-variant-numeric:tabular-nums}}.ep .t b{{display:block;font-size:15px;font-weight:600}}.ep .t span{{color:var(--mut);font-size:13px}}
@media (max-width:700px){{.mt .row{{grid-template-columns:1fr}}.mt .row:first-child{{display:none}}.ep .row{{grid-template-columns:24px 1fr}}.ep .row .c{{grid-column:2}}}}
.li3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:8px}}.li3 div{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}.li3 b{{display:block;font-size:15px;font-weight:600;margin-bottom:4px}}.li3 span{{color:var(--fg2);font-size:14px}}
.tabs{{display:flex;gap:6px;margin:4px 0 4px}}.tabs button{{font:inherit;font-size:14px;padding:6px 14px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}}.tabs button[aria-selected="true"]{{background:var(--acc);border-color:var(--acc);color:var(--bg)}}
.offen{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}.orow{{display:grid;grid-template-columns:84px minmax(0,1fr) 64px 70px;gap:12px;align-items:center;padding:9px 16px;border-top:1px solid var(--line);font-size:14px}}.orow:first-child{{border-top:0}}.oh{{font-size:11px;font-weight:600;color:var(--mut);letter-spacing:.05em;text-transform:uppercase}}.orow a{{color:var(--acc);font-size:13px;white-space:nowrap}}
.o3{{grid-template-columns:minmax(0,1fr) 64px 70px}}
.straenge{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}.strang{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;display:flex;flex-direction:column;gap:6px}}.strang .sh{{display:flex;gap:8px;align-items:baseline}}.strang .sh .n{{color:var(--mut);font-variant-numeric:tabular-nums}}.strang .sh b{{font-weight:600}}.strang .neu2{{margin:0;font-size:13px;color:var(--fg2)}}.strang ul li{{justify-content:space-between;align-items:center;font-size:14px;padding:5px 0}}.strang ul li:last-child{{border-bottom:0}}.strang ul li a{{color:var(--acc)}}.strang ul li span:first-child{{min-width:0}}
.who{{font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;justify-self:start}}.w-syn{{background:var(--wa-bg);color:var(--wa-fg)}}.w-360{{background:var(--ar-bg);color:var(--ar-fg)}}
.seit .mail{{color:var(--mut);font-size:13px}}.ep .t b a{{color:inherit;text-decoration:none}}.ep .t b a:hover{{color:var(--acc);text-decoration:underline}}
.lk{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:2px 16px}}.lk li:last-child{{border-bottom:0}}.lk a{{color:var(--acc)}}
@media (max-width:640px){{.orow{{grid-template-columns:76px minmax(0,1fr)}}.orow .d,.orow a{{grid-column:2}}.oh{{display:none}}}}
.seit{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 16px}}.seit li:last-child{{border-bottom:0}}.seit li span:first-child{{min-width:52px}}.seit a{{color:var(--acc);white-space:nowrap}}
.ep .t em.neu{{display:block;font-style:normal;font-size:13px;color:var(--acc);margin-top:2px}}
.lsub{{color:var(--fg2);font-size:14px;margin:0 0 4px}}.bl{{font-size:13px;font-weight:600;color:var(--acc);margin:18px 0 8px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
.cd{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;gap:8px}}
.cd .top{{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}}.cd h3{{margin:0;font-size:16px;font-weight:600}}.cd h3 i{{font-style:normal;color:var(--mut);margin-right:8px;font-variant-numeric:tabular-nums}}
.cd .lst{{color:var(--mut);font-size:13px}}.cd .sk{{font-size:14px;color:var(--fg2)}}.cd .kl{{font-size:14px;border-left:3px solid var(--acc);padding:2px 0 2px 10px}}.cd .kl small{{display:block;color:var(--acc);font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase}}
.cd .meta{{display:flex;gap:8px;align-items:center;flex:none}}.cd .meta .d{{font-size:13px}}
.ag{{border:1px solid var(--line);border-radius:10px;padding:2px 16px;margin-top:8px}}.ag li:last-child{{border-bottom:0}}.ag li span:first-child{{min-width:20px;font-weight:600;color:var(--acc)}}.ag b{{font-weight:600}}
@media (max-width:640px){{.r{{grid-template-columns:1fr auto}}.d{{grid-column:1/-1;text-align:left}}.ms{{width:80px}}.tl{{height:290px}}.ms-alt{{top:220px}}}}
.ths{{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:12px}}.th{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:6px;min-width:0}}
.thh{{display:flex;justify-content:space-between;gap:10px;align-items:baseline}}.thh b{{font-size:16px;font-weight:600}}.zl{{color:var(--mut);font-size:12px;white-space:nowrap}}
.th .stand{{margin:0;font-size:14px;color:var(--fg2)}}.lbl{{font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--mut);margin-top:6px}}
.zud{{border-top:1px solid var(--line);margin-top:6px;padding-top:4px}}.zud summary{{cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;user-select:none}}.zud summary::-webkit-details-marker{{display:none}}
.zud summary::before{{content:"▸";font-size:11px;transition:transform .15s}}.zud[open] summary::before{{transform:rotate(90deg)}}.zud summary:hover{{color:var(--fg2)}}.zn{{font-weight:500;letter-spacing:0;opacity:.8}}
.th ul li{{padding:5px 0;font-size:13px}}.th ul li:last-child{{border-bottom:0}}.th .zu li span:first-child{{min-width:42px}}.th a{{color:var(--acc);white-space:nowrap}}
.nx .who{{min-width:0!important;text-align:center}}.nx{{display:grid!important;grid-template-columns:84px minmax(0,1fr) auto auto;gap:10px!important;align-items:center}}.nx .tx{{min-width:0;color:var(--fg)!important;font-size:13px!important}}.nx .d{{font-size:12px;white-space:nowrap}}
.w-gem{{background:var(--ab-bg);color:var(--ab-fg)}}.mut2{{color:var(--mut);font-size:12px}}
.src{{display:inline-block;font-style:normal;font-size:11px;font-weight:600;padding:1px 7px;border-radius:999px;border:1px solid var(--line);color:var(--fg2);margin-right:4px}}.s-termin{{border-color:var(--ab-fg);color:var(--ab-fg)}}.s-mail{{border-color:var(--wa-fg);color:var(--wa-fg)}}.s-ticket{{border-color:var(--ar-fg);color:var(--ar-fg)}}
.tm{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}}.tmi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px}}.tmi b{{display:block;font-size:14px;font-weight:600}}.tmi span{{color:var(--fg2);font-size:13px}}
.flt{{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px}}.flt button{{font:inherit;font-size:13px;padding:4px 12px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}}.flt button[aria-pressed="true"]{{border-color:var(--acc);color:var(--acc)}}
.vl .vg{{font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--acc);padding-top:14px}}.vl .tn{{color:var(--mut);font-size:12px}}
@media (max-width:640px){{.ths{{grid-template-columns:1fr}}.nx{{grid-template-columns:64px minmax(0,1fr)}}.nx .d,.nx a,.nx .mut2{{grid-column:2}}}}
</style>
<main>
<h1>{E(R["titel"])}</h1>
<p class="sub">{E(R["untertitel"])} · Stand {stand}</p>
<p class="lsub" style="margin-top:-12px">{E(R["kompakt"]["hinweis"])}</p>
<nav class="tabs" role="tablist"><button type="button" role="tab" data-tab="stand" aria-selected="true">Überblick</button><button type="button" role="tab" data-tab="verlauf" aria-selected="false">Verlauf</button><button type="button" role="tab" data-tab="angebot" aria-selected="false">Angebot</button><button type="button" role="tab" data-tab="links" aria-selected="false">Links</button></nav>
<div data-panel="stand">{komp_html}</div>
<div data-panel="verlauf" hidden>{verlauf_html}</div>
<div data-panel="angebot" hidden>{angebot_html}</div>
<div data-panel="links" hidden>{links_html}</div>
<p class="foot">Ansprechpartner: Kevin Owusu, 360VIER.</p>
</main>
<script>
(function(){{var b=document.querySelectorAll('[data-tab]'),p=document.querySelectorAll('[data-panel]');
function zeig(k){{b.forEach(function(x){{x.setAttribute('aria-selected',String(x.dataset.tab===k))}});p.forEach(function(x){{x.hidden=x.dataset.panel!==k}})}}
b.forEach(function(x){{x.addEventListener('click',function(){{zeig(x.dataset.tab);try{{history.replaceState(null,'','#'+x.dataset.tab)}}catch(e){{}}}})}});
var h=location.hash.slice(1);if(['verlauf','angebot','links'].indexOf(h)>-1)zeig(h);
document.querySelectorAll('[data-f]').forEach(function(f){{f.addEventListener('click',function(){{var k=f.dataset.f;document.querySelectorAll('[data-f]').forEach(function(y){{y.setAttribute('aria-pressed',String(y===f))}});document.querySelectorAll('.vl li[data-typ]').forEach(function(li){{li.hidden=k!=='alle'&&li.dataset.typ!==k}})}})}});}})();
</script>'''
_txt = _re.sub(r"<[^>]+>", " ", page.split("<main>", 1)[1])
# Vornamen von Personen stehen nur als SHA-256-Prüfsumme (klein geschrieben) in regeln.json, weil das Repo öffentlich ist.
import hashlib as _hl
_schutz = set(R.get("schutz_hashes", []))
_verboten = sorted({w for w in _re.findall(r"\w+", _txt) if _hl.sha256(w.lower().encode()).hexdigest() in _schutz})
_verboten += [m for m in _re.findall(r"\d+(?:,\d+)?\s*(?:h\b|Std|Stunden|€|EUR|Euro|%|Prozent|PT\b)", _txt)]
if _verboten:
    raise SystemExit("SCHUTZ: nicht geschrieben, Kundenseite enthält " + ", ".join(sorted(set(_verboten))))
(HERE / "kundensicht.html").write_text(page)  # Artefakt-Fassung (ohne Dokumentgerüst)
_kopf = ('<!doctype html>\n<html lang="de"><head><meta charset="utf-8"><meta name="viewport" '
         'content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">\n')
(HERE / "index.html").write_text(_kopf + page[page.index("<title>"):] + "\n</html>\n")  # öffentliche Seite (GitHub Pages)
print(f"ok: {len(epics)} Epics, {n_aktiv} aktiv, {len(dl)} bestätigte Entscheidungen, Stand {stand}")
