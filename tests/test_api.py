"""Tests de l'API (bibliothèque standard uniquement).

Lancé par tests/lancer_tests.sh, qui démarre un serveur sur une base temporaire avec les
données de démonstration (--demo) et définit BASE, TEST_TMP, BDD_PUBS_DATA, BDD_PUBS_SAUVEGARDES.
"""
import base64
import http.client
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:8799")
TMP = os.environ["TEST_TMP"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECHECS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        ECHECS.append(msg)


def call(method, path, body=None, projet=None, raw=None, ctype="application/json", base=BASE):
    headers = {"Content-Type": ctype}
    if projet:
        headers["X-Projet"] = projet
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            content = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        content, status = e.read(), e.code
    try:
        return status, json.loads(content.decode("utf-8"))
    except ValueError:
        return status, content


def get(path, projet=None):
    return call("GET", path, projet=projet)[1]


def counts(projet=None):
    return get("/api/dashboard", projet)["counts"]


def section(t):
    print(t)


# ---------------------------------------------------------------------------
section("Données de démonstration")
c = counts()
check((c["games"], c["ads"], c["appearances"], c["issues"]) == (4, 5, 8, 6),
      f"démo : 4 jeux, 5 pubs, 8 parutions, 6 numéros (obtenu {c['games']}, {c['ads']}, {c['appearances']}, {c['issues']})")
check(c["images"] == 5, "une affiche de démo par pub")
plat = {p["name"]: p["id"] for p in get("/api/platforms")}
mags = {m["name"]: m["id"] for m in get("/api/magazines")}

section("Recherche croisée")
r = get(f"/api/search?jeu=final&magazine_id={mags['Weekly Famitsu']}")
check(r["stats"]["total"] == 3, "Final Fantasy dans Famitsu : 3 parutions")
check(get("/api/search?annee=1996")["stats"]["total"] == 1, "année 1996 : 1 parution")
check(get(f"/api/search?platform_id={plat['Sega Saturn']}")["stats"]["total"] == 2, "plateforme Saturn : 2 parutions")
check(get("/api/search?vente=1")["stats"]["total"] == 4, "en vente : 4")

section("Règles de saisie")
s, r = call("POST", "/api/issues", {"magazine_id": mags["Weekly Famitsu"], "number": "1", "date": "97/01"})
check(s == 400, "date mal formée refusée")
s, r = call("POST", "/api/magazines", {"name": "weekly famitsu"})
check(s == 409, "magazine en double refusé (sans tenir compte des majuscules)")
s, r = call("DELETE", "/api/games/1")
check(s == 409 and "pub" in r.get("error", ""), "suppression d'un jeu qui a des pubs refusée, message clair")

section("Parution dans un nouveau numéro + plusieurs plateformes")
s, ap = call("POST", "/api/appearances", {"magazine_id": mags["Dengeki PlayStation"], "issue_number": "77",
                                          "issue_date": "1998-05", "ad_id": 3, "page": "12", "for_sale": "1"})
check(s == 201 and ap["number"] == "77" and ap["date"] == "1998-05", "numéro créé à la volée avec sa date")
s, ad = call("PUT", "/api/ads/3", {"platform_ids": [plat["PlayStation"], plat["Sega Saturn"]]})
check(sorted(ad["platform_ids"]) == sorted([plat["PlayStation"], plat["Sega Saturn"]]), "pub avec 2 plateformes")
check(get(f"/api/search?platform_id={plat['Sega Saturn']}")["stats"]["total"] == 2 + 2,
      "recherche Saturn inclut la pub multi-plateformes")

section("Dates de parution en texte libre")
sys.path.insert(0, os.path.join(ROOT, "appli"))
import app as APP  # noqa: E402  (fonctions pures seulement : l'analyseur de dates)
FORMES = {
    "1997-04-08": ("1997-04-08", ""), "1997": ("1997", ""),
    "8 et 15 avril 1997": ("1997-04-08", "8 et 15 avril 1997"),
    "juillet-août 1996": ("1996-07", "juillet-août 1996"),
    "Juillet/Août 1996": ("1996-07", "Juillet/Août 1996"),
    "31 décembre 1996 - 7 janvier 1997": ("1996-12-31", None),
    "décembre 1996 / janvier 1997": ("1996-12", None),
    "08/04/1997": ("1997-04-08", None), "4/1997": ("1997-04", None), "1997/04/08": ("1997-04-08", None),
    "1997年4月8・15日号": ("1997-04-08", None), "1996年7・8月合併号": ("1996-07", None),
    "1997年4月号": ("1997-04", None), "１９９７年４月": ("1997-04", None),
    "1er mai 1998": ("1998-05-01", None), "avril 97": ("1997-04", None),
    "April 8-15, 1997": ("1997-04-08", None), "hiver 1996": ("1996", None),
    "n° spécial été 1998": ("1998", None), "  8  et 15 avril 1997 ": ("1997-04-08", "8 et 15 avril 1997"),
}
for txt, (iso, label) in FORMES.items():
    got = APP.parse_issue_date(txt)
    check(got[0] == iso and (label is None or got[1] == label), f"« {txt} » → {iso} (obtenu {got})")
for txt in ("12 avril", "bientôt", "97/01"):
    try:
        APP.parse_issue_date(txt)
        check(False, f"« {txt} » refusé (pas d'année)")
    except ValueError:
        check(True, f"« {txt} » refusé (pas d'année)")
s, iss = call("POST", "/api/issues", {"magazine_id": mags["Weekly Famitsu"], "number": "431", "date": "8 et 15 avril 1997"})
check(s == 201 and iss["date"] == "1997-04-08" and iss["date_label"] == "8 et 15 avril 1997",
      "numéro enregistré avec le texte de la date et une date triable")
s, iss = call("PUT", f"/api/issues/{iss['id']}", {"date": "1997-04-08"})
check(iss["date_label"] == "", "date ISO : plus de libellé")
with urllib.request.urlopen(BASE + "/api/export/apparitions.csv") as r_:
    check("7 et 14 mars 1997" in r_.read().decode("utf-8"), "export CSV : date telle qu'écrite")

section("Statistiques et compteur de pages")
st = get("/api/stats?par=genre")
g = {x["label"]: x for x in st["groups"]}
check(g["RPG"]["n"] == 5 and g["RPG"]["games"] == 2, f"par type de jeu : RPG = 5 parutions, 2 jeux ({g.get('RPG')})")
check(st["total"]["total"] == 9 and st["total"]["pages"] == sum(x["pages"] for x in st["groups"]), "totaux cohérents")
st = get(f"/api/stats?par=editeur&magazine_id={mags['Weekly Famitsu']}")
check({x["label"]: x["n"] for x in st["groups"]} == {"Square": 3, "Sega": 1, "Enix": 1}, "par éditeur, filtré sur un magazine")
st = get("/api/stats?par=annee")
check([x["key"] for x in st["groups"]] == ["1996", "1997", "1998", ""], f"par année de parution, triée ({[x['key'] for x in st['groups']]})")
check(get("/api/stats?par=plateforme")["groups"][0]["label"] == "PlayStation", "par plateforme")
s, _ = call("GET", "/api/stats?par=nimporte")
check(s == 400, "regroupement inconnu refusé")
m = get(f"/api/magazines/{mags['Weekly Famitsu']}")
check(m["ad_pages"] == 2 + 1 + 2 + 1 + 2 and m["avg_ad_pages"] == round(8 / 4, 1),
      f"pages de pub du magazine et moyenne par numéro ({m['ad_pages']}, {m['avg_ad_pages']})")
i421 = [i for i in m["issues"] if i["number"] == "421"][0]
check(i421["ad_pages"] == 3, "pages de pub d'un numéro")
check(get(f"/api/search?genre=RPG&publisher=Square")["stats"]["total"] == 4, "recherche par type de jeu + éditeur")
meta = get("/api/meta")
check("RPG" in meta["genres"] and "Square" in meta["publishers"], "valeurs proposées (genres, éditeurs)")

section("Catalogue des magazines (possédés / manquants)")
ssm = get(f"/api/magazines/{mags['Sega Saturn Magazine']}")
check((ssm["expected"], ssm["owned_count"], ssm["missing"]) == (12, 1, 11), "démo : 1 numéro possédé sur 12, il en manque 11")
s, r = call("POST", f"/api/magazines/{mags['Sega Saturn Magazine']}/generer", {"de": 1, "a": 14})
check(s == 200 and r["crees"] == 2 and r["magazine"]["missing"] == 13, "générer 1 à 14 : seuls les 2 numéros absents sont créés")
s, _ = call("POST", f"/api/magazines/{mags['Sega Saturn Magazine']}/generer", {"de": 10, "a": 2})
check(s == 400, "plage de numéros à l'envers refusée")
n7 = [i for i in r["magazine"]["issues"] if i["number"] == "7"][0]
s, _ = call("PUT", f"/api/issues/{n7['id']}", {"owned": 1})
check(get(f"/api/magazines/{mags['Sega Saturn Magazine']}")["owned_count"] == 2, "un numéro marqué possédé")
call("POST", "/api/appearances", {"magazine_id": mags["Sega Saturn Magazine"], "issue_number": "8", "ad_id": 4})
ssm = get(f"/api/magazines/{mags['Sega Saturn Magazine']}")
check(ssm["owned_count"] == 3, "saisir une pub dans un numéro manquant le marque possédé")
check(counts()["issues"] == 10, f"accueil : seuls les numéros possédés sont comptés ({counts()['issues']})")
s, mg = call("PUT", f"/api/magazines/{mags['Sega Saturn Magazine']}", {"total_issues": 20, "platform_id": plat["Sega Saturn"]})
check(mg["expected"] == 20 and mg["platform_name"] == "Sega Saturn", "nombre de numéros parus + console du magazine")

section("Mise à jour d'une base d'une version précédente (sans perte)")
import sqlite3  # noqa: E402
vieille = os.path.join(TMP, "vieille_base.sqlite")
db = sqlite3.connect(vieille)
db.executescript(APP.SCHEMA_V1 + APP.SCHEMA_V2 + "PRAGMA user_version = 2;")
db.execute("INSERT INTO magazines(name) VALUES ('Famitsu')")
db.execute("INSERT INTO issues(magazine_id, number, date) VALUES (1, '1', '1997-01')")
db.execute("INSERT INTO games(title) VALUES ('Jeu')")
db.commit()
db.close()
class _P:  # projet minimal pour init_db
    id = "test"; dir = os.path.join(TMP, "vieux_projet"); db_path = vieille
    img_dir = os.path.join(dir, "images"); thumb_dir = os.path.join(dir, "miniatures"); backup_dir = os.path.join(dir, "sauv")
APP.init_db(_P)
db = sqlite3.connect(vieille)
check(db.execute("PRAGMA user_version").fetchone()[0] == len(APP.MIGRATIONS), "base mise à jour au dernier schéma")
check(db.execute("SELECT number, date, date_label, owned FROM issues").fetchone() == ("1", "1997-01", "", 1),
      "numéros existants conservés et marqués possédés")
check(db.execute("SELECT title, genre FROM games").fetchone() == ("Jeu", ""), "jeux existants conservés")
check(len(os.listdir(_P.backup_dir)) == 1, "copie de la base faite avant la mise à jour")
db.close()

section("Lecture romaji")
check(APP.kana_romaji("ファイナルファンタジーVII") == ("fainarufantajī VII", True), "katakana + chiffres romains")
for kana, attendu in (("スーパーマリオブラザーズ", "sūpāmarioburazāzu"), ("がんばれゴエモン", "ganbaregoemon"),
                      ("メタルギアソリッド", "metarugiasoriddo"), ("チョコボ", "chokobo"), ("しんよう", "shin'you"),
                      ("ティンクル・スタースプライツ", "tinkuru sutāsupuraitsu"), ("ヴァンパイア", "vanpaia"),
                      ("マッチ", "matchi"), ("ロックマンＸ", "rokkuman X"), ("ぷよぷよ", "puyopuyo")):
    check(APP.kana_romaji(kana)[0] == attendu, f"{kana} → {attendu} ({APP.kana_romaji(kana)[0]})")
r, complet = APP.romaji("サクラ大戦")
check(r.startswith("sakura") and (complet == ("大戦" not in r)),
      f"kanji : lus si « pykakasi » est installé, sinon gardés et signalés ({r}, complet={complet})")
s, g = call("POST", "/api/games", {"title": "Puyo Puyo", "original_title": "ぷよぷよ"})
check(g["romaji"] == "puyopuyo", "romaji rempli automatiquement à la création d'un jeu")
s, g = call("PUT", f"/api/games/{g['id']}", {"romaji": "Puyo Puyo (corrigé)"})
check(g["romaji"] == "Puyo Puyo (corrigé)", "romaji modifiable à la main")
check(get("/api/games?q=corrig")[0]["id"] == g["id"], "recherche aussi sur le romaji")
check(get("/api/romaji?texte=%E3%83%86%E3%83%88%E3%83%AA%E3%82%B9")["romaji"] == "tetorisu", "lecture à la demande")
check(get("/api/games?q=Biohazard%202")[0]["romaji"] == "baiohazādo 2", "jeux de la démo : romaji rempli")

section("Recherche de jeux en ligne (Wikidata simulé)")
res = get("/api/enligne?q=Final%20Fantasy%20VII")
check(len(res) == 1, "seuls les jeux vidéo sont proposés (le film est écarté)")
ff = res[0]
check((ff["title"], ff["original_title"], ff["year"], ff["publisher"], ff["series"])
      == ("Final Fantasy VII", "ファイナルファンタジーVII", 1997, "Square", "Final Fantasy"),
      f"fiche : titres, année (sortie japonaise), éditeur, série ({ff})")
check(ff["platforms"] == ["PlayStation", "PC (Windows)"], f"plateformes ramenées aux noms de l'application ({ff['platforms']})")
check(get("/api/enligne?q=%E3%83%95%E3%82%A1%E3%82%A4%E3%83%8A%E3%83%AB%E3%83%95%E3%82%A1%E3%83%B3%E3%82%BF%E3%82%B8%E3%83%BCVII")[0]["wikidata"] == "Q100001",
      "recherche par le titre japonais")
call("POST", "/api/reglages", {"enligne": False})
s, r = call("GET", "/api/enligne?q=Final%20Fantasy%20VII")
check(s == 403 and "désactivée" in r["error"], "désactivable : plus aucun appel quand c'est coupé")
call("POST", "/api/reglages", {"enligne": True})
_faux = os.environ.pop("BDD_PUBS_WIKIDATA_FAUX", None)
APP.WIKIDATA_API = "http://127.0.0.1:9/api.php"  # personne n'écoute : comme sans Internet
try:
    APP.search_games_online("Final Fantasy")
    check(False, "sans Internet : message clair")
except APP.ApiError as e:
    check(e.status == 503 and "Internet" in e.msg, "sans Internet : message clair, pas de plantage")
if _faux:
    os.environ["BDD_PUBS_WIKIDATA_FAUX"] = _faux

section("Images")
png = open(os.path.join(TMP, "image_bleue.png"), "rb").read()
s, im = call("POST", "/api/images", {"entity": "ads", "entity_id": 2, "name": "scan.png",
                                     "data": base64.b64encode(png).decode()})
check(s == 201 and im["url"].startswith("/p/principal/images/"), "image envoyée, URL rattachée au projet")
with urllib.request.urlopen(BASE + im["url"]) as r_:
    check(r_.status == 200 and r_.read() == png, "image servie à l'identique")
call("DELETE", f"/api/images/{im['id']}")
check(not os.path.exists(os.path.join(os.environ["BDD_PUBS_DATA"], "images", im["file"])), "fichier effacé avec l'image")

section("Exports CSV")
with urllib.request.urlopen(BASE + "/api/export/apparitions.csv") as r_:
    t = r_.read().decode("utf-8")
check(t.startswith("﻿ID;Magazine;Numéro"), "CSV avec BOM et séparateur « ; » (Excel FR)")

section("Connexion réutilisée après une requête dont le contenu n'est pas lu")
conn = http.client.HTTPConnection(BASE.split("//")[1], timeout=30)
conn.request("POST", "/api/donnees/sauvegarder", body="{}", headers={"Content-Type": "application/json"})
conn.getresponse().read()
try:
    conn.request("GET", "/api/ping")
    st = conn.getresponse().status
except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
    conn = http.client.HTTPConnection(BASE.split("//")[1], timeout=30)
    conn.request("GET", "/api/ping")
    st = conn.getresponse().status
check(st == 200, "la requête suivante n'est pas faussée (pas de 501)")

section("Projets")
s, demo = call("POST", "/api/projets", {"nom": "Démo test", "demo": True})
check(s == 201, "projet de démonstration créé")
check(counts(demo["id"])["ads"] == 5, "le nouveau projet a ses propres données")
before = counts()["appearances"]
call("POST", "/api/appearances", {"magazine_id": 1, "issue_number": "500", "ad_id": 1}, projet=demo["id"])
check(counts()["appearances"] == before, "une saisie dans un projet ne touche pas le projet principal")
with urllib.request.urlopen(f"{BASE}/api/projets/{demo['id']}/export.zip") as r_:
    zdata = r_.read()
s, imp = call("POST", "/api/projets/import", raw=zdata, ctype="application/zip")
check(s == 201 and counts(imp["id"])["appearances"] == 9, "export puis import d'un projet (photos comprises)")
s, r = call("DELETE", "/api/projets/principal")
check(s == 409, "le projet de base ne peut pas être supprimé")

section("Import Excel / CSV")
def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()
xl = b64(os.path.join(TMP, "catalogue.xlsx"))
s, pv = call("POST", "/api/import/lire", {"name": "catalogue.xlsx", "data": xl})
check(s == 200 and [x["name"] for x in pv["sheets"]] == ["Liste", "Jeux"] and not pv["classeur"], "classeur .xlsx lu (2 onglets)")
liste = pv["sheets"][0]
check(liste["type"] == "numeros" and liste["mapping"]["numeros"] == {"magazine": 0, "number": 1, "date": 2, "owned": 3},
      f"onglet reconnu comme numéros, colonnes associées ({liste['type']}, {liste['mapping']['numeros']})")
check(pv["sheets"][1]["rows"][0][1] == "トバルNo.1", "texte japonais lu sans la lecture furigana")
before = counts()
args = {"name": "catalogue.xlsx", "data": xl, "type": "numeros", "sheet": "Liste", "mapping": liste["mapping"]["numeros"]}
s, r = call("POST", "/api/import/appliquer", {**args, "essai": True})
check(r["essai"] and r["crees"] == {"magazines": 1, "numéros": 3} and len(r["erreurs"]) == 1 and r["erreurs"][0]["ligne"] == 6,
      f"essai : 1 magazine et 3 numéros à créer, 1 ligne en erreur signalée ({r})")
check(counts() == before, "essai : rien n'est enregistré")
s, r = call("POST", "/api/import/appliquer", args)
mag = [m for m in get("/api/magazines") if m["name"] == "Hippon Super"][0]
iss = {i["number"]: i for i in get(f"/api/magazines/{mag['id']}")["issues"]}
check(set(iss) == {"1", "2", "3"} and iss["1"]["owned"] == 1 and iss["2"]["owned"] == 0 and iss["3"]["owned"] == 1,
      "numéros importés avec possédé / manquant")
check(iss["1"]["date_label"] == "juillet-août 1996" and iss["2"]["date"] == "1996-12-01", "dates libres et dates Excel converties")
s, r = call("POST", "/api/import/appliquer", args)
check(not r["crees"] and r["deja"].get("numéros") == 3, "réimporter le même fichier ne crée pas de doublons")
s, r = call("POST", "/api/import/appliquer", {"name": "catalogue.xlsx", "data": xl, "type": "jeux", "sheet": "Jeux",
                                             "mapping": pv["sheets"][1]["mapping"]["jeux"]})
ff7 = get("/api/games?q=Final%20Fantasy%20VII")[0]
check(r["crees"] == {"jeux": 1} and r["completes"] == {"jeux": 1} and ff7["licence"] == "Final Fantasy" and ff7["publisher"] == "Square",
      f"jeux : 1 créé, 1 existant complété sans rien remplacer ({r['crees']}, {r['completes']})")
csvw = b64(os.path.join(TMP, "jeux_windows.csv"))
s, pv = call("POST", "/api/import/lire", {"name": "jeux_windows.csv", "data": csvw})
m = pv["sheets"][0]["mapping"]["jeux"]
s, r = call("POST", "/api/import/appliquer", {"name": "jeux_windows.csv", "data": csvw, "type": "jeux", "mapping": m})
check(r["crees"].get("jeux") == 2 and "Éditeur" in pv["sheets"][0]["headers"]
      and get("/api/games?licence=Gundam")[0]["year"] == 1996, "CSV Excel Windows (« ; », accents) importé")
s, r = call("POST", "/api/import/appliquer", {"name": "x.csv", "data": csvw, "type": "parutions", "mapping": {"game": 0}})
check(s == 400 and "Magazine" in r["error"], "colonne obligatoire non choisie : message clair")
s, r = call("POST", "/api/import/lire", {"name": "vieux.xls", "data": csvw})
check(s == 400 and ".xlsx" in r["error"], "ancien format .xls : explique comment faire")
# Aller-retour : export CSV des parutions -> import dans un projet vide = mêmes chiffres
with urllib.request.urlopen(BASE + "/api/export/apparitions.csv") as r_:
    exp = r_.read()
s, vide = call("POST", "/api/projets", {"nom": "Import test"})
s, pv = call("POST", "/api/import/lire", {"name": "apparitions.csv", "data": base64.b64encode(exp).decode()}, projet=vide["id"])
s, r = call("POST", "/api/import/appliquer", {"name": "apparitions.csv", "data": base64.b64encode(exp).decode(),
                                             "type": "parutions", "mapping": pv["sheets"][0]["mapping"]["parutions"]},
            projet=vide["id"])
a, b = get("/api/search", )["stats"], get("/api/search", vide["id"])["stats"]
check(not r["erreurs"] and (a["total"], a["ads"], a["games"], a["issues"], a["for_sale"], a["pages"])
      == (b["total"], b["ads"], b["games"], b["issues"], b["for_sale"], b["pages"]),
      f"export CSV puis import dans un projet vide : mêmes chiffres ({a} / {b})")
# Ancien classeur BDD Pubs (fichier du dépôt : uniquement des lignes d'exemple)
vx = b64(os.path.join(ROOT, "BDD_Pubs.xlsx"))
s, pv = call("POST", "/api/import/lire", {"name": "BDD_Pubs.xlsx", "data": vx}, projet=vide["id"])
check(pv["classeur"], "ancien classeur « BDD Pubs » reconnu")
s, r = call("POST", "/api/import/appliquer", {"name": "BDD_Pubs.xlsx", "data": vx, "classeur": True, "essai": True},
            projet=vide["id"])
check(r["ignorees"] > 10 and not r["erreurs"] and not r["crees"].get("parutions"), "lignes « EXEMPLE » ignorées")
call("DELETE", f"/api/projets/{vide['id']}")

section("Tout exporter / Tout restaurer")
etat = lambda: sorted((p["nom"], (p["stats"] or {}).get("appearances")) for p in get("/api/projets")["projets"])
ref = etat()
with urllib.request.urlopen(BASE + "/api/projets/tout.zip") as r_:
    tout = r_.read()
call("POST", "/api/projets", {"nom": "Intrus"})
call("PUT", "/api/projets/principal", {"nom": "Autre nom"})
s, r = call("POST", "/api/projets/restaurer", raw=tout, ctype="application/zip")
check(s == 200, "restauration acceptée")
check(etat() == ref, "tout est revenu exactement comme avant (projets, noms, contenus)")
s, r = call("POST", "/api/projets/import", raw=tout, ctype="application/zip")
check(s == 400 and "Tout restaurer" in r.get("error", ""), "import d'un seul projet refuse une sauvegarde complète")

section("Sauvegarde automatique")
s, st = call("POST", "/api/donnees/sauvegarder", {})
liste = st["sauvegarde"]["liste"]
check(s == 200 and liste, "sauvegarde faite et listée")
photos = os.path.join(os.environ["BDD_PUBS_SAUVEGARDES"], "photos", "images")
check(os.path.isdir(photos) and len(os.listdir(photos)) >= 5, "photos copiées dans le dossier de sauvegarde")
call("DELETE", "/api/appearances/1")
s, r = call("POST", "/api/donnees/restaurer", {"nom": liste[0]["nom"]})
check(s == 200 and get("/api/appearances/1").get("id") == 1, "restauration d'une sauvegarde automatique")
s, r = call("POST", "/api/donnees/restaurer", {"nom": "../../x"})
check(s == 400, "nom de sauvegarde invalide refusé")

# ménage : supprime les projets créés (les tests navigateur repartent du projet principal seul)
for p in get("/api/projets")["projets"]:
    if not p["protege"]:
        call("DELETE", f"/api/projets/{p['id']}")

section("Reprise automatique des données d'une ancienne version")
home = os.path.join(TMP, "maison")
ancien = os.path.join(home, "Downloads", "BDD Pubs (ancienne)", "data")
shutil.copytree(os.environ["BDD_PUBS_DATA"], ancien, ignore=shutil.ignore_patterns("sauvegardes", "journal.txt"))
env = {k: v for k, v in os.environ.items() if k not in ("BDD_PUBS_DATA", "XDG_DATA_HOME")}
env.update(HOME=home, USERPROFILE=home, BDD_PUBS_SAUVEGARDES=os.path.join(TMP, "sauv_maison"))
port2 = int(BASE.rsplit(":", 1)[1]) + 1
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "appli", "app.py"), "--no-browser", "--port", str(port2)],
                        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    base2 = f"http://127.0.0.1:{port2}"
    d = {}
    for _ in range(60):
        try:
            d = call("GET", "/api/donnees", base=base2)[1]
            break
        except OSError:
            time.sleep(0.25)
    check(d.get("reprise") and d["reprise"]["source"].endswith(os.path.join("BDD Pubs (ancienne)", "data")),
          "anciennes données trouvées dans Téléchargements et reprises")
    check(d["contenu"]["pubs"] == counts()["ads"], "contenu repris complet")
    check(d["dossier_donnees"].startswith(home), "données rangées à l'emplacement fixe (hors du programme)")
    check(os.path.exists(os.path.join(ancien, "LISEZMOI - données reprises.txt")), "ancien dossier conservé, avec une note")
finally:
    call("POST", "/api/quitter", {}, base=f"http://127.0.0.1:{port2}")
    proc.wait(timeout=15)

print(f"{'ÉCHEC' if ECHECS else 'OK'} : {len(ECHECS)} problème(s)")
sys.exit(1 if ECHECS else 0)
