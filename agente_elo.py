"""Agente ELO Rating
Legge i risultati dai database Notion degli agenti (badminton, judo, lotta, scherma, squash,
tennistavolo, vela), scarica le classifiche ELO del tennis da Tennis Abstract, calcola i dati
e rigenera index.html (l'app ELO Rating) a partire da template.html.

Uso:  python agente_elo.py           -> aggiornamento completo (serve NOTION_TOKEN)
      python agente_elo.py --prova   -> legge Notion ma NON scrive index.html
"""
import datetime, html.parser, json, os, re, sys, time, urllib.request, urllib.error

try:
    from zoneinfo import ZoneInfo
    ROMA = ZoneInfo("Europe/Rome")
except Exception:  # pragma: no cover
    ROMA = None

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
NOTION_VERSION = "2022-06-28"
PROVA = "--prova" in sys.argv

# ID dei database Notion (dalla pagina "⚙️ Agenti")
DB = {
    "badminton":    "4b3d72bd6b48466395954d0f6ca06308",
    "judo":         "410f48c9aad9807dbf98dbe62d1098ff",
    "wrestling":    "40ef48c9aad980cd99cddb408b9511c1",
    "scherma":      "bad38844495d474ea78c1ae2e8ef8c87",
    "squash":       "40ef48c9aad980dba869dddc0c5ed879",
    "tennistavolo": "41df48c9aad9819f90e9fed635bcf84a",
    "vela":         "41bf48c9aad98176aeb3d4c671fd9089",
}

# ---------------------------------------------------------------- Notion

def notion_query(db_id):
    """Tutte le righe di un database Notion (100 per volta)."""
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    rows, cursor, tentativi = [], None, 0
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and tentativi < 6:
                tentativi += 1
                time.sleep(2 * tentativi)
                continue
            msg = e.read().decode(errors="replace")[:300]
            raise SystemExit(f"Errore Notion {e.code} sul database {db_id}: {msg}\n"
                             "Controlla che la connessione 'Agente ELO' sia collegata alla pagina Agenti.")
        tentativi = 0
        rows += data.get("results", [])
        if not data.get("has_more"):
            return rows
        cursor = data.get("next_cursor")
        time.sleep(0.35)  # Notion: massimo ~3 richieste al secondo


def val(page, name):
    """Valore di una proprietà come testo."""
    p = page.get("properties", {}).get(name)
    if not p:
        return ""
    t = p.get("type")
    v = p.get(t)
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v or [])
    if t in ("select", "status"):
        return (v or {}).get("name", "")
    if t == "multi_select":
        return ", ".join(x.get("name", "") for x in v or [])
    if t == "number":
        if v is None:
            return ""
        return str(int(v)) if float(v).is_integer() else str(v)
    if t == "date":
        return ((v or {}).get("start") or "")[:10]
    if t in ("url", "email", "phone_number"):
        return v or ""
    if t == "formula":
        f = v or {}
        x = f.get(f.get("type"))
        return "" if x is None else str(x)
    return ""


def righe_incontri(sport, pages):
    """Converte le pagine Notion nei 14 campi usati dal calcolo:
    data, torneo, livello, gender, gruppo, turno, vincitore, p1, noc1, id1, p2, noc2, id2, score"""
    out = []
    for pg in pages:
        g = lambda n: val(pg, n)
        if sport == "judo":
            r = [g("Data"), g("Torneo"), g("Tipo Torneo"), g("Gender"), g("Categoria"), g("Turno"), g("Winner"),
                 g("Player 1"), g("NOC 1"), g("ID IJF 1"), g("Player 2"), g("NOC 2"), g("ID IJF 2"), g("Score")]
        elif sport == "badminton":
            r = [g("Data"), g("Torneo"), g("Categoria"), g("Gender"), g("Disciplina"), g("Turno"), "",
                 g("Player 1"), g("NOC 1"), g("ID BWF 1"), g("Player 2"), g("NOC 2"), g("ID BWF 2"), g("Score")]
        elif sport == "scherma":
            if g("Gara") != "Individuale":
                continue
            r = [g("Data"), g("Torneo"), g("Livello"), g("Gender"), g("Arma"), g("Turno"), "",
                 g("Player 1"), g("NOC 1"), g("ID FIE 1"), g("Player 2"), g("NOC 2"), g("ID FIE 2"), g("Score")]
        elif sport == "wrestling":
            r = [g("Data"), g("Torneo"), g("Tipo Torneo"), g("Gender"), f'{g("Stile")} {g("Categoria")}', g("Turno"),
                 g("Vincitore"), g("Player 1"), g("NOC 1"), g("ID UWW 1"), g("Player 2"), g("NOC 2"), g("ID UWW 2"),
                 g("Score")]
        elif sport == "tennistavolo":  # il vincitore è sempre Player 1
            r = [g("Data"), g("Torneo"), g("Categoria"), g("Gender"), g("Disciplina"), g("Turno"), g("Player 1"),
                 g("Player 1"), g("NOC 1"), g("ID ITTF 1"), g("Player 2"), g("NOC 2"), g("ID ITTF 2"), g("Score")]
        elif sport == "squash":
            r = [g("Data"), g("Torneo"), "", g("Gender"), g("Gender"), g("Turno"), "",
                 g("Player 1"), g("NOC 1"), "", g("Player 2"), g("NOC 2"), "", g("Score")]
        elif sport == "vela":
            r = [g("Data fine") or g("Data inizio"), g("Evento"), g("Tipo Evento"), g("Classe"), g("Barca"),
                 g("Timoniere"), g("Prodiere"), g("NOC"), g("ID WS 1"), g("ID WS 2"), g("Posizione"),
                 g("Barche in classifica"), g("Punti netti"), g("Note")]
        else:
            continue
        out.append(r)
    return out

