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
import mimetypes
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import traceback
import uuid
import webbrowser
import zipfile
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
DATA_DIR = os.environ.get("BDD_PUBS_DATA", os.path.join(HERE, "data"))
IMG_DIR = os.path.join(DATA_DIR, "images")
THUMB_DIR = os.path.join(DATA_DIR, "miniatures")
BACKUP_DIR = os.path.join(DATA_DIR, "sauvegardes")
DB_PATH = os.path.join(DATA_DIR, "bdd_pubs.sqlite")

MAX_UPLOAD = 60 * 1024 * 1024
IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "avif", "heic"}
IMAGE_ENTITIES = {"ads", "appearances", "issues", "games"}
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
MIGRATIONS = [SCHEMA_V1]

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
    ("PC (Windows)", ""), ("Arcade", ""), ("Multi-plateformes", ""),
]


def connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    for d in (DATA_DIR, IMG_DIR, THUMB_DIR, BACKUP_DIR):
        os.makedirs(d, exist_ok=True)
    fresh = not os.path.exists(DB_PATH)
    if not fresh:
        backup_on_start()
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


def backup_on_start(keep=15):
    """Copie de sécurité de la base à chaque lancement (garde les 15 dernières)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_DIR, f"bdd_pubs_{stamp}.sqlite")
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(dest)
    src.backup(dst)
    dst.close()
    src.close()
    old = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith("bdd_pubs_") and f.endswith(".sqlite"))
    for f in old[:-keep]:
        os.remove(os.path.join(BACKUP_DIR, f))


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def one(cur):
    r = cur.fetchone()
    return dict(r) if r else None


def img_url(entity, id_expr):
    """Sous-requête : URL de l'image principale d'un élément."""
    return (f"(SELECT CASE WHEN im.thumb IS NOT NULL THEN '/miniatures/' || im.thumb "
            f"ELSE '/images/' || im.file END FROM images im "
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
    "ads": {"game_id": ("fk", True), "platform_id": ("fk", False), "description": ("text", False),
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
LEFT JOIN platforms p ON p.id = a.platform_id
LEFT JOIN series s ON s.id = g.series_id
"""

NUM_ORDER = "CAST({0} AS INTEGER), {0}"


def list_platforms(db, qs):
    return rows(db.execute("""
        SELECT p.*,
          (SELECT COUNT(*) FROM ads a WHERE a.platform_id = p.id) AS ads_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             WHERE a.platform_id = p.id) AS app_count
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
    return rows(db.execute(f"""
        SELECT g.*, s.name AS series_name,
          (SELECT COUNT(*) FROM ads a WHERE a.game_id = g.id) AS ads_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             WHERE a.game_id = g.id) AS app_count,
          (SELECT COUNT(*) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             WHERE a.game_id = g.id AND ap.for_sale = 1) AS sale_count,
          (SELECT MIN(NULLIF(i.date, '')) FROM appearances ap JOIN ads a ON a.id = ap.ad_id
             JOIN issues i ON i.id = ap.issue_id WHERE a.game_id = g.id) AS first_date,
          COALESCE({img_url('games', 'g.id')},
            (SELECT CASE WHEN im.thumb IS NOT NULL THEN '/miniatures/' || im.thumb
                    ELSE '/images/' || im.file END
             FROM images im JOIN ads a ON im.entity = 'ads' AND im.entity_id = a.id
             WHERE a.game_id = g.id ORDER BY im.sort, im.id LIMIT 1)) AS thumb_url
        FROM games g LEFT JOIN series s ON s.id = g.series_id {w}
        ORDER BY g.title COLLATE NOCASE, g.year""", params))


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
    for key, col in (("game_id", "a.game_id"), ("platform_id", "a.platform_id"),
                     ("series_id", "g.series_id")):
        if qs.get(key):
            where.append(f"{col} = ?")
            params.append(qs[key])
    if qs.get("sans_image") == "1":
        where.append("NOT EXISTS (SELECT 1 FROM images im WHERE im.entity = 'ads' AND im.entity_id = a.id)")
    w = ("WHERE " + " AND ".join(where)) if where else ""
    order = "a.id DESC" if qs.get("tri") == "recent" else "g.title COLLATE NOCASE, a.id"
    return rows(db.execute(f"""
        SELECT a.*, g.title AS game_title, g.original_title, g.series_id,
          p.name AS platform_name, s.name AS series_name,
          (SELECT COUNT(*) FROM appearances ap WHERE ap.ad_id = a.id) AS app_count,
          (SELECT COUNT(*) FROM appearances ap WHERE ap.ad_id = a.id AND ap.for_sale = 1) AS sale_count,
          (SELECT COUNT(*) FROM images im WHERE im.entity = 'ads' AND im.entity_id = a.id) AS img_count,
          (SELECT MIN(NULLIF(i.date, '')) FROM appearances ap JOIN issues i ON i.id = ap.issue_id
             WHERE ap.ad_id = a.id) AS first_date,
          {img_url('ads', 'a.id')} AS thumb_url
        FROM ads a JOIN games g ON g.id = a.game_id
        LEFT JOIN platforms p ON p.id = a.platform_id
        LEFT JOIN series s ON s.id = g.series_id {w}
        ORDER BY {order}""", params))


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
    eq("platform_id", "a.platform_id")
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
          g.id AS game_id, g.title AS game, g.original_title, p.id AS platform_id, p.name AS platform,
          s.id AS series_id, s.name AS series, a.description, a.pages,
          COALESCE({img_url('appearances', 'ap.id')}, {img_url('ads', 'a.id')}) AS thumb_url
        {APP_JOIN} {w} ORDER BY {order} {lim}""", params))
    st = one(db.execute(f"""
        SELECT COUNT(*) AS total, COUNT(DISTINCT ap.ad_id) AS ads, COUNT(DISTINCT a.game_id) AS games,
          COUNT(DISTINCT ap.issue_id) AS issues, COUNT(DISTINCT i.magazine_id) AS magazines,
          COALESCE(SUM(ap.for_sale), 0) AS for_sale, COALESCE(SUM(a.pages), 0) AS pages
        {APP_JOIN} {w}""", params))
    return {"items": items, "stats": st}


