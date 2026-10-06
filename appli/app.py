#!/usr/bin/env python3
"""BDD Pubs : application locale pour référencer les pubs de jeux vidéo
parues dans les magazines.

Aucune dépendance : uniquement la bibliothèque standard de Python (3.8+).
Les données sont dans le dossier « data » à côté de ce fichier :
  data/bdd_pubs.sqlite   la base
  data/images/           les images d'origine
  data/miniatures/       les miniatures (générées par le navigateur)
  data/sauvegardes/      une copie de la base à chaque démarrage

Lancement : python app.py            (ouvre http://localhost:8765)
Options   : --port 8765  --no-browser  --reseau  --demo
"""
import argparse
import base64
import binascii
import csv
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import unicodedata
import time
import traceback
import uuid
import webbrowser
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

FROZEN = getattr(sys, "frozen", False)  # True dans l'exécutable « BDD Pubs.exe »
if FROZEN:
    # Données à côté de l'exécutable, interface embarquée dans l'exécutable
    HERE = os.path.dirname(os.path.abspath(sys.executable))
    STATIC_DIR = os.path.join(getattr(sys, "_MEIPASS", HERE), "static")
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(HERE, "static")


def default_data_dir():
    """Emplacement fixe des données, indépendant de l'endroit où se trouve le programme :
    une mise à jour (ou un programme déplacé / supprimé) ne touche jamais aux données."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(base, "BDD Pubs", "data")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/BDD Pubs/data")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "bdd-pubs", "data")


def documents_dir():
    home = os.path.expanduser("~")
    for d in (os.path.join(home, "Documents"), os.path.join(home, "OneDrive", "Documents")):
        if os.path.isdir(d):
            return d
    return home


DATA_FIXED = bool(os.environ.get("BDD_PUBS_DATA"))  # dossier imposé (tests, usage avancé)
DATA_DIR = os.environ.get("BDD_PUBS_DATA") or default_data_dir()
LEGACY_DATA_DIR = os.path.join(HERE, "data")  # anciennes versions : données à côté du programme
DEFAULT_BACKUP_DIR = os.environ.get("BDD_PUBS_SAUVEGARDES") or os.path.join(documents_dir(), "BDD Pubs - sauvegardes")

APP_VERSION = "2026.10.06"


def build_id():
    """Identifiant de cette version précise (change à chaque mise à jour de l'appli)."""
    import hashlib
    h = hashlib.sha1(APP_VERSION.encode())
    if FROZEN:  # l'exécutable contient tout (ses fichiers internes sont redécompressés à chaque lancement)
        sources = [sys.executable]
    else:
        sources = [os.path.abspath(__file__)]
        for root, _dirs, files in os.walk(STATIC_DIR):
            sources += [os.path.join(root, f) for f in sorted(files)]
    for path in sources:
        try:
            st = os.stat(path)
            h.update(f"{os.path.basename(path)}:{st.st_size}:{int(st.st_mtime)}".encode())
        except OSError:
            pass
    return h.hexdigest()[:12]


BUILD = build_id()
# Projets : le projet de base (« principal ») est à la racine de data/,
# les projets supplémentaires dans data/projets/<id>/ (même organisation).
REGISTRY_PATH = os.path.join(DATA_DIR, "projets.json")

MAX_UPLOAD = 60 * 1024 * 1024
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "avif", "heic"}
IMAGE_ENTITIES = {"ads", "appearances", "issues", "games"}
# Types de fichiers servis (table interne : le module « mimetypes » de Python
# lirait sinon toute la liste des types déclarés dans le registre Windows)
CONTENT_TYPES = {
    "html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8", "svg": "image/svg+xml", "ico": "image/x-icon",
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "webp": "image/webp", "bmp": "image/bmp", "tif": "image/tiff", "tiff": "image/tiff",
    "avif": "image/avif", "heic": "image/heic", "zip": "application/zip",
}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
SCHEMA_V1 = """
CREATE TABLE platforms (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    maker TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE series (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE magazines (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    publisher TEXT NOT NULL DEFAULT '',
    frequency TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE issues (
    id INTEGER PRIMARY KEY,
    magazine_id INTEGER NOT NULL REFERENCES magazines(id) ON DELETE RESTRICT,
    number TEXT NOT NULL COLLATE NOCASE,
    date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    UNIQUE (magazine_id, number)
);
CREATE TABLE games (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    original_title TEXT NOT NULL DEFAULT '',
    series_id INTEGER REFERENCES series(id) ON DELETE SET NULL,
    publisher TEXT NOT NULL DEFAULT '',
    year INTEGER,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE ads (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE RESTRICT,
    platform_id INTEGER REFERENCES platforms(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    pages REAL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE appearances (
    id INTEGER PRIMARY KEY,
    ad_id INTEGER NOT NULL REFERENCES ads(id) ON DELETE RESTRICT,
    issue_id INTEGER NOT NULL REFERENCES issues(id) ON DELETE RESTRICT,
    page TEXT NOT NULL DEFAULT '',
    for_sale INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    entity TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    file TEXT NOT NULL,
    thumb TEXT,
    original_name TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    sort INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX idx_issues_magazine ON issues(magazine_id);
CREATE INDEX idx_games_series ON games(series_id);
CREATE INDEX idx_ads_game ON ads(game_id);
CREATE INDEX idx_ads_platform ON ads(platform_id);
CREATE INDEX idx_app_ad ON appearances(ad_id);
CREATE INDEX idx_app_issue ON appearances(issue_id);
CREATE INDEX idx_images_entity ON images(entity, entity_id);
"""

# Pour faire évoluer la base : ajouter une étape à la fin de cette liste
# (ex. "ALTER TABLE ads ADD COLUMN format TEXT NOT NULL DEFAULT ''").
# Chaque étape n'est jouée qu'une fois (numéro stocké dans PRAGMA user_version).
SCHEMA_V2 = """
CREATE TABLE ad_platforms (
    ad_id INTEGER NOT NULL REFERENCES ads(id) ON DELETE CASCADE,
    platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
    PRIMARY KEY (ad_id, platform_id)
);
CREATE INDEX idx_adplat_platform ON ad_platforms(platform_id);
INSERT INTO ad_platforms(ad_id, platform_id) SELECT id, platform_id FROM ads WHERE platform_id IS NOT NULL;
UPDATE ads SET platform_id = NULL;
"""

MIGRATIONS = [SCHEMA_V1, SCHEMA_V2]

PLATFORMS = [
    ("Famicom", "Nintendo"), ("Famicom Disk System", "Nintendo"), ("Super Famicom", "Nintendo"),
    ("Nintendo 64", "Nintendo"), ("GameCube", "Nintendo"), ("Wii", "Nintendo"), ("Wii U", "Nintendo"),
    ("Switch", "Nintendo"), ("Game Boy", "Nintendo"), ("Game Boy Color", "Nintendo"),
    ("Game Boy Advance", "Nintendo"), ("Nintendo DS", "Nintendo"), ("Nintendo 3DS", "Nintendo"),
    ("Virtual Boy", "Nintendo"), ("SG-1000", "Sega"), ("Mark III / Master System", "Sega"),
    ("Mega Drive", "Sega"), ("Mega-CD", "Sega"), ("Super 32X", "Sega"), ("Sega Saturn", "Sega"),
    ("Dreamcast", "Sega"), ("Game Gear", "Sega"), ("PC Engine", "NEC"),
    ("PC Engine CD-ROM²", "NEC"), ("PC Engine SuperGrafx", "NEC"), ("PC-FX", "NEC"),
    ("PlayStation", "Sony"), ("PlayStation 2", "Sony"), ("PlayStation 3", "Sony"),
    ("PlayStation 4", "Sony"), ("PlayStation 5", "Sony"), ("PSP", "Sony"), ("PS Vita", "Sony"),
    ("Neo Geo", "SNK"), ("Neo Geo CD", "SNK"), ("Neo Geo Pocket", "SNK"), ("WonderSwan", "Bandai"),
    ("3DO", "Panasonic"), ("Xbox", "Microsoft"), ("Xbox 360", "Microsoft"), ("MSX", ""),
    ("PC-8801", "NEC"), ("PC-9801", "NEC"), ("X68000", "Sharp"), ("FM Towns", "Fujitsu"),
    ("PC (Windows)", ""), ("Arcade", ""),
]


# ---------------------------------------------------------------------------
# Projets
# ---------------------------------------------------------------------------
class Project:
    def __init__(self, pid, name, folder):
        self.id = pid
        self.name = name
        self.dir = folder
        self.db_path = os.path.join(folder, "bdd_pubs.sqlite")
        self.img_dir = os.path.join(folder, "images")
        self.thumb_dir = os.path.join(folder, "miniatures")
        self.backup_dir = os.path.join(folder, "sauvegardes")
        self.prefix = f"/p/{pid}"


_CTX = threading.local()
REG_LOCK = threading.RLock()
OPENED = set()
PRINCIPAL = "principal"


def cur():
    """Projet de la requête en cours."""
    return _CTX.project


def use_project(project):
    _CTX.project = project
    return project


def load_registry():
    with REG_LOCK:
        try:
            with open(REGISTRY_PATH, encoding="utf-8") as f:
                reg = json.load(f)
        except (OSError, ValueError):
            reg = {}
        projets = reg.setdefault("projets", {})
        projets.setdefault(PRINCIPAL, {"nom": "Projet principal", "dossier": ""})
        if reg.get("defaut") not in projets:
            reg["defaut"] = PRINCIPAL
        return reg


def save_registry(reg):
    with REG_LOCK:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = REGISTRY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        os.replace(tmp, REGISTRY_PATH)


def project_by_id(pid):
    reg = load_registry()
    pid = pid or reg["defaut"]
    info = reg["projets"].get(pid)
    if not info:
        raise ApiError(404, "Projet introuvable (il a peut-être été supprimé).")
    folder = os.path.join(DATA_DIR, info["dossier"]) if info["dossier"] else DATA_DIR
    return Project(pid, info["nom"], folder)


def open_project(pid=None):
    """Projet prêt à l'emploi (dossiers créés, base à jour) et actif pour la requête."""
    p = project_by_id(pid)
    with REG_LOCK:
        if p.id not in OPENED:
            init_db(p)
            OPENED.add(p.id)
    return use_project(p)


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]
    return s or "projet"


def create_project(name, demo=False):
    name = (name or "").strip()
    if not name:
        raise ApiError(400, "Donnez un nom au projet")
    with REG_LOCK:
        reg = load_registry()
        if any(v["nom"].lower() == name.lower() for v in reg["projets"].values()):
            raise ApiError(409, "Un projet porte déjà ce nom.")
        base = slugify(name)
        pid, n = base, 2
        while pid in reg["projets"] or os.path.exists(os.path.join(DATA_DIR, "projets", pid)):
            pid, n = f"{base}-{n}", n + 1
        reg["projets"][pid] = {"nom": name, "dossier": f"projets/{pid}"}
        save_registry(reg)
    p = open_project(pid)
    if demo:
        load_demo()
    return p


def quick_counts(p):
    if not os.path.exists(p.db_path):
        return {"ads": 0, "appearances": 0, "games": 0}
    try:
        db = sqlite3.connect(p.db_path, timeout=5)
        try:
            c = lambda t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            return {"ads": c("ads"), "appearances": c("appearances"), "games": c("games")}
        finally:
            db.close()
    except sqlite3.Error:
        return None