# ---------------------------------------------------------------- calcolo dati

ROUND_ORDER = {
    "Round 1": 1, "Round of 128": 1, "Round of 64": 2, "Round of 32": 3, "Round of 16": 4,
    "Quarter Final": 5, "Quarter-Final": 5, "Repechage": 6, "Semi Final": 7, "Semi-Final": 7,
    "Bronze": 8, "Final": 9, "Group Stage": 1, "Qualifying Group": 0, "Qualifying Round 1": 0,
    "Qualifying Round 2": 0, "Qualifying Round 3": 0, "Qualifying Round 4": 0, "Qualification Elimination Round": 0,
    "Preliminare da 256": 0, "Preliminare da 128": 1, "Preliminare da 64": 1, "Tabellone da 128": 2,
    "Tabellone da 64": 2, "Tabellone da 32": 3, "Tabellone da 16": 4, "Quarti di finale": 5, "Semifinale": 7,
    "Finale 3° posto": 8, "Finale": 9, "Qualif.": 1, "A | Round 1": 1, "B | Round 1": 1, "A | Round 2": 2,
    "B | Round 2": 2, "A | Round 3": 3, "B | Round 3": 3, "Round 2": 2, "Round 3": 3, "Round 4": 4, "Round 5": 5,
    "1/16 Final": 2, "1/8 Final": 3, "1/4 Final": 5, "1/2 Final": 7, "Final 3-5": 8, "Final 3-4": 8, "Final 1-2": 9,
}
SCORE_PAIR = re.compile(r"(\d+)\s*-\s*(\d+)")
WALKOVER = re.compile(r"\b(w/?o|walkover|walk over|forfeit|fusen|kiken|non present|dns|vfo)\b", re.I)


def winner_side(f):
    w, p1, p2, score = f[6].strip(), f[7].strip(), f[10].strip(), f[13].strip()
    if WALKOVER.search(score):
        return None
    if w:
        if w == p1:
            return 1
        if w == p2:
            return 2
    m = SCORE_PAIR.search(score)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            return 1
        if b > a:
            return 2
    return None


def pool_label(sport, f):
    gender, pool = f[3].strip(), f[4].strip()
    if sport == "scherma":
        return f"{pool} {'M' if gender == 'Men' else 'F'}"
    if sport == "judo":
        return f"{'M' if gender == 'Men' else 'F'} {pool}"
    if sport == "squash":
        return "Maschile" if gender == "Men" else "Femminile"
    return pool


def entity_key(name, id_):
    id_ = id_.strip()
    if id_:
        return "id:" + "/".join(sorted(p.strip() for p in id_.split("/") if p.strip()))
    return "nm:" + name.strip().upper()