def images_of(db, entity, eid):
    return rows(db.execute(
        "SELECT * FROM images WHERE entity = ? AND entity_id = ? ORDER BY sort, id", (entity, eid)))


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
    for folder, name in ((IMG_DIR, im["file"]), (THUMB_DIR, im["thumb"])):
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
    with open(os.path.join(IMG_DIR, fname), "wb") as f:
        f.write(data)
    tname = None
    if thumb:
        tname = f"{stem}.jpg"
        with open(os.path.join(THUMB_DIR, tname), "wb") as f:
            f.write(thumb)
    sort = db.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM images WHERE entity = ? AND entity_id = ?",
                      (entity, eid)).fetchone()[0]
    iid = db.execute(
        "INSERT INTO images(entity, entity_id, file, thumb, original_name, caption, sort) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entity, eid, fname, tname, name, str(body.get("caption") or ""), sort)).lastrowid
    return one(db.execute("SELECT * FROM images WHERE id = ?", (iid,)))


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
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(snap)
    src.backup(dst)
    dst.close()
    src.close()
    zpath = os.path.join(tmpdir, "sauvegarde.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(snap, "data/bdd_pubs.sqlite")
        for folder, arc in ((IMG_DIR, "data/images"), (THUMB_DIR, "data/miniatures")):
            for f in os.listdir(folder):
                z.write(os.path.join(folder, f), f"{arc}/{f}", compress_type=zipfile.ZIP_STORED)
    return tmpdir, zpath


# ---------------------------------------------------------------------------
# Données de démonstration (python app.py --demo, uniquement si la base est vide)
# ---------------------------------------------------------------------------
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
            aid.append(db.execute("INSERT INTO ads(game_id, platform_id, description, pages, notes) "
                                  "VALUES (?,?,?,?,?)", (gid[g], pid[p], d, n, "DÉMO")).lastrowid)
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
        ctype = ctype or mimetypes.guess_type(path)[0] or "application/octet-stream"
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
        if path.startswith("/images/") or path.startswith("/miniatures/"):
            folder = IMG_DIR if path.startswith("/images/") else THUMB_DIR
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
        db = connect()
        try:
            self.api_inner(db, method, parts, qs)
        except sqlite3.IntegrityError as e:
            table = parts[0] if parts[0] in SPEC else ""
            raise ApiError(409, friendly_integrity(table, e))
        finally:
            db.close()

    def api_inner(self, db, method, parts, qs):
        head = parts[0]
        rid = None
        if len(parts) > 1 and parts[1].isdigit():
            rid = int(parts[1])

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


def main():
    ap = argparse.ArgumentParser(description="BDD Pubs : application locale")
    ap.add_argument("--port", type=int, default=int(os.environ.get("BDD_PUBS_PORT", 8765)))
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    ap.add_argument("--reseau", action="store_true",
                    help="accessible depuis les autres appareils du réseau local (téléphone...)")
    ap.add_argument("--demo", action="store_true", help="charger des données d'exemple si la base est vide")
    args = ap.parse_args()

    init_db()
    if args.demo:
        load_demo()

    host = "0.0.0.0" if args.reseau else "127.0.0.1"
    try:
        httpd = ThreadingHTTPServer((host, args.port), Handler)
    except OSError:
        print(f"Le port {args.port} est déjà utilisé : l'application tourne peut-être déjà.")
        print(f"Ouvrez http://localhost:{args.port} ou relancez avec --port 8766")
        if not args.no_browser:
            webbrowser.open(f"http://localhost:{args.port}")
        sys.exit(1)
    httpd.daemon_threads = True
    url = f"http://localhost:{args.port}"
    print("=" * 60)
    print(f"  BDD Pubs est lancée : {url}")
    if args.reseau:
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.0.2.1", 80))
            print(f"  Depuis un téléphone (même Wi-Fi) : http://{s.getsockname()[0]}:{args.port}")
            s.close()
        except OSError:
            pass
    print(f"  Données : {DATA_DIR}")
    print("  Pour arrêter : fermer cette fenêtre (ou Ctrl+C)")
    print("=" * 60)
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