def projects_info(current_id):
    reg = load_registry()
    out = []
    for pid, info in reg["projets"].items():
        p = project_by_id(pid)
        out.append({"id": pid, "nom": info["nom"], "defaut": pid == reg["defaut"],
                    "protege": pid == PRINCIPAL, "actuel": pid == current_id,
                    "stats": quick_counts(p)})
    out.sort(key=lambda x: (x["id"] != PRINCIPAL, x["nom"].lower()))
    return {"defaut": reg["defaut"], "actuel": current_id, "projets": out}


def delete_project(pid):
    with REG_LOCK:
        reg = load_registry()
        if pid not in reg["projets"]:
            raise ApiError(404, "Projet introuvable")
        if pid == PRINCIPAL:
            raise ApiError(409, "Le projet de base ne peut pas être supprimé (vous pouvez le renommer).")
        if pid == reg["defaut"]:
            raise ApiError(409, "C'est le projet ouvert au lancement : choisissez-en un autre d'abord.")
        folder = os.path.realpath(os.path.join(DATA_DIR, reg["projets"][pid]["dossier"]))
        root = os.path.realpath(os.path.join(DATA_DIR, "projets"))
        del reg["projets"][pid]
        save_registry(reg)
        OPENED.discard(pid)
    if folder.startswith(root + os.sep):
        shutil.rmtree(folder, ignore_errors=True)