def build_incontri(sport, rows):
    pools, tourns, rounds, ents = {}, {}, {}, {}
    pool_l, tourn_l, round_l, ent_list, matches, seen, skipped = [], [], [], [], [], set(), 0

    def idx(d, k, lst):
        if k not in d:
            d[k] = len(d)
            lst.append(k)
        return d[k]

    for f in rows:
        if len(f) != 14 or not f[0]:
            skipped += 1
            continue
        side = winner_side(f)
        if side is None:
            skipped += 1
            continue
        dedup = (f[0], f[1], f[4], f[5], f[9], f[12], f[7], f[10])
        if dedup in seen:
            skipped += 1
            continue
        seen.add(dedup)
        k1, k2 = entity_key(f[7], f[9]), entity_key(f[10], f[12])
        if k1 == k2:
            skipped += 1
            continue
        for k, nm, noc in ((k1, f[7], f[8]), (k2, f[10], f[11])):
            if k not in ents:
                ents[k] = len(ent_list)
                ent_list.append([nm.strip(), noc.strip()])
            else:
                old = ent_list[ents[k]]
                ent_list[ents[k]] = [nm.strip() or old[0], noc.strip() or old[1]]
        w, l = (ents[k1], ents[k2]) if side == 1 else (ents[k2], ents[k1])
        lvl = f[2].strip()
        if sport == "squash":
            n = f[1].lower()
            lvl = "Mondiali" if "world championships" in n else "Tour Finals" if "tour finals" in n else "PSA World Tour"
        p = idx(pools, pool_label(sport, f), pool_l)
        t = idx(tourns, (f[1].strip(), lvl), tourn_l)
        r = idx(rounds, f[5].strip(), round_l)
        matches.append([f[0][:10], p, t, r, w, l, f[13].strip()])
    rr = [ROUND_ORDER.get(x, 5) for x in round_l]
    matches.sort(key=lambda m: (m[0], rr[m[3]]))
    print(f"  {sport}: {len(matches)} incontri, {len(ent_list)} atleti, scartati {skipped}")
    return {"pools": pool_l, "tournaments": [list(t) for t in tourn_l], "rounds": round_l,
            "athletes": ent_list, "matches": matches, "skipped": skipped}


def build_vela(rows):
    pools, tourns, ents, ent_list, pool_l, tourn_l, events, skipped = {}, {}, {}, [], [], [], {}, 0
    for f in rows:
        if len(f) != 14 or not f[0] or not f[10] or "mai partita" in f[13].lower():
            skipped += 1
            continue
        name = " ".join(f[4].split()) or " / ".join(x for x in (f[5].strip(), f[6].strip()) if x)
        k = name.upper()
        if k not in ents:
            ents[k] = len(ent_list)
            ent_list.append([name, f[7].strip()])
        else:
            ent_list[ents[k]][1] = f[7].strip() or ent_list[ents[k]][1]
        if f[3] not in pools:
            pools[f[3]] = len(pool_l)
            pool_l.append(f[3])
        tk = (f[1].strip(), f[2].strip())
        if tk not in tourns:
            tourns[tk] = len(tourn_l)
            tourn_l.append(list(tk))
        ev = events.setdefault((f[0][:10], pools[f[3]], tourns[tk]), {})
        if ents[k] in ev:
            skipped += 1
            continue
        ev[ents[k]] = int(float(f[10]))
    evl = [[d, p, t, sorted(([a, pos] for a, pos in res.items()), key=lambda x: x[1])]
           for (d, p, t), res in sorted(events.items()) if len(res) >= 2]
    print(f"  vela: {len(evl)} regate, {len(ent_list)} barche, scartati {skipped}")
    return {"pools": pool_l, "tournaments": tourn_l, "rounds": [], "athletes": ent_list,
            "matches": [], "events": evl, "skipped": skipped}

# ---------------------------------------------------------------- tennis (Tennis Abstract)

ITA_TENNIS = {"Jannik Sinner", "Lorenzo Musetti", "Flavio Cobolli", "Matteo Berrettini", "Luciano Darderi",
              "Matteo Arnaldi", "Mattia Bellucci", "Francesco Passaro", "Lorenzo Sonego", "Andrea Vavassori",
              "Federico Cina", "Andrea Guerrieri", "Luca Nardi", "Jasmine Paolini", "Elisabetta Cocciaretto",
              "Lucrezia Stefanini", "Lisa Pigato", "Lucia Bronzetti"}
TOP_TENNIS = 200


class TableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.in_cell = [], None, "", False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.in_cell, self.cell = True, ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.row is not None and self.in_cell:
            self.row.append(" ".join(self.cell.split()))
            self.in_cell = False
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.in_cell:
            self.cell += data


