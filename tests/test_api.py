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