def import_project(stream, length, name):
    """Crée un projet à partir d'un ZIP exporté (ou d'une sauvegarde complète)."""
    if length <= 0:
        raise ApiError(400, "Fichier vide")
    tmpdir = tempfile.mkdtemp(prefix="bddpubs_import_")
    try:
        zpath = os.path.join(tmpdir, "import.zip")
        with open(zpath, "wb") as f:
            left = length
            while left > 0:
                chunk = stream.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        try:
            z = zipfile.ZipFile(zpath)
        except zipfile.BadZipFile:
            raise ApiError(400, "Ce fichier n'est pas un ZIP valide.")
        with z:
            names = z.namelist()
            if FULL_MARKER in names:
                raise ApiError(400, "C'est une sauvegarde complète (tous les projets) : "
                                    "utilisez « Tout restaurer » dans la page Projets.")
            dbs = sorted((n for n in names if n.endswith("bdd_pubs.sqlite") and "sauvegardes/" not in n), key=len)
            if not dbs:
                raise ApiError(400, "Ce ZIP ne contient pas de projet BDD Pubs (bdd_pubs.sqlite introuvable).")
            base = dbs[0][:-len("bdd_pubs.sqlite")]
            if not name and base + "projet.json" in names:
                try:
                    name = json.loads(z.read(base + "projet.json").decode("utf-8")).get("nom", "")
                except ValueError:
                    name = ""
            name = (name or "Projet importé").strip()
            reg = load_registry()
            existing = {v["nom"].lower() for v in reg["projets"].values()}
            final, n = name, 2
            while final.lower() in existing:
                final, n = f"{name} ({n})", n + 1
            staging = os.path.join(tmpdir, "projet")
            for d in ("images", "miniatures"):
                os.makedirs(os.path.join(staging, d))
            with open(os.path.join(staging, "bdd_pubs.sqlite"), "wb") as f:
                f.write(z.read(dbs[0]))
            for n_ in names:
                for d in ("images", "miniatures"):
                    if n_.startswith(f"{base}{d}/"):
                        fname = n_.rsplit("/", 1)[-1]
                        if fname and SAFE_NAME.match(fname):
                            with open(os.path.join(staging, d, fname), "wb") as f:
                                f.write(z.read(n_))
        try:
            db = sqlite3.connect(os.path.join(staging, "bdd_pubs.sqlite"))
            db.execute("SELECT COUNT(*) FROM ads").fetchone()
            db.close()
        except sqlite3.Error:
            raise ApiError(400, "La base contenue dans ce ZIP est illisible.")
        p = create_project(final)
        OPENED.discard(p.id)
        shutil.rmtree(p.dir, ignore_errors=True)
        shutil.move(staging, p.dir)
        return open_project(p.id)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def connect():
    db = sqlite3.connect(cur().db_path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db(p):
    use_project(p)
    for d in (p.dir, p.img_dir, p.thumb_dir, p.backup_dir):
        os.makedirs(d, exist_ok=True)
    fresh = not os.path.exists(p.db_path)
    if not fresh:
        backup_on_start(p)
    db = connect()
    version = db.execute("PRAGMA user_version").fetchone()[0]
    for i, step in enumerate(MIGRATIONS[version:], start=version + 1):
        with db:
            db.executescript(step)
            db.execute(f"PRAGMA user_version = {i}")
    if fresh:
        with db:
            db.executemany("INSERT INTO platforms(name, maker) VALUES (?, ?)", PLATFORMS)
    db.close()


def backup_on_start(p, keep=15):
    """Copie de sécurité de la base à chaque lancement (garde les 15 dernières)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(p.backup_dir, f"bdd_pubs_{stamp}.sqlite")
    src = sqlite3.connect(p.db_path)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.close()
    src.close()
    old = sorted(f for f in os.listdir(p.backup_dir) if f.startswith("bdd_pubs_") and f.endswith(".sqlite"))
    for f in old[:-keep]:
        os.remove(os.path.join(p.backup_dir, f))


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def one(cur):
    r = cur.fetchone()
    return dict(r) if r else None


def img_case():
    pre = cur().prefix
    return (f"CASE WHEN im.thumb IS NOT NULL THEN '{pre}/miniatures/' || im.thumb "
            f"ELSE '{pre}/images/' || im.file END")


def img_url(entity, id_expr):
    """Sous-requête : URL de l'image principale d'un élément."""
    return (f"(SELECT {img_case()} FROM images im "
            f"WHERE im.entity = '{entity}' AND im.entity_id = {id_expr} "
            f"ORDER BY im.sort, im.id LIMIT 1)")


def like(v):
    return "%" + v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ---------------------------------------------------------------------------
# Règles de saisie
# ---------------------------------------------------------------------------
class ApiError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status
        self.msg = msg


SPEC = {
    "platforms": {"name": ("text", True), "maker": ("text", False), "notes": ("text", False)},
    "series": {"name": ("text", True), "notes": ("text", False)},
    "magazines": {"name": ("text", True), "publisher": ("text", False),
                  "frequency": ("text", False), "notes": ("text", False)},
    "issues": {"magazine_id": ("fk", True), "number": ("text", True), "date": ("date", False),
               "notes": ("text", False)},
    "games": {"title": ("text", True), "original_title": ("text", False), "series_id": ("fk", False),
              "publisher": ("text", False), "year": ("int", False), "notes": ("text", False)},
    "ads": {"game_id": ("fk", True), "description": ("text", False),
            "pages": ("real", False), "notes": ("text", False)},
    "appearances": {"ad_id": ("fk", True), "issue_id": ("fk", True), "page": ("text", False),
                    "for_sale": ("bool", False), "notes": ("text", False)},
}

LABELS = {
    "name": "Nom", "number": "Numéro", "title": "Titre", "magazine_id": "Magazine",
    "game_id": "Jeu", "ad_id": "Pub", "issue_id": "Numéro", "date": "Date", "year": "Année",
    "pages": "Nb pages",
}


def clean(table, data, partial=False):
    out = {}
    for field, (kind, required) in SPEC[table].items():
        if field not in data:
            if required and not partial:
                raise ApiError(400, f"Champ obligatoire : {LABELS.get(field, field)}")
            continue
        v = data[field]
        if isinstance(v, str):
            v = v.strip()
        if v in ("", None):
            if required:
                raise ApiError(400, f"Champ obligatoire : {LABELS.get(field, field)}")
            v = None if kind in ("fk", "int", "real") else (0 if kind == "bool" else "")
        elif kind in ("fk", "int"):
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ApiError(400, f"{LABELS.get(field, field)} : nombre entier attendu")
        elif kind == "real":
            try:
                v = float(str(v).replace(",", "."))
            except ValueError:
                raise ApiError(400, f"{LABELS.get(field, field)} : nombre attendu")
        elif kind == "bool":
            v = 1 if v in (True, 1, "1", "true", "oui", "○") else 0
        elif kind == "date":
            v = str(v)
            if not DATE_RE.match(v):
                raise ApiError(400, "Date : format AAAA, AAAA-MM ou AAAA-MM-JJ attendu")
        else:
            v = str(v)
        out[field] = v
    return out


def friendly_integrity(table, err):
    msg = str(err)
    if "UNIQUE" in msg:
        if table == "issues":
            return "Ce numéro existe déjà pour ce magazine."
        return "Ce nom existe déjà."
    if "FOREIGN KEY" in msg:
        return "Élément lié introuvable ou encore utilisé ailleurs."
    return msg


# ---------------------------------------------------------------------------
# Requêtes de liste / détail
# ---------------------------------------------------------------------------
APP_JOIN = """
FROM appearances ap
JOIN ads a ON a.id = ap.ad_id
JOIN games g ON g.id = a.game_id
JOIN issues i ON i.id = ap.issue_id
JOIN magazines m ON m.id = i.magazine_id
LEFT JOIN series s ON s.id = g.series_id
"""


def ad_platforms_sql(ad_expr):
    """Noms des plateformes d'une pub, « PS4 / Switch »."""
    return (f"(SELECT group_concat(name, ' / ') FROM (SELECT p.name FROM ad_platforms x "
            f"JOIN platforms p ON p.id = x.platform_id WHERE x.ad_id = {ad_expr} ORDER BY p.name))")


def has_platform_sql(ad_expr):
    return f"EXISTS (SELECT 1 FROM ad_platforms x WHERE x.ad_id = {ad_expr} AND x.platform_id = ?)"


def set_ad_platforms(db, ad_id, ids):
    if ids is None:
        return
    if not isinstance(ids, list):
        raise ApiError(400, "Plateformes : liste attendue")
    try:
        ids = sorted({int(i) for i in ids})
    except (TypeError, ValueError):
        raise ApiError(400, "Plateformes invalides")
    db.execute("DELETE FROM ad_platforms WHERE ad_id = ?", (ad_id,))
    db.executemany("INSERT INTO ad_platforms(ad_id, platform_id) VALUES (?, ?)", [(ad_id, i) for i in ids])

NUM_ORDER = "CAST({0} AS INTEGER), {0}"


def list_platforms(db, qs):
    return rows(db.execute("""
        SELECT p.*,
          (SELECT COUNT(*) FROM ad_platforms x WHERE x.platform_id = p.id) AS ads_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ad_platforms x ON x.ad_id = ap.ad_id
             WHERE x.platform_id = p.id) AS app_count
        FROM platforms p ORDER BY p.name"""))


def list_series(db, qs):
    return rows(db.execute("""
        SELECT s.*,
          (SELECT COUNT(*) FROM games g WHERE g.series_id = s.id) AS games_count,
          (SELECT COUNT(*) FROM ads a JOIN games g ON g.id = a.game_id
             WHERE g.series_id = s.id) AS ads_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             JOIN games g ON g.id = a.game_id WHERE g.series_id = s.id) AS app_count
        FROM series s ORDER BY s.name"""))


def list_magazines(db, qs, mid=None):
    where = "WHERE m.id = ?" if mid else ""
    return rows(db.execute(f"""
        SELECT m.*,
          (SELECT COUNT(*) FROM issues i WHERE i.magazine_id = m.id) AS issues_count,
          (SELECT COUNT(*) FROM appearances ap JOIN issues i ON i.id = ap.issue_id
             WHERE i.magazine_id = m.id) AS app_count,
          (SELECT COUNT(*) FROM appearances ap JOIN issues i ON i.id = ap.issue_id
             WHERE i.magazine_id = m.id AND ap.for_sale = 1) AS sale_count,
          (SELECT MIN(NULLIF(i.date, '')) FROM issues i WHERE i.magazine_id = m.id) AS first_date,
          (SELECT MAX(NULLIF(i.date, '')) FROM issues i WHERE i.magazine_id = m.id) AS last_date
        FROM magazines m {where} ORDER BY m.name""", (mid,) if mid else ()))


def list_issues(db, qs, iid=None):
    where, params = [], []
    if iid:
        where.append("i.id = ?")
        params.append(iid)
    if qs.get("magazine_id"):
        where.append("i.magazine_id = ?")
        params.append(qs["magazine_id"])
    if qs.get("number") is not None and qs.get("magazine_id"):
        where.append("i.number = ?")
        params.append(qs["number"])
    w = ("WHERE " + " AND ".join(where)) if where else ""
    return rows(db.execute(f"""
        SELECT i.*, m.name AS magazine_name,
          (SELECT COUNT(*) FROM appearances ap WHERE ap.issue_id = i.id) AS app_count,
          (SELECT COUNT(*) FROM appearances ap WHERE ap.issue_id = i.id AND ap.for_sale = 1) AS sale_count,
          {img_url('issues', 'i.id')} AS thumb_url
        FROM issues i JOIN magazines m ON m.id = i.magazine_id {w}
        ORDER BY m.name, NULLIF(i.date, '') IS NULL, i.date, {NUM_ORDER.format('i.number')}""", params))


def list_games(db, qs, gid=None):
    where, params = [], []
    if gid:
        where.append("g.id = ?")
        params.append(gid)
    if qs.get("q"):
        where.append("(g.title LIKE ? ESCAPE '\\' OR g.original_title LIKE ? ESCAPE '\\' "
                     "OR g.publisher LIKE ? ESCAPE '\\')")
        params += [like(qs["q"])] * 3
    if qs.get("series_id"):
        where.append("g.series_id = ?")
        params.append(qs["series_id"])
    w = ("WHERE " + " AND ".join(where)) if where else ""
    res = rows(db.execute(f"""
        SELECT g.*, s.name AS series_name,
          (SELECT group_concat(name, ' / ') FROM (SELECT DISTINCT p.name FROM ads a
             JOIN ad_platforms x ON x.ad_id = a.id JOIN platforms p ON p.id = x.platform_id
             WHERE a.game_id = g.id ORDER BY p.name)) AS platforms,
          (SELECT COUNT(*) FROM ads a WHERE a.game_id = g.id) AS ads_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             WHERE a.game_id = g.id) AS app_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             WHERE a.game_id = g.id AND ap.for_sale = 1) AS sale_count,
          (SELECT MIN(NULLIF(i.date, '')) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             JOIN issues i ON i.id = ap.issue_id WHERE a.game_id = g.id) AS first_date,
          COALESCE({img_url('games', 'g.id')},
            (SELECT {img_case()}
             FROM images im JOIN ads a ON im.entity = 'ads' AND im.entity_id = a.id
             WHERE a.game_id = g.id ORDER BY im.sort, im.id LIMIT 1)) AS thumb_url
        FROM games g LEFT JOIN series s ON s.id = g.series_id {w}
        ORDER BY g.title COLLATE NOCASE, g.year""", params))
    return res


def list_ads(db, qs, aid=None):
    where, params = [], []
    if aid:
        where.append("a.id = ?")
        params.append(aid)
    if qs.get("q"):
        q = qs["q"].strip()
        if re.fullmatch(r"#?\d+", q):
            where.append("a.id = ?")
            params.append(int(q.lstrip("#")))
        else:
            where.append("(g.title LIKE ? ESCAPE '\\' OR g.original_title LIKE ? ESCAPE '\\' "
                         "OR a.description LIKE ? ESCAPE '\\' OR a.notes LIKE ? ESCAPE '\\')")
            params += [like(q)] * 4
    for key, col in (("game_id", "a.game_id"), ("series_id", "g.series_id")):
        if qs.get(key):
            where.append(f"{col} = ?")
            params.append(qs[key])
    if qs.get("platform_id"):
        where.append(has_platform_sql("a.id"))
        params.append(qs["platform_id"])
    if qs.get("sans_image") == "1":
        where.append("NOT EXISTS (SELECT 1 FROM images im WHERE im.entity = 'ads' AND im.entity_id = a.id)")
    w = ("WHERE " + " AND ".join(where)) if where else ""
    order = "a.id DESC" if qs.get("tri") == "recent" else "g.title COLLATE NOCASE, a.id"
    res = rows(db.execute(f"""
        SELECT a.*, g.title AS game_title, g.original_title, g.series_id,
          {ad_platforms_sql('a.id')} AS platform_name, s.name AS series_name,
          (SELECT group_concat(platform_id) FROM ad_platforms x WHERE x.ad_id = a.id) AS platform_ids,
          (SELECT COUNT(*) FROM appearances ap WHERE ap.ad_id = a.id) AS app_count,
          (SELECT COUNT(*) FROM appearances ap WHERE ap.ad_id = a.id AND ap.for_sale = 1) AS sale_count,
          (SELECT COUNT(*) FROM images im WHERE im.entity = 'ads' AND im.entity_id = a.id) AS img_count,
          (SELECT MIN(NULLIF(i.date, '')) FROM appearances ap JOIN issues i ON i.id = ap.issue_id
             WHERE ap.ad_id = a.id) AS first_date,
          {img_url('ads', 'a.id')} AS thumb_url
        FROM ads a JOIN games g ON g.id = a.game_id
        LEFT JOIN series s ON s.id = g.series_id {w}
        ORDER BY {order}""", params))
    for r in res:
        r["platform_ids"] = [int(x) for x in (r["platform_ids"] or "").split(",") if x]
    return res


def search(db, qs, limit=None, offset=0):
    """Recherche croisée sur les apparitions (une pub dans un numéro)."""
    where, params = [], []

    def eq(key, col):
        if qs.get(key) not in (None, ""):
            where.append(f"{col} = ?")
            params.append(qs[key])

    eq("magazine_id", "i.magazine_id")
    eq("issue_id", "ap.issue_id")
    eq("numero", "i.number")
    eq("game_id", "a.game_id")
    eq("series_id", "g.series_id")
    if qs.get("platform_id"):
        where.append(has_platform_sql("a.id"))
        params.append(qs["platform_id"])
    if qs.get("ad_id"):
        where.append("ap.ad_id = ?")
        params.append(str(qs["ad_id"]).lstrip("#"))
    if qs.get("annee"):
        where.append("substr(i.date, 1, 4) = ?")
        params.append(qs["annee"])
    if qs.get("jeu"):
        where.append("(g.title LIKE ? ESCAPE '\\' OR g.original_title LIKE ? ESCAPE '\\')")
        params += [like(qs["jeu"])] * 2
    if qs.get("vente") in ("1", "0"):
        where.append("ap.for_sale = ?")
        params.append(int(qs["vente"]))
    if qs.get("q"):
        where.append("(a.description LIKE ? ESCAPE '\\' OR a.notes LIKE ? ESCAPE '\\' "
                     "OR ap.notes LIKE ? ESCAPE '\\')")
        params += [like(qs["q"])] * 3
    if qs.get("id"):
        where.append("ap.id = ?")
        params.append(qs["id"])
    w = ("WHERE " + " AND ".join(where)) if where else ""

    tri = qs.get("tri", "")
    if tri == "recent":
        order = "ap.id DESC"
    elif tri == "jeu":
        order = f"g.title COLLATE NOCASE, NULLIF(i.date, '') IS NULL, i.date, m.name"
    elif tri == "date":
        order = f"NULLIF(i.date, '') IS NULL, i.date, m.name, {NUM_ORDER.format('i.number')}, {NUM_ORDER.format('ap.page')}"
    else:
        order = (f"m.name, NULLIF(i.date, '') IS NULL, i.date, {NUM_ORDER.format('i.number')}, "
                 f"{NUM_ORDER.format('ap.page')}")
    lim = f"LIMIT {int(limit)} OFFSET {int(offset)}" if limit else ""
    items = rows(db.execute(f"""
        SELECT ap.id, ap.page, ap.for_sale, ap.notes, ap.ad_id, ap.issue_id, ap.created_at,
          i.number, i.date, m.id AS magazine_id, m.name AS magazine,
          g.id AS game_id, g.title AS game, g.original_title, {ad_platforms_sql('a.id')} AS platform,
          s.id AS series_id, s.name AS series, a.description, a.pages,
          COALESCE({img_url('appearances', 'ap.id')}, {img_url('ads', 'a.id')}) AS thumb_url
        {APP_JOIN} {w} ORDER BY {order} {lim}""", params))
    st = one(db.execute(f"""
        SELECT COUNT(*) AS total, COUNT(DISTINCT ap.ad_id) AS ads, COUNT(DISTINCT a.game_id) AS games,
          COUNT(DISTINCT ap.issue_id) AS issues, COUNT(DISTINCT i.magazine_id) AS magazines,
          COALESCE(SUM(ap.for_sale), 0) AS for_sale, COALESCE(SUM(a.pages), 0) AS pages
        {APP_JOIN} {w}""", params))
    return {"items": items, "stats": st}


def with_urls(im):
    if im:
        pre = cur().prefix
        im["url"] = f"{pre}/images/{im['file']}"
        im["thumb_url"] = f"{pre}/miniatures/{im['thumb']}" if im.get("thumb") else im["url"]
    return im


def images_of(db, entity, eid):
    return [with_urls(im) for im in rows(db.execute(
        "SELECT * FROM images WHERE entity = ? AND entity_id = ? ORDER BY sort, id", (entity, eid)))]


def detail(db, table, rid):
    if table == "games":
        g = (list_games(db, {}, rid) or [None])[0]
        if g:
            g["ads"] = list_ads(db, {"game_id": rid})
            g["appearances"] = search(db, {"game_id": rid, "tri": "date"})["items"]
            g["images"] = images_of(db, "games", rid)
        return g
    if table == "ads":
        a = (list_ads(db, {}, rid) or [None])[0]
        if a:
            a["images"] = images_of(db, "ads", rid)
            a["appearances"] = search(db, {"ad_id": rid, "tri": "date"})["items"]
        return a
    if table == "magazines":
        m = (list_magazines(db, {}, rid) or [None])[0]
        if m:
            m["issues"] = list_issues(db, {"magazine_id": rid})
        return m
    if table == "issues":
        i = (list_issues(db, {}, rid) or [None])[0]
        if i:
            i["images"] = images_of(db, "issues", rid)
            i["appearances"] = search(db, {"issue_id": rid})["items"]
        return i
    if table == "appearances":
        res = search(db, {"id": rid})["items"]
        if res:
            res[0]["images"] = images_of(db, "appearances", rid)
            return res[0]
        return None
    return one(db.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)))