def parse_tennis_abstract(page):
    """Estrae la tabella ELO dalla pagina HTML di Tennis Abstract. Restituisce (data, righe csv)."""
    p = TableParser()
    p.feed(page)
    head = next((r for r in p.rows if any(c.lower() == "player" for c in r) and any(c.lower() == "elo" for c in r)), None)
    if not head:
        raise ValueError("tabella non trovata")
    low = [c.lower() for c in head]
    col = lambda *names: next((low.index(n) for n in names if n in low), None)
    i_rank, i_pl, i_age, i_elo = col("elo rank", "rank"), col("player"), col("age"), col("elo")
    i_h, i_c, i_g = col("helo"), col("celo"), col("gelo")
    i_pk, i_pm, i_tr = col("peak elo"), col("peak month"), col("atp rank", "wta rank")
    out = []
    for r in p.rows:
        if r is head or len(r) < len(head) or not r[i_rank].isdigit():
            continue
        g = lambda i: r[i] if i is not None and i < len(r) else ""
        out.append(";".join([g(i_rank), g(i_pl), g(i_age), g(i_elo), g(i_h), g(i_c), g(i_g), g(i_pk), g(i_pm), g(i_tr)]))
        if len(out) >= TOP_TENNIS:
            break
    if len(out) < 50:
        raise ValueError(f"solo {len(out)} righe lette")
    m = re.search(r"(20\d\d-\d\d-\d\d)", page)
    return (m.group(1) if m else datetime.date.today().isoformat()), out


def aggiorna_tennis():
    for tour in ("atp", "wta"):
        fn = f"tennis_{tour}.csv"
        try:
            req = urllib.request.Request(f"https://tennisabstract.com/reports/{tour}_elo_ratings.html",
                                         headers={"User-Agent": "Mozilla/5.0 (agente-elo)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                page = r.read().decode("utf-8", errors="replace")
            data, rows = parse_tennis_abstract(page)
            with open(fn, "w", encoding="utf-8") as f:
                f.write(f"#{data}\n" + "\n".join(rows) + "\n")
            print(f"  tennis {tour.upper()}: {len(rows)} giocatori (aggiornato {data})")
        except Exception as e:  # tengo il file precedente
            print(f"  tennis {tour.upper()}: download non riuscito ({e}); uso i dati salvati")


def build_tennis():
    pools, athletes, players, updated = ["ATP", "WTA"], [], [], {}
    num = lambda x: float(x) if x else None
    for p, tour in enumerate(("atp", "wta")):
        fn = f"tennis_{tour}.csv"
        if not os.path.exists(fn):
            continue
        for line in open(fn, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                updated[pools[p]] = line[1:]
                continue
            f = line.split(";")
            if len(f) < 10:
                continue
            athletes.append([f[1], "ITA" if f[1] in ITA_TENNIS else ""])
            players.append([p, int(f[0]), len(athletes) - 1, num(f[2]), num(f[3]), num(f[4]), num(f[5]), num(f[6]),
                            num(f[7]), f[8], int(f[9]) if f[9].isdigit() else None])
    return {"pools": pools, "tournaments": [], "rounds": [], "athletes": athletes, "matches": [],
            "players": players, "updated": updated, "skipped": 0}

# ---------------------------------------------------------------- main

def main():
    if not NOTION_TOKEN:
        raise SystemExit("Manca NOTION_TOKEN (va inserito nei Secrets del repository).")
    ora = datetime.datetime.now(ROMA) if ROMA else datetime.datetime.now()
    out = {"generated": ora.strftime("%Y-%m-%d %H:%M"), "sports": {}}
    print("Lettura Notion…")
    for sport, db in DB.items():
        pages = notion_query(db)
        print(f"  {sport}: {len(pages)} righe lette")
        rows = righe_incontri(sport, pages)
        out["sports"][sport] = build_vela(rows) if sport == "vela" else build_incontri(sport, rows)
    print("Tennis Abstract…")
    aggiorna_tennis()
    out["sports"]["tennis"] = build_tennis()
    if PROVA:
        print("Modalità prova: index.html NON modificato.")
        return
    data = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    tpl = open("template.html", encoding="utf-8").read()
    if "__DATA__" not in tpl:
        raise SystemExit("template.html non contiene __DATA__")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(tpl.replace("__DATA__", data))
    print(f"index.html aggiornato ({os.path.getsize('index.html') // 1024} KB)")


if __name__ == "__main__":
    main()
