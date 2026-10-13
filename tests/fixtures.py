"""Crée les fichiers de test (images PNG unies, classeur Excel .xlsx, CSV) sans dépendance."""
import os
import struct
import sys
import zipfile
import zlib
from xml.sax.saxutils import escape


def png(path, w, h, color):
    raw = b"".join(b"\x00" + bytes(color) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def xlsx(path, sheets):
    """Classeur .xlsx minimal : textes en « chaînes partagées » (dont une avec lecture furigana,
    comme dans les fichiers Excel japonais), nombres en valeurs numériques."""
    shared, idx = [], {}

    def sid(t):
        if t not in idx:
            idx[t] = len(shared)
            shared.append(t)
        return idx[t]

    def col(n):
        s = ""
        n += 1
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    sheet_xml = []
    for _name, rows in sheets:
        out = []
        for i, row in enumerate(rows, 1):
            cells = []
            for j, v in enumerate(row):
                ref = f"{col(j)}{i}"
                if isinstance(v, (int, float)):
                    cells.append(f'<c r="{ref}"><v>{v}</v></c>')
                elif v != "":
                    cells.append(f'<c r="{ref}" t="s"><v>{sid(v)}</v></c>')
            out.append(f'<row r="{i}">{"".join(cells)}</row>')
        sheet_xml.append('<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/'
                         f'spreadsheetml/2006/main"><sheetData>{"".join(out)}</sheetData></worksheet>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'

    def si(t):
        if t.endswith("（よみ）"):  # texte enrichi + lecture furigana à ignorer
            base = t[:-4]
            return f'<si><r><t>{escape(base)}</t></r><rPh sb="0" eb="1"><t>よみ</t></rPh></si>'
        return f'<si><t xml:space="preserve">{escape(t)}</t></si>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("xl/workbook.xml", f'<?xml version="1.0"?><workbook {ns} {rns}><sheets>' + "".join(
            f'<sheet name="{escape(n)}" sheetId="{k + 1}" r:id="rId{k + 1}"/>' for k, (n, _) in enumerate(sheets)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{k + 1}" Target="worksheets/sheet{k + 1}.xml" Type="ws"/>' for k in range(len(sheets)))
                   + "</Relationships>")
        for k, xml in enumerate(sheet_xml):
            z.writestr(f"xl/worksheets/sheet{k + 1}.xml", xml)
        z.writestr("xl/sharedStrings.xml", f'<?xml version="1.0"?><sst {ns}>{"".join(si(t) for t in shared)}</sst>')


if __name__ == "__main__":
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    png(os.path.join(d, "image_bleue.png"), 600, 800, (40, 90, 160))
    png(os.path.join(d, "image_rouge.png"), 500, 700, (200, 60, 40))
    # Catalogue de numéros (onglet « Liste », titres de colonnes à reconnaître) + un onglet de jeux
    xlsx(os.path.join(d, "catalogue.xlsx"), [
        ("Liste", [["Revue", "N°", "Date de parution", "Je l'ai"],
                   ["Hippon Super", 1, "juillet-août 1996", "oui"],
                   ["Hippon Super", 2, 35400, "non"],  # date Excel (nombre de jours)
                   ["Hippon Super", 3, "", ""],
                   ["", "", "", ""],
                   ["Hippon Super", "", "1997", "oui"]]),  # numéro manquant : erreur signalée
        ("Jeux", [["Titre", "Titre original", "Éditeur", "Licence"],
                  ["Tobal No.1", "トバルNo.1（よみ）", "Square", ""],
                  ["Final Fantasy VII", "", "Enix", "Final Fantasy"]]),  # existant : complété, rien de remplacé
    ])
    # CSV enregistré par Excel français : « ; » et encodage Windows
    with open(os.path.join(d, "jeux_windows.csv"), "wb") as f:
        f.write("Jeu;Éditeur;Année;Licence\r\nGundam Side Story;Bandai;1996;Gundam\r\n"
                "Dragon Ball Z Legends;Bandai;1996;Dragon Ball\r\n".encode("cp1252"))