LISTERS = {"platforms": list_platforms, "series": list_series, "magazines": list_magazines,
           "issues": list_issues, "games": list_games, "ads": list_ads}

DELETE_CHECKS = {
    "games": ("SELECT COUNT(*) FROM ads WHERE game_id = ?",
              "Ce jeu a {n} pub(s). Supprimez-les ou rattachez-les à un autre jeu d'abord."),
    "ads": ("SELECT COUNT(*) FROM appearances WHERE ad_id = ?",
            "Cette pub est référencée dans {n} numéro(s). Supprimez d'abord ces parutions."),
    "magazines": ("SELECT COUNT(*) FROM issues WHERE magazine_id = ?",
                  "Ce magazine a {n} numéro(s). Supprimez-les d'abord."),
    "issues": ("SELECT COUNT(*) FROM appearances WHERE issue_id = ?",
               "Ce numéro contient {n} pub(s) référencée(s). Supprimez-les d'abord."),
}


def ensure_issue(db, magazine_id, number, date=""):
    number = str(number or "").strip()
    if not magazine_id or not number:
        raise ApiError(400, "Magazine et numéro obligatoires")
    r = db.execute("SELECT id, date FROM issues WHERE magazine_id = ? AND number = ?",
                   (magazine_id, number)).fetchone()
    if r:
        if date and not r["date"]:
            data = clean("issues", {"date": date}, partial=True)
            db.execute("UPDATE issues SET date = ? WHERE id = ?", (data["date"], r["id"]))
        return r["id"]
    data = clean("issues", {"magazine_id": magazine_id, "number": number, "date": date or ""})
    return db.execute("INSERT INTO issues(magazine_id, number, date) VALUES (?, ?, ?)",
                      (data["magazine_id"], data["number"], data["date"])).lastrowid


def delete_images(db, entity, eid):
    for im in images_of(db, entity, eid):
        remove_image_files(im)
    db.execute("DELETE FROM images WHERE entity = ? AND entity_id = ?", (entity, eid))


def remove_image_files(im):
    for folder, name in ((cur().img_dir, im["file"]), (cur().thumb_dir, im["thumb"])):
        if name:
            try:
                os.remove(os.path.join(folder, name))
            except FileNotFoundError:
                pass


def decode_b64(s):
    if not s:
        return None
    if s.startswith("data:"):
        s = s.split(",", 1)[1]
    try:
        return base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError):
        raise ApiError(400, "Image illisible")


def save_image(db, body):
    entity = body.get("entity")
    if entity not in IMAGE_ENTITIES:
        raise ApiError(400, "Type d'élément inconnu pour l'image")
    try:
        eid = int(body.get("entity_id"))
    except (TypeError, ValueError):
        raise ApiError(400, "Élément manquant pour l'image")
    if not db.execute(f"SELECT 1 FROM {entity} WHERE id = ?", (eid,)).fetchone():
        raise ApiError(404, "Élément introuvable")
    name = os.path.basename(str(body.get("name") or "image.jpg"))
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "jpg"
    if ext not in IMAGE_EXT:
        raise ApiError(400, f"Format d'image non pris en charge (.{ext})")
    data = decode_b64(body.get("data"))
    if not data:
        raise ApiError(400, "Image vide")
    thumb = decode_b64(body.get("thumb"))
    stem = f"{entity}{eid}_{uuid.uuid4().hex[:10]}"
    fname = f"{stem}.{ext}"
    with open(os.path.join(cur().img_dir, fname), "wb") as f:
        f.write(data)
    tname = None
    if thumb:
        tname = f"{stem}.jpg"
        with open(os.path.join(cur().thumb_dir, tname), "wb") as f:
            f.write(thumb)
    sort = db.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM images WHERE entity = ? AND entity_id = ?",
                      (entity, eid)).fetchone()[0]
    iid = db.execute(
        "INSERT INTO images(entity, entity_id, file, thumb, original_name, caption, sort) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entity, eid, fname, tname, name, str(body.get("caption") or ""), sort)).lastrowid
    return with_urls(one(db.execute("SELECT * FROM images WHERE id = ?", (iid,))))


def dashboard(db):
    count = lambda sql: db.execute(sql).fetchone()[0]
    return {
        "counts": {
            "appearances": count("SELECT COUNT(*) FROM appearances"),
            "ads": count("SELECT COUNT(*) FROM ads"),
            "games": count("SELECT COUNT(*) FROM games"),
            "magazines": count("SELECT COUNT(*) FROM magazines"),
            "issues": count("SELECT COUNT(*) FROM issues"),
            "series": count("SELECT COUNT(*) FROM series"),
            "images": count("SELECT COUNT(*) FROM images"),
            "for_sale": count("SELECT COUNT(*) FROM appearances WHERE for_sale = 1"),
            "ads_without_image": count(
                "SELECT COUNT(*) FROM ads a WHERE NOT EXISTS (SELECT 1 FROM images im "
                "WHERE im.entity = 'ads' AND im.entity_id = a.id)"),
            "week": count("SELECT COUNT(*) FROM appearances "
                          "WHERE created_at >= datetime('now', 'localtime', '-7 days')"),
        },
        "recent": search(db, {"tri": "recent"}, limit=12)["items"],
        "top_games": rows(db.execute(f"""
            SELECT g.id, g.title, COUNT(*) AS n, COUNT(DISTINCT a.id) AS ads
            {APP_JOIN} GROUP BY g.id ORDER BY n DESC, g.title LIMIT 10""")),
        "top_magazines": rows(db.execute(f"""
            SELECT m.id, m.name, COUNT(*) AS n, COUNT(DISTINCT i.id) AS issues
            {APP_JOIN} GROUP BY m.id ORDER BY n DESC, m.name LIMIT 10""")),
    }


# ---------------------------------------------------------------------------
# Exports CSV (séparateur « ; » + BOM : s'ouvre directement dans Excel FR)
# ---------------------------------------------------------------------------
def to_csv(headers, data):
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(headers)
    for r in data:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue().encode("utf-8")


def fmt_num(v):
    if v is None:
        return ""
    return str(int(v)) if float(v).is_integer() else str(v).replace(".", ",")


def csv_appearances(items):
    return to_csv(
        ["ID", "Magazine", "Numéro", "Date", "Page", "Jeu", "Titre original", "Plateforme", "Série",
         "ID pub", "Description pub", "Nb pages", "En vente", "Remarques"],
        [(r["id"], r["magazine"], r["number"], r["date"], r["page"], r["game"], r["original_title"],
          r["platform"], r["series"], r["ad_id"], r["description"], fmt_num(r["pages"]),
          "○" if r["for_sale"] else "×", r["notes"]) for r in items])


def export_csv(db, name, qs):
    if name == "apparitions":
        return csv_appearances(search(db, qs)["items"])
    if name == "pubs":
        return to_csv(["ID", "Jeu", "Plateforme", "Série", "Description", "Nb pages", "Remarques",
                       "Nb apparitions", "Dont en vente", "Nb images", "1re parution"],
                      [(r["id"], r["game_title"], r["platform_name"], r["series_name"], r["description"],
                        fmt_num(r["pages"]), r["notes"], r["app_count"], r["sale_count"], r["img_count"],
                        r["first_date"]) for r in list_ads(db, {})])
    if name == "jeux":
        return to_csv(["ID", "Titre", "Titre original", "Série", "Éditeur", "Année", "Remarques",
                       "Nb pubs", "Nb apparitions", "Dont en vente", "1re parution"],
                      [(r["id"], r["title"], r["original_title"], r["series_name"], r["publisher"],
                        r["year"], r["notes"], r["ads_count"], r["app_count"], r["sale_count"],
                        r["first_date"]) for r in list_games(db, {})])
    if name == "magazines":
        return to_csv(["ID", "Magazine", "Éditeur", "Périodicité", "Remarques", "Nb numéros",
                       "Nb apparitions", "Dont en vente"],
                      [(r["id"], r["name"], r["publisher"], r["frequency"], r["notes"], r["issues_count"],
                        r["app_count"], r["sale_count"]) for r in list_magazines(db, {})])
    if name == "numeros":
        return to_csv(["ID", "Magazine", "Numéro", "Date", "Remarques", "Nb pubs", "Dont en vente"],
                      [(r["id"], r["magazine_name"], r["number"], r["date"], r["notes"], r["app_count"],
                        r["sale_count"]) for r in list_issues(db, {})])
    if name == "series":
        return to_csv(["ID", "Série", "Remarques", "Nb jeux", "Nb pubs", "Nb apparitions"],
                      [(r["id"], r["name"], r["notes"], r["games_count"], r["ads_count"], r["app_count"])
                       for r in list_series(db, {})])
    if name == "plateformes":
        return to_csv(["ID", "Plateforme", "Constructeur", "Remarques", "Nb pubs", "Nb apparitions"],
                      [(r["id"], r["name"], r["maker"], r["notes"], r["ads_count"], r["app_count"])
                       for r in list_platforms(db, {})])
    raise ApiError(404, "Export inconnu")


def build_backup():
    """ZIP complet : base + images + miniatures. Renvoie le chemin du fichier temporaire."""
    tmpdir = tempfile.mkdtemp(prefix="bddpubs_")
    snap = os.path.join(tmpdir, "bdd_pubs.sqlite")
    src = sqlite3.connect(cur().db_path)
    dst = sqlite3.connect(snap)
    src.backup(dst)
    dst.close()
    src.close()
    zpath = os.path.join(tmpdir, "sauvegarde.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(snap, "data/bdd_pubs.sqlite")
        z.writestr("data/projet.json", json.dumps({"nom": cur().name, "id": cur().id}, ensure_ascii=False))
        for folder, arc in ((cur().img_dir, "data/images"), (cur().thumb_dir, "data/miniatures")):
            for f in os.listdir(folder):
                z.write(os.path.join(folder, f), f"{arc}/{f}", compress_type=zipfile.ZIP_STORED)
    return tmpdir, zpath


# ---------------------------------------------------------------------------
# Sauvegarde complète : tous les projets (bases + images) dans un seul ZIP,
# avec la même organisation que le dossier data/. « Tout restaurer » la remet en place.
# ---------------------------------------------------------------------------
FULL_MARKER = "data/bdd_pubs_sauvegarde_complete.json"
FULL_MEMBER = re.compile(
    r"^data/(?:projets/(?P<pid>[a-z0-9-]+)/)?(?:bdd_pubs\.sqlite|projet\.json|(?:images|miniatures)/[A-Za-z0-9_.-]+)$")


def export_all(zpath):
    """Écrit dans zpath le ZIP de tous les projets. Copies cohérentes des bases (API de sauvegarde SQLite)."""
    reg = load_registry()
    tmpdir = tempfile.mkdtemp(prefix="bddpubs_tout_")
    try:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(FULL_MARKER, json.dumps({"type": "sauvegarde complète", "version": APP_VERSION,
                                                "date": datetime.now().isoformat(timespec="seconds"),
                                                "projets": len(reg["projets"])}, ensure_ascii=False))
            z.writestr("data/projets.json", json.dumps(reg, ensure_ascii=False, indent=2))
            for pid, info in reg["projets"].items():
                p = project_by_id(pid)
                arc = "data/" + (f"{info['dossier']}/" if info["dossier"] else "")
                if os.path.exists(p.db_path):
                    snap = os.path.join(tmpdir, f"{pid}.sqlite")
                    src = sqlite3.connect(p.db_path)
                    dst = sqlite3.connect(snap)
                    src.backup(dst)
                    dst.close()
                    src.close()
                    z.write(snap, arc + "bdd_pubs.sqlite")
                for folder, sub in ((p.img_dir, "images"), (p.thumb_dir, "miniatures")):
                    if os.path.isdir(folder):
                        for f in os.listdir(folder):
                            z.write(os.path.join(folder, f), f"{arc}{sub}/{f}", compress_type=zipfile.ZIP_STORED)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def save_stream(stream, length, path):
    with open(path, "wb") as f:
        left = length
        while left > 0:
            chunk = stream.read(min(1 << 20, left))
            if not chunk:
                break
            f.write(chunk)
            left -= len(chunk)


def _remove(path):
    """Suppression tolérante (Windows peut garder un fichier ouvert un court instant)."""
    for _ in range(20):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            return
        except OSError:
            time.sleep(0.25)
    raise ApiError(409, f"Impossible de remplacer {os.path.basename(path)} : fichier utilisé. Réessayez.")


def restore_all(stream, length):
    """Remplace TOUTES les données par une sauvegarde complète (après une copie de sécurité)."""
    if length <= 0:
        raise ApiError(400, "Fichier vide")
    work = tempfile.mkdtemp(prefix="bddpubs_restau_")
    try:
        zpath = os.path.join(work, "restauration.zip")
        save_stream(stream, length, zpath)
        try:
            z = zipfile.ZipFile(zpath)
        except zipfile.BadZipFile:
            raise ApiError(400, "Ce fichier n'est pas un ZIP valide.")
        with z:
            names = z.namelist()
            if FULL_MARKER not in names or "data/projets.json" not in names:
                raise ApiError(400, "Ce ZIP n'est pas une sauvegarde complète (« Tout exporter »). "
                                    "Pour un seul projet, utilisez « Importer un projet ».")
            try:
                reg = json.loads(z.read("data/projets.json").decode("utf-8"))
                assert isinstance(reg.get("projets"), dict)
            except (ValueError, AssertionError):
                raise ApiError(400, "Liste des projets illisible dans la sauvegarde.")
            staging = os.path.join(work, "data")
            for n in names:
                m = FULL_MEMBER.match(n)
                if not m:
                    continue  # tout le reste est ignoré (chemins inattendus compris)
                dest = os.path.join(staging, *n.split("/")[1:])
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(z.read(n))
        return apply_restore(staging, reg)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def apply_restore(staging, reg):
    """Remplace toutes les données par le contenu du dossier staging (organisation de data/),
    après vérification des bases et une copie de sécurité de l'existant."""
    for pid, info in reg["projets"].items():
        if not re.fullmatch(r"[a-z0-9-]+", pid) or (info.get("dossier") not in ("", f"projets/{pid}")):
            raise ApiError(400, "Sauvegarde invalide (dossier de projet inattendu).")
        dbp = os.path.join(staging, info["dossier"], "bdd_pubs.sqlite") if info["dossier"] else \
            os.path.join(staging, "bdd_pubs.sqlite")
        if os.path.exists(dbp):
            try:
                db = sqlite3.connect(dbp)
                db.execute("SELECT COUNT(*) FROM ads").fetchone()
                db.close()
            except sqlite3.Error:
                raise ApiError(400, f"La base du projet « {info.get('nom', pid)} » est illisible.")
    # 1. copie de sécurité de l'existant (avant le verrou : la sauvegarde automatique le prend aussi)
    safety = safety_copy("avant_restauration")
    with REG_LOCK:
        # 2. remplacement (réglages, journal et sauvegardes sont conservés)
        for name in DATA_ITEMS:
            _remove(os.path.join(DATA_DIR, name))
        for name in DATA_ITEMS:
            src = os.path.join(staging, name)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(DATA_DIR, name))
            elif os.path.isfile(src):
                shutil.copy2(src, os.path.join(DATA_DIR, name))
        if not os.path.exists(REGISTRY_PATH):
            save_registry(reg)
        OPENED.clear()
    open_project(None)  # base de lancement prête (dossiers, mise à jour éventuelle)
    return {"projets": len(reg["projets"]), "securite": safety}


DATA_ITEMS = ("bdd_pubs.sqlite", "images", "miniatures", "projets", "projets.json")


def safety_copy(reason):
    """Copie de sécurité avant de remplacer les données. Passe par la sauvegarde automatique
    (bases + seules les nouvelles photos : léger) ; ZIP complet seulement si elle est impossible."""
    state = auto_backup()
    if state.get("ok"):
        return f"sauvegarde automatique du {datetime.fromisoformat(state['date']):%d/%m/%Y à %Hh%M}"
    safety_dir = os.path.join(DATA_DIR, "sauvegardes")
    os.makedirs(safety_dir, exist_ok=True)
    safety = os.path.join(safety_dir, f"{reason}_{datetime.now():%Y%m%d-%H%M%S}.zip")
    export_all(safety)
    prune_safety_copies()
    return os.path.relpath(safety, DATA_DIR)


def prune_safety_copies(keep=5):
    """Copies de sécurité (avant restauration / reprise) : on garde les plus récentes."""
    d = os.path.join(DATA_DIR, "sauvegardes")
    try:
        zips = sorted((f for f in os.listdir(d) if f.startswith(("avant_restauration_", "avant_reprise_"))
                       and f.endswith(".zip")), key=lambda f: os.path.getmtime(os.path.join(d, f)))
    except OSError:
        return
    for f in zips[:-keep]:
        try:
            os.remove(os.path.join(d, f))
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Protection des données
#  - reprise automatique des données d'une ancienne version (rangées à côté du programme)
#  - sauvegarde automatique quotidienne hors du dossier de l'application
# ---------------------------------------------------------------------------
def describe_data(d):
    """Contenu d'un dossier de données : nombre de jeux / pubs / parutions / photos, tous projets."""
    out = {"chemin": d, "jeux": 0, "pubs": 0, "parutions": 0, "photos": 0, "projets": 0, "date": 0}
    dbs = [os.path.join(d, "bdd_pubs.sqlite")]
    pdir = os.path.join(d, "projets")
    if os.path.isdir(pdir):
        dbs += [os.path.join(pdir, x, "bdd_pubs.sqlite") for x in sorted(os.listdir(pdir))]
    for dbp in dbs:
        if not os.path.isfile(dbp):
            continue
        out["projets"] += 1
        out["date"] = max(out["date"], os.path.getmtime(dbp))
        try:
            from pathlib import Path
            db = sqlite3.connect(Path(dbp).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
            try:
                c = lambda t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                out["jeux"] += c("games")
                out["pubs"] += c("ads")
                out["parutions"] += c("appearances")
                out["photos"] += c("images")
            finally:
                db.close()
        except sqlite3.Error:
            pass
    out["total"] = out["jeux"] + out["pubs"] + out["parutions"]
    out["date_txt"] = datetime.fromtimestamp(out["date"]).strftime("%d/%m/%Y %H:%M") if out["date"] else ""
    return out


SKIP_SCAN = {"appdata", "node_modules", "$recycle.bin", "windows", "program files", "program files (x86)",
             "programdata", "library", "__pycache__", "site-packages", "bdd pubs - sauvegardes"}
LAST_SCAN = set()


def scan_for_data(max_depth=3, limit=8000, extra=()):
    """Cherche des dossiers « data » d'anciennes versions (à côté d'un programme BDD Pubs)."""
    home = os.path.expanduser("~")
    roots = []
    for r in [HERE, os.path.dirname(HERE), home] + [os.path.join(home, n) for n in (
            "Desktop", "Bureau", "Downloads", "Téléchargements", "Documents",
            os.path.join("OneDrive", "Desktop"), os.path.join("OneDrive", "Bureau"),
            os.path.join("OneDrive", "Documents"))]:
        if os.path.isdir(r) and r not in roots:
            roots.append(r)
    current = os.path.realpath(DATA_DIR)
    found = {}

    def consider(path):
        rp = os.path.realpath(path)
        if rp != current and rp not in found and os.path.isfile(os.path.join(rp, "bdd_pubs.sqlite")):
            found[rp] = describe_data(rp)

    for x in extra:
        if x:
            consider(x)
    consider(LEGACY_DATA_DIR)
    seen = 0
    for root in roots:
        stack = [(root, 0)]
        while stack and seen < limit:
            d, depth = stack.pop()
            seen += 1
            try:
                entries = list(os.scandir(d))
            except OSError:
                continue
            for e in entries:
                try:
                    if e.is_symlink() or getattr(e, "is_junction", lambda: False)() \
                            or not e.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if e.name.startswith(".") or e.name.lower() in SKIP_SCAN:
                    continue
                if e.name == "data" and os.path.isfile(os.path.join(e.path, "bdd_pubs.sqlite")):
                    consider(e.path)
                    continue
                if depth < max_depth:
                    stack.append((e.path, depth + 1))
    res = [c for c in found.values() if c["total"] > 0]
    res.sort(key=lambda c: (-c["total"], -c["date"]))
    LAST_SCAN.clear()
    LAST_SCAN.update(c["chemin"] for c in res)
    return res


def migrate_from(src):
    """Copie les données d'un ancien dossier vers l'emplacement fixe. L'ancien dossier n'est pas modifié
    (on y dépose seulement une note explicative)."""
    src = os.path.realpath(src)
    os.makedirs(DATA_DIR, exist_ok=True)
    if describe_data(DATA_DIR)["total"] > 0:  # ne jamais écraser des données sans copie de sécurité
        safety_copy("avant_reprise")
    with REG_LOCK:
        for name in DATA_ITEMS:
            _remove(os.path.join(DATA_DIR, name))
        for name in DATA_ITEMS:
            s_ = os.path.join(src, name)
            d_ = os.path.join(DATA_DIR, name)
            if name == "bdd_pubs.sqlite" and os.path.isfile(s_):
                a_, b_ = sqlite3.connect(s_), sqlite3.connect(d_)
                a_.backup(b_)
                b_.close()
                a_.close()
            elif os.path.isdir(s_):
                shutil.copytree(s_, d_)
            elif os.path.isfile(s_):
                shutil.copy2(s_, d_)
        for extra in ("reglages.json",):
            if os.path.isfile(os.path.join(src, extra)) and not os.path.isfile(os.path.join(DATA_DIR, extra)):
                shutil.copy2(os.path.join(src, extra), os.path.join(DATA_DIR, extra))
        OPENED.clear()
    save_settings(reprise={"source": src, "date": datetime.now().isoformat(timespec="seconds")})
    try:
        with open(os.path.join(src, "LISEZMOI - données reprises.txt"), "w", encoding="utf-8") as f:
            f.write(f"Le {datetime.now():%d/%m/%Y à %H:%M}, BDD Pubs a COPIÉ ces données vers :\n{DATA_DIR}\n\n"
                    "C'est là que l'application les utilise désormais. Ce dossier-ci n'est plus utilisé :\n"
                    "c'est une ancienne copie, que vous pouvez garder ou supprimer.\n")
    except OSError:
        pass
    print(f"Données reprises depuis {src}")


def auto_migrate(extra=()):
    """Au démarrage : si l'emplacement fixe est vide, reprendre les données d'une ancienne version."""
    if DATA_FIXED:
        return
    if os.path.isfile(os.path.join(DATA_DIR, "bdd_pubs.sqlite")) and describe_data(DATA_DIR)["total"] > 0:
        return
    try:
        cands = scan_for_data(extra=extra)
    except Exception:  # noqa: BLE001 - la recherche ne doit jamais empêcher le démarrage
        traceback.print_exc()
        return
    if cands:
        try:
            migrate_from(cands[0]["chemin"])
        except Exception:  # noqa: BLE001
            traceback.print_exc()


BACKUP_LOCK = threading.Lock()
BACKUP_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}h\d{2}$")
KEEP_BACKUPS = 30


def backup_dir():
    return load_settings().get("dossier_sauvegarde") or DEFAULT_BACKUP_DIR


def auto_backup():
    """Sauvegarde hors de l'application : bases de tous les projets (historique daté, 30 conservées)
    + copie des photos (seules les nouvelles sont copiées). Restaurable depuis l'application."""
    root = backup_dir()
    now = datetime.now()
    with BACKUP_LOCK:
        try:
            reg = load_registry()
            hist_root = os.path.join(root, "historique")
            name = now.strftime("%Y-%m-%d_%Hh%M")
            snap = os.path.join(hist_root, name)
            os.makedirs(snap, exist_ok=True)
            for pid, info in reg["projets"].items():
                p = project_by_id(pid)
                arc = info["dossier"]
                if os.path.exists(p.db_path):
                    dest = os.path.join(snap, arc) if arc else snap
                    os.makedirs(dest, exist_ok=True)
                    a_, b_ = sqlite3.connect(p.db_path, timeout=15), sqlite3.connect(os.path.join(dest, "bdd_pubs.sqlite"))
                    a_.backup(b_)
                    b_.close()
                    a_.close()
                for sub, folder in (("images", p.img_dir), ("miniatures", p.thumb_dir)):
                    if not os.path.isdir(folder):
                        continue
                    mirror = os.path.join(root, "photos", arc, sub) if arc else os.path.join(root, "photos", sub)
                    os.makedirs(mirror, exist_ok=True)
                    for f in os.listdir(folder):
                        src_f, dst_f = os.path.join(folder, f), os.path.join(mirror, f)
                        if not os.path.exists(dst_f) or os.path.getsize(dst_f) != os.path.getsize(src_f):
                            shutil.copy2(src_f, dst_f)
            with open(os.path.join(snap, "projets.json"), "w", encoding="utf-8") as f:
                json.dump(reg, f, ensure_ascii=False, indent=2)
            olds = sorted(d for d in os.listdir(hist_root) if BACKUP_NAME.match(d))
            for d in olds[:-KEEP_BACKUPS]:
                shutil.rmtree(os.path.join(hist_root, d), ignore_errors=True)
            with open(os.path.join(root, "LISEZMOI.txt"), "w", encoding="utf-8") as f:
                f.write("Sauvegardes automatiques de BDD Pubs (une par jour, les 30 dernières sont gardées).\n\n"
                        "- historique\\<date>\\ : la base de tous les projets à cette date\n"
                        "- photos\\ : toutes les photos (seules les nouvelles sont copiées à chaque fois)\n\n"
                        "Pour restaurer : application BDD Pubs > menu 📁 > Gérer les projets >\n"
                        "« Sauvegarde automatique » > Restaurer, à la date voulue.\n")
            state = {"date": now.isoformat(timespec="seconds"), "ok": True, "dossier": root, "nom": name}
        except Exception as e:  # noqa: BLE001 - clé USB débranchée, disque plein…
            traceback.print_exc()
            state = {"date": now.isoformat(timespec="seconds"), "ok": False, "dossier": root, "erreur": str(e)}
        save_settings(derniere_sauvegarde=state)
        return state


def backup_due():
    last = load_settings().get("derniere_sauvegarde") or {}
    try:
        when = datetime.fromisoformat(last.get("date", ""))
    except ValueError:
        return True
    age = (datetime.now() - when).total_seconds()
    if last.get("dossier") != backup_dir():
        return True
    return age > (3600 if not last.get("ok") else 20 * 3600)


def backup_loop():
    if STOP.wait(60):  # laisser l'application démarrer tranquillement
        return
    while True:
        try:
            if backup_due():
                auto_backup()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        if STOP.wait(1800):
            return


def list_auto_backups():
    hist_root = os.path.join(backup_dir(), "historique")
    out = []
    if os.path.isdir(hist_root):
        for d in sorted((d for d in os.listdir(hist_root) if BACKUP_NAME.match(d)), reverse=True):
            info = describe_data(os.path.join(hist_root, d))
            out.append({"nom": d, "date": f"{d[8:10]}/{d[5:7]}/{d[:4]} à {d[11:13]}h{d[14:16]}",
                        "jeux": info["jeux"], "pubs": info["pubs"], "parutions": info["parutions"],
                        "projets": info["projets"]})
    return out


def restore_auto_backup(name):
    if not BACKUP_NAME.match(name or ""):
        raise ApiError(400, "Sauvegarde inconnue")
    root = backup_dir()
    snap = os.path.join(root, "historique", name)
    try:
        with open(os.path.join(snap, "projets.json"), encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError):
        raise ApiError(404, "Sauvegarde introuvable ou incomplète")
    work = tempfile.mkdtemp(prefix="bddpubs_auto_")
    try:
        staging = os.path.join(work, "data")
        shutil.copytree(snap, staging)
        os.remove(os.path.join(staging, "projets.json"))
        with open(os.path.join(staging, "projets.json"), "w", encoding="utf-8") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        for pid, info in reg.get("projets", {}).items():
            arc = info.get("dossier", "")
            for sub in ("images", "miniatures"):
                mirror = os.path.join(root, "photos", arc, sub) if arc else os.path.join(root, "photos", sub)
                if os.path.isdir(mirror):
                    shutil.copytree(mirror, os.path.join(staging, arc, sub) if arc else os.path.join(staging, sub),
                                    dirs_exist_ok=True)
        return apply_restore(staging, reg)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def data_status():
    st = load_settings()
    return {"dossier_donnees": DATA_DIR, "reprise": st.get("reprise"), "contenu": describe_data(DATA_DIR),
            "sauvegarde": {"dossier": backup_dir(), "par_defaut": DEFAULT_BACKUP_DIR,
                           "derniere": st.get("derniere_sauvegarde"), "liste": list_auto_backups()}}


# ---------------------------------------------------------------------------
# Données de démonstration (python app.py --demo, uniquement si la base est vide)
# ---------------------------------------------------------------------------
def demo_poster(title, desc, platform, n):
    """Fausse affiche (SVG) pour illustrer le projet de démonstration."""
    from xml.sax.saxutils import escape
    bg = ["#1d3557", "#6a040f", "#1b4332", "#3c096c", "#7f5539"][n % 5]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" width="600" height="800">
<rect width="600" height="800" fill="{bg}"/>
<circle cx="480" cy="170" r="210" fill="#ffffff" opacity=".08"/>
<circle cx="90" cy="640" r="160" fill="#ffffff" opacity=".06"/>
<rect x="40" y="40" width="160" height="44" rx="8" fill="#ffffff" opacity=".9"/>
<text x="120" y="70" font-family="sans-serif" font-size="22" font-weight="700" fill="{bg}" text-anchor="middle">DÉMO</text>
<text x="300" y="420" font-family="sans-serif" font-size="46" font-weight="800" fill="#ffffff" text-anchor="middle">{escape(title)}</text>
<text x="300" y="480" font-family="sans-serif" font-size="26" fill="#ffffff" opacity=".85" text-anchor="middle">{escape(desc)}</text>
<rect x="0" y="700" width="600" height="100" fill="#000000" opacity=".35"/>
<text x="300" y="762" font-family="sans-serif" font-size="30" font-weight="700" fill="#ffffff" text-anchor="middle">{escape(platform)}</text>
</svg>"""


def load_demo():
    db = connect()
    if db.execute("SELECT COUNT(*) FROM games").fetchone()[0]:
        print("Base non vide : données de démo non chargées.")
        return
    with db:
        pid = {r["name"]: r["id"] for r in db.execute("SELECT id, name FROM platforms")}
        sid = {}
        for s in ("Final Fantasy", "Dragon Quest", "Biohazard", "Sakura Taisen"):
            sid[s] = db.execute("INSERT INTO series(name) VALUES (?)", (s,)).lastrowid
        mid = {}
        for n, pub, fr in (("Weekly Famitsu", "ASCII / Enterbrain", "Hebdomadaire"),
                           ("Dengeki PlayStation", "MediaWorks", ""),
                           ("Sega Saturn Magazine", "SoftBank", "")):
            mid[n] = db.execute("INSERT INTO magazines(name, publisher, frequency, notes) VALUES (?,?,?,?)",
                                (n, pub, fr, "DÉMO")).lastrowid
        gid = {}
        for t, o, s, p, y in (("Final Fantasy VII", "ファイナルファンタジーVII", "Final Fantasy", "Square", 1997),
                              ("Biohazard 2", "バイオハザード2", "Biohazard", "Capcom", 1998),
                              ("Sakura Taisen", "サクラ大戦", "Sakura Taisen", "Sega", 1996),
                              ("Dragon Quest VII", "ドラゴンクエストVII エデンの戦士たち", "Dragon Quest", "Enix", 2000)):
            gid[t] = db.execute("INSERT INTO games(title, original_title, series_id, publisher, year, notes) "
                                "VALUES (?,?,?,?,?,?)", (t, o, sid[s], p, y, "DÉMO")).lastrowid
        aid = []
        for g, p, d, n in (("Final Fantasy VII", "PlayStation", "Cloud devant Midgar", 2),
                           ("Final Fantasy VII", "PlayStation", "Aerith, fond fleurs", 1),
                           ("Biohazard 2", "PlayStation", "Leon & Claire", 2),
                           ("Sakura Taisen", "Sega Saturn", "Sakura au sabre", 1),
                           ("Dragon Quest VII", "PlayStation", "Logo + illustration", 2)):
            ad = db.execute("INSERT INTO ads(game_id, description, pages, notes) VALUES (?,?,?,?)",
                            (gid[g], d, n, "DÉMO")).lastrowid
            set_ad_platforms(db, ad, [pid[x] for x in p.split("|")])
            fname = f"ads{ad}_demo.svg"
            with open(os.path.join(cur().img_dir, fname), "w", encoding="utf-8") as f:
                f.write(demo_poster(g, d, p.replace("|", " / "), len(aid)))
            db.execute("INSERT INTO images(entity, entity_id, file, original_name) VALUES ('ads', ?, ?, ?)",
                       (ad, fname, "affiche de démonstration"))
            aid.append(ad)
        for m, num, date, page, ad, sale in (
                ("Weekly Famitsu", "421", "1997-01-03", "12", 0, 1),
                ("Weekly Famitsu", "421", "1997-01-03", "40", 3, 0),
                ("Weekly Famitsu", "425", "1997-01-31", "8", 0, 0),
                ("Weekly Famitsu", "430", "1997-03-07", "2", 1, 1),
                ("Dengeki PlayStation", "38", "1997-01-10", "2", 0, 1),
                ("Dengeki PlayStation", "38", "1997-01-10", "100", 2, 0),
                ("Sega Saturn Magazine", "5", "1996-09", "表4", 3, 1),
                ("Weekly Famitsu", "600", "", "4", 4, 0)):
            iid = ensure_issue(db, mid[m], num, date)
            db.execute("INSERT INTO appearances(ad_id, issue_id, page, for_sale, notes) VALUES (?,?,?,?,?)",
                       (aid[ad], iid, page, sale, "DÉMO"))
    print("Données de démonstration chargées.")


# ---------------------------------------------------------------------------
# Serveur HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "BDDPubs/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if os.environ.get("BDD_PUBS_DEBUG"):
            super().log_message(fmt, *args)

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def do_DELETE(self):
        self.dispatch("DELETE")

    # -- réponses ------------------------------------------------------------
    def send_bytes(self, data, ctype, status=200, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, obj, status=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8", status)

    def send_file(self, path, ctype=None, cache=True, download_name=None):
        if not os.path.isfile(path):
            raise ApiError(404, "Fichier introuvable")
        ctype = ctype or CONTENT_TYPES.get(path.rsplit(".", 1)[-1].lower(), "application/octet-stream")
        size = os.path.getsize(path)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "max-age=31536000, immutable" if cache else "no-store")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def read_json(self):
        self._consumed = True
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ApiError(413, "Fichier trop volumineux (60 Mo max)")
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "Requête invalide")

    # -- routage -------------------------------------------------------------
    def dispatch(self, method):
        self._consumed = False
        try:
            self._dispatch(method)
        finally:
            # Contenu de requête non lu : il resterait dans la connexion et fausserait la requête
            # suivante (connexions réutilisées). On ferme alors la connexion proprement.
            if not self._consumed and int(self.headers.get("Content-Length") or 0) > 0:
                self.close_connection = True

    def _dispatch(self, method):
        url = urlparse(self.path)
        path = unquote(url.path)
        qs = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        try:
            if path.startswith("/api/"):
                self.api(method, path[5:].strip("/"), qs)
            elif method == "GET":
                self.static(path)
            else:
                raise ApiError(405, "Méthode non autorisée")
        except ApiError as e:
            if path.startswith("/api/") or e.status != 404:
                self.send_json({"error": e.msg}, e.status)
            else:
                self.send_bytes(e.msg.encode("utf-8"), "text/plain; charset=utf-8", e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send_json({"error": f"Erreur interne : {e}"}, 500)

    def static(self, path):
        m = re.match(r"^/p/([a-z0-9-]+)(/.*)?$", path)
        if m:
            pid, path = m.group(1), m.group(2) or "/"
            if path.startswith("/images/") or path.startswith("/miniatures/"):
                p = open_project(pid)
                folder = p.img_dir if path.startswith("/images/") else p.thumb_dir
                name = path.split("/", 2)[2]
                if not SAFE_NAME.match(name):
                    raise ApiError(404, "Fichier introuvable")
                return self.send_file(os.path.join(folder, name))
        if path in ("/", ""):
            path = "/index.html"
        name = path.lstrip("/")
        if not SAFE_NAME.match(name):
            raise ApiError(404, "Fichier introuvable")
        ctype = {"js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8",
                 "html": "text/html; charset=utf-8", "svg": "image/svg+xml"}.get(name.rsplit(".", 1)[-1])
        self.send_file(os.path.join(STATIC_DIR, name), ctype, cache=False)

    def api(self, method, route, qs):
        parts = route.split("/")
        pid = self.headers.get("X-Projet") or qs.get("projet") or None
        if parts[0] == "donnees":
            use_project(project_by_id(None))
            return self.api_data(method, parts)
        if parts[0] == "projets":
            try:
                use_project(project_by_id(pid))
            except ApiError:  # onglet resté sur un projet supprimé
                use_project(project_by_id(None))
            return self.api_projects(method, parts, qs)
        open_project(pid)
        db = connect()
        try:
            self.api_inner(db, method, parts, qs)
        except sqlite3.IntegrityError as e:
            table = parts[0] if parts[0] in SPEC else ""
            raise ApiError(409, friendly_integrity(table, e))
        finally:
            db.close()

    def api_data(self, method, parts):
        """Emplacement des données, sauvegarde automatique, reprise d'anciennes données."""
        action = parts[1] if len(parts) > 1 else ""
        if method == "GET" and not action:
            return self.send_json(data_status())
        if method == "POST" and action == "sauvegarder":
            state = auto_backup()
            if not state.get("ok"):
                raise ApiError(500, f"Sauvegarde impossible dans « {state['dossier']} » : {state.get('erreur')}")
            return self.send_json(data_status())
        if method == "PUT" and action == "dossier":
            path = str(self.read_json().get("dossier") or "").strip().strip('"')
            if path:
                if not os.path.isabs(path):
                    raise ApiError(400, "Indiquez un chemin complet, par ex. E:\\Sauvegardes BDD Pubs")
                try:
                    os.makedirs(path, exist_ok=True)
                    test = os.path.join(path, ".test_ecriture")
                    with open(test, "w") as f:
                        f.write("ok")
                    os.remove(test)
                except OSError as e:
                    raise ApiError(400, f"Impossible d'écrire dans ce dossier : {e}")
            save_settings(dossier_sauvegarde=path or None)
            return self.send_json(data_status())
        if method == "POST" and action == "restaurer":
            return self.send_json(restore_auto_backup(self.read_json().get("nom")))
        if method == "GET" and action == "recherche":
            return self.send_json({"resultats": scan_for_data(max_depth=4)})
        if method == "POST" and action == "reprendre":
            path = os.path.realpath(str(self.read_json().get("chemin") or ""))
            if path not in LAST_SCAN:
                raise ApiError(400, "Dossier inconnu : relancez la recherche.")
            migrate_from(path)
            open_project(None)
            return self.send_json(data_status())
        raise ApiError(405, "Méthode non autorisée")

    def api_projects(self, method, parts, qs):
        current = cur().id
        target = parts[1] if len(parts) > 1 and parts[1] else None
        if method == "GET" and not target:
            return self.send_json(projects_info(current))
        if method == "POST" and not target:
            body = self.read_json()
            p = create_project(body.get("nom"), demo=bool(body.get("demo")))
            return self.send_json({"id": p.id, "nom": p.name}, 201)
        if method == "GET" and target == "tout.zip":
            tmpdir = tempfile.mkdtemp(prefix="bddpubs_")
            try:
                zpath = os.path.join(tmpdir, "tout.zip")
                export_all(zpath)
                stamp = datetime.now().strftime("%Y%m%d-%H%M")
                return self.send_file(zpath, "application/zip", cache=False,
                                      download_name=f"bdd_pubs_TOUT_{stamp}.zip")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        if method == "POST" and target == "restaurer":
            n = int(self.headers.get("Content-Length") or 0)
            self._consumed = True
            return self.send_json(restore_all(self.rfile, n))
        if method == "POST" and target == "import":
            n = int(self.headers.get("Content-Length") or 0)
            self._consumed = True
            p = import_project(self.rfile, n, qs.get("nom", ""))
            return self.send_json({"id": p.id, "nom": p.name}, 201)
        if target and method == "GET" and len(parts) == 3 and parts[2] == "export.zip":
            p = open_project(target)
            tmpdir, zpath = build_backup()
            try:
                stamp = datetime.now().strftime("%Y%m%d-%H%M")
                return self.send_file(zpath, "application/zip", cache=False,
                                      download_name=f"bdd_pubs_{p.id}_{stamp}.zip")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
        if target and method == "PUT":
            body = self.read_json()
            with REG_LOCK:
                reg = load_registry()
                if target not in reg["projets"]:
                    raise ApiError(404, "Projet introuvable")
                if "nom" in body:
                    nom = str(body["nom"]).strip()
                    if not nom:
                        raise ApiError(400, "Donnez un nom au projet")
                    if any(k != target and v["nom"].lower() == nom.lower() for k, v in reg["projets"].items()):
                        raise ApiError(409, "Un projet porte déjà ce nom.")
                    reg["projets"][target]["nom"] = nom
                if body.get("defaut"):
                    reg["defaut"] = target
                save_registry(reg)
            return self.send_json(projects_info(current))
        if target and method == "DELETE":
            delete_project(target)
            return self.send_json({"ok": True})
        raise ApiError(405, "Méthode non autorisée")

    def api_inner(self, db, method, parts, qs):
        head = parts[0]
        rid = None
        if len(parts) > 1 and parts[1].isdigit():
            rid = int(parts[1])

        if head == "ping":
            if method == "POST":
                PRESENCE.ping(self.read_json().get("tab", "?"))
            return self.send_json({"app": "bdd_pubs", "ok": True, "version": APP_VERSION, "build": BUILD,
                                   "data": os.path.realpath(DATA_DIR)})
        if head == "bye" and method == "POST":
            PRESENCE.bye(self.read_json().get("tab", "?"))
            return self.send_json({"ok": True})
        if head == "quitter" and method == "POST":
            self.send_json({"ok": True})
            STOP.set()
            return
        if head == "reseau":
            if method == "POST":
                on = bool(self.read_json().get("actif"))
                if on:
                    NETWORK.enable()
                else:
                    NETWORK.disable()
                save_settings(reseau=on)
            return self.send_json(NETWORK.status())
        if method == "GET" and head == "meta":
            return self.send_json({"platforms": list_platforms(db, {}), "series": list_series(db, {}),
                                   "magazines": list_magazines(db, {})})
        if method == "GET" and head == "dashboard":
            return self.send_json(dashboard(db))
        if method == "GET" and head == "search":
            limit = int(qs.get("limit") or 200)
            offset = int(qs.get("offset") or 0)
            return self.send_json(search(db, qs, limit=limit, offset=offset))
        if method == "GET" and head == "export" and len(parts) == 2 and parts[1].endswith(".csv"):
            name = parts[1][:-4]
            data = export_csv(db, name, qs)
            stamp = datetime.now().strftime("%Y%m%d")
            return self.send_bytes(data, "text/csv; charset=utf-8", headers={
                "Content-Disposition": f'attachment; filename="bdd_pubs_{name}_{stamp}.csv"'})
        if method == "GET" and head == "sauvegarde.zip":
            tmpdir, zpath = build_backup()
            try:
                stamp = datetime.now().strftime("%Y%m%d-%H%M")
                return self.send_file(zpath, "application/zip", cache=False,
                                      download_name=f"bdd_pubs_sauvegarde_{stamp}.zip")
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

        if head == "images":
            if method == "POST" and rid is None:
                body = self.read_json()
                with db:
                    return self.send_json(save_image(db, body), 201)
            im = one(db.execute("SELECT * FROM images WHERE id = ?", (rid,))) if rid else None
            if not im:
                raise ApiError(404, "Image introuvable")
            if method == "DELETE":
                with db:
                    db.execute("DELETE FROM images WHERE id = ?", (rid,))
                remove_image_files(im)
                return self.send_json({"ok": True})
            if method == "PUT":
                body = self.read_json()
                with db:
                    if body.get("principale"):
                        db.execute("UPDATE images SET sort = (SELECT MIN(sort) - 1 FROM images "
                                   "WHERE entity = ? AND entity_id = ?) WHERE id = ?",
                                   (im["entity"], im["entity_id"], rid))
                    if "caption" in body:
                        db.execute("UPDATE images SET caption = ? WHERE id = ?",
                                   (str(body["caption"]).strip(), rid))
                return self.send_json(one(db.execute("SELECT * FROM images WHERE id = ?", (rid,))))
            raise ApiError(405, "Méthode non autorisée")

        if head == "issues" and len(parts) == 2 and parts[1] == "ensure" and method == "POST":
            body = self.read_json()
            with db:
                iid = ensure_issue(db, body.get("magazine_id"), body.get("number"), body.get("date") or "")
            return self.send_json(detail(db, "issues", iid))

        if head not in SPEC:
            raise ApiError(404, "Route inconnue")

        if method == "GET":
            if rid is None:
                if head == "appearances":
                    return self.send_json(search(db, qs)["items"])
                return self.send_json(LISTERS[head](db, qs))
            d = detail(db, head, rid)
            if d is None:
                raise ApiError(404, "Élément introuvable")
            return self.send_json(d)

        if method == "POST" and rid is None:
            body = self.read_json()
            with db:
                if head == "appearances" and not body.get("issue_id"):
                    body["issue_id"] = ensure_issue(db, body.get("magazine_id"), body.get("issue_number"),
                                                    body.get("issue_date") or "")
                data = clean(head, body)
                cols = ", ".join(data)
                marks = ", ".join("?" for _ in data)
                new_id = db.execute(f"INSERT INTO {head} ({cols}) VALUES ({marks})",
                                    list(data.values())).lastrowid
                if head == "ads":
                    set_ad_platforms(db, new_id, body.get("platform_ids", []))
            return self.send_json(detail(db, head, new_id), 201)

        if method == "PUT" and rid is not None:
            body = self.read_json()
            with db:
                if head == "appearances" and body.get("magazine_id") and body.get("issue_number"):
                    body["issue_id"] = ensure_issue(db, body.get("magazine_id"), body.get("issue_number"),
                                                    body.get("issue_date") or "")
                data = clean(head, body, partial=True)
                if data:
                    sets = ", ".join(f"{k} = ?" for k in data)
                    cur = db.execute(f"UPDATE {head} SET {sets} WHERE id = ?", list(data.values()) + [rid])
                    if cur.rowcount == 0:
                        raise ApiError(404, "Élément introuvable")
                if head == "ads":
                    set_ad_platforms(db, rid, body.get("platform_ids"))
            return self.send_json(detail(db, head, rid))

        if method == "DELETE" and rid is not None:
            with db:
                check = DELETE_CHECKS.get(head)
                if check:
                    n = db.execute(check[0], (rid,)).fetchone()[0]
                    if n:
                        raise ApiError(409, check[1].format(n=n))
                cur = db.execute(f"DELETE FROM {head} WHERE id = ?", (rid,))
                if cur.rowcount == 0:
                    raise ApiError(404, "Élément introuvable")
                if head in IMAGE_ENTITIES:
                    delete_images(db, head, rid)
            return self.send_json({"ok": True})

        raise ApiError(405, "Méthode non autorisée")


# ---------------------------------------------------------------------------
# Arrêt automatique : l'onglet envoie un signe de vie toutes les 20 s ;
# quand plus aucun onglet n'est ouvert, le serveur s'arrête tout seul.
# ---------------------------------------------------------------------------
class Presence:
    IDLE = 150   # s sans aucun signe de vie (onglet en arrière-plan : le navigateur ralentit ses envois)
    GRACE = 12   # s après la fermeture du dernier onglet (laisse le temps d'un rechargement de page)

    def __init__(self):
        self.lock = threading.Lock()
        self.tabs = {}
        self.last_seen = time.monotonic()
        self.closed_at = None

    def ping(self, tab):
        with self.lock:
            now = time.monotonic()
            self.tabs[str(tab)] = now
            self.last_seen = now
            self.closed_at = None

    def bye(self, tab):
        with self.lock:
            self.tabs.pop(str(tab), None)
            if not self.tabs:
                self.closed_at = time.monotonic()

    def reset(self):
        """Après une mise en veille de l'ordinateur : on laisse aux onglets le temps de se manifester."""
        with self.lock:
            now = time.monotonic()
            self.tabs = {k: now for k in self.tabs}
            self.last_seen = now
            if self.closed_at is not None:
                self.closed_at = now

    def should_stop(self):
        with self.lock:
            now = time.monotonic()
            self.tabs = {k: t for k, t in self.tabs.items() if now - t < self.IDLE}
            if self.tabs:
                return False
            if self.closed_at is not None and now - self.closed_at > self.GRACE:
                return True
            return now - self.last_seen > self.IDLE


PRESENCE = Presence()
STOP = threading.Event()


def load_settings():
    try:
        with open(os.path.join(DATA_DIR, "reglages.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(**changes):
    data = load_settings()
    data.update(changes)
    with open(os.path.join(DATA_DIR, "reglages.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Network:
    """Accès depuis le téléphone : 2e écoute sur l'adresse de l'ordinateur dans le réseau local."""

    def __init__(self):
        self.lock = threading.Lock()
        self.httpd = None
        self.port = None
        self.always = False  # lancé avec --reseau : déjà accessible partout

    def status(self):
        ip = lan_ip()
        return {"actif": self.always or self.httpd is not None,
                "force": self.always,
                "url": f"http://{ip}:{self.port}" if ip else None}

    def enable(self):
        with self.lock:
            if self.always or self.httpd:
                return
            ip = lan_ip()
            if not ip:
                raise ApiError(409, "Aucun réseau local détecté (l'ordinateur est-il connecté au Wi-Fi ?)")
            try:
                srv = Server((ip, self.port), Handler)
            except OSError as e:
                raise ApiError(409, f"Impossible d'ouvrir l'accès réseau : {e}")
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            self.httpd = srv

    def disable(self):
        with self.lock:
            srv, self.httpd = self.httpd, None
        if srv:
            srv.shutdown()
            srv.server_close()


NETWORK = Network()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # Sous Windows, SO_REUSEADDR permettrait d'occuper un port déjà pris par un autre programme
    allow_reuse_address = sys.platform != "win32"


def watchdog(httpd, auto_stop):
    prev = time.monotonic()
    while not STOP.wait(3):
        now = time.monotonic()
        if now - prev > 30:  # l'ordinateur sortait de veille
            PRESENCE.reset()
        prev = now
        if auto_stop and PRESENCE.should_stop():
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Plus aucun onglet ouvert : arrêt.")
            break
    httpd.shutdown()


def running_instance(port):
    """Infos de l'application BDD Pubs qui tourne déjà sur ce port (ou None)."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1.5) as r:
            info = json.loads(r.read().decode("utf-8"))
            return info if info.get("app") == "bdd_pubs" else None
    except Exception:  # noqa: BLE001
        return None


def ask_to_quit(port):
    """Demande à une autre version de l'appli de s'arrêter ; attend que le port se libère."""
    import urllib.request
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/quitter", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:  # noqa: BLE001
        return False
    for _ in range(40):
        time.sleep(0.25)
        if running_instance(port) is None:
            return True
    return False


def lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="BDD Pubs : application locale")
    ap.add_argument("--port", type=int, default=int(os.environ.get("BDD_PUBS_PORT", 8765)))
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    ap.add_argument("--reseau", action="store_true",
                    help="accessible depuis les autres appareils du réseau local (téléphone...)")
    ap.add_argument("--arret-auto", action="store_true",
                    help="s'arrêter quand plus aucun onglet n'est ouvert (par défaut : seulement avec « Quitter »)")
    ap.add_argument("--sans-arret-auto", action="store_true", help=argparse.SUPPRESS)  # ancien réglage, sans effet
    ap.add_argument("--demo", action="store_true", help="charger des données d'exemple si la base est vide")
    args = ap.parse_args(argv)

    os.makedirs(DATA_DIR, exist_ok=True)
    if sys.stdout is None or sys.stderr is None:
        # Lancé sans fenêtre (BDD Pubs.pyw / BDD Pubs.exe) : messages dans data/journal.txt
        log = open(os.path.join(DATA_DIR, "journal.txt"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log

    # Déjà lancée ? Même version : on rouvre simplement l'onglet.
    # Autre version (mise à jour) ou autre dossier : on lui demande de s'arrêter et on prend sa place.
    port = None
    previous_data = []  # dossier de données d'une ancienne version encore lancée
    for p in range(args.port, args.port + 10):
        other = running_instance(p)
        if other:
            previous_data.append(other.get("data"))
            same = other.get("build") == BUILD and other.get("data") == os.path.realpath(DATA_DIR)
            if same:
                print(f"BDD Pubs tourne déjà sur le port {p} : ouverture du navigateur.")
                if not args.no_browser:
                    webbrowser.open(f"http://localhost:{p}")
                return
            print(f"Une autre version de BDD Pubs tourne sur le port {p} : arrêt de celle-ci.")
            if not ask_to_quit(p):
                continue
        try:
            httpd = Server(("0.0.0.0" if args.reseau else "127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if port is None:
        print(f"Aucun port libre entre {args.port} et {args.port + 9}.")
        sys.exit(1)

    # Données d'une ancienne version (à côté du programme, ou celle qui tournait) : reprises
    # automatiquement si l'emplacement fixe est encore vide.
    auto_migrate(extra=previous_data)
    open_project(None)
    if args.demo:
        load_demo()

    url = f"http://localhost:{port}"
    # Par défaut l'application reste lancée jusqu'au bouton « Quitter » (ou l'arrêt du PC) :
    # un onglet en arrière-plan est mis en sommeil par le navigateur, ce n'est pas un signe de fermeture.
    auto_stop = args.arret_auto and not args.no_browser
    print("=" * 60)
    print(f"  BDD Pubs est lancée : {url}")
    if args.reseau and lan_ip():
        print(f"  Depuis un téléphone (même Wi-Fi) : http://{lan_ip()}:{port}")
    print(f"  Données : {DATA_DIR}")
    print(f"  Sauvegarde automatique : {backup_dir()}")
    if auto_stop:
        print("  S'arrête toute seule quand on ferme le dernier onglet.")
    else:
        print("  Pour arrêter : bouton « Quitter » dans l'application (ou Ctrl+C ici)")
    print("=" * 60)
    NETWORK.port, NETWORK.always = port, args.reseau
    if load_settings().get("reseau") and not args.reseau:
        try:
            NETWORK.enable()
            print(f"  Accès téléphone activé : {NETWORK.status()['url']}")
        except ApiError as e:
            print(f"  Accès téléphone non activé : {e.msg}")
    threading.Thread(target=watchdog, args=(httpd, auto_stop), daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        STOP.set()
        NETWORK.disable()
        httpd.server_close()


if __name__ == "__main__":
    main()
