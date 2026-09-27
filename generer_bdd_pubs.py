#!/usr/bin/env python3
"""Génère BDD_Pubs.xlsx : base de données des publicités de jeux vidéo
parues dans les magazines.

Le classeur est pensé comme une petite base relationnelle dans Excel :
un onglet par « table » (Plateformes, Séries, Magazines, Numéros, Jeux,
Pubs, Apparitions) reliées par des listes déroulantes, plus un onglet
Recherche qui croise tout.

Seules des fonctions Excel 2007 sont utilisées (INDEX, MATCH, COUNTIF...),
sauf MINIFS pour la « première parution » (Excel 2019 / 365 / LibreOffice),
protégée par IFERROR.

Usage : python3 generer_bdd_pubs.py [fichier_sortie.xlsx]
"""
import sys
from datetime import date

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

OUT = sys.argv[1] if len(sys.argv) > 1 else "BDD_Pubs.xlsx"

# Nombre de lignes pré-équipées (formules + listes déroulantes) par onglet.
N_PLAT, N_SERIE, N_MAG, N_NUM, N_JEU, N_PUB, N_APP = 200, 1000, 300, 3000, 3000, 3000, 5000
N_RES = 500  # lignes de résultats dans l'onglet Recherche

FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_HEAD = Font(name=FONT, size=10, bold=True)
F_HEAD_W = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=16, bold=True, color="1F3864")
F_H2 = Font(name=FONT, size=12, bold=True, color="1F3864")
F_AUTO = Font(name=FONT, size=10, color="595959")
F_NOTE = Font(name=FONT, size=9, italic=True, color="7F7F7F")

FILL_IN = PatternFill("solid", fgColor="FFE699")     # en-tête : à saisir
FILL_AUTO = PatternFill("solid", fgColor="D9D9D9")   # en-tête : calculé
FILL_AUTO_CELL = PatternFill("solid", fgColor="F2F2F2")
FILL_CRIT = PatternFill("solid", fgColor="FFF2CC")
FILL_TITLE = PatternFill("solid", fgColor="1F3864")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

FILL_OK = PatternFill("solid", fgColor="C6EFCE")
FILL_NO = PatternFill("solid", fgColor="FFC7CE")
FILL_WARN = PatternFill("solid", fgColor="F8CBAD")

MARU, BATSU = "○", "×"

wb = Workbook()
wb.remove(wb.active)


def q(sheet):
    """Référence de feuille toujours entre apostrophes (accents, espaces)."""
    return f"'{sheet}'"


def add_list_name(name, sheet, col, nrows):
    """Plage nommée dynamique : s'arrête à la dernière ligne remplie."""
    rng = f"{q(sheet)}!${col}$2:${col}${nrows + 1}"
    ref = f"OFFSET({q(sheet)}!${col}$2,0,0,MAX(1,SUMPRODUCT(--(LEN({rng})>0))),1)"
    wb.defined_names[name] = DefinedName(name, attr_text=ref)


def dropdown(ws, rng, source, strict=False, prompt=None):
    dv = DataValidation(type="list", formula1=source, allow_blank=True)
    # « warning » : propose la liste mais laisse saisir autre chose si besoin.
    dv.errorStyle = "stop" if strict else "warning"
    dv.showErrorMessage = True
    dv.errorTitle = "Valeur hors liste"
    dv.error = ("Cette valeur n'existe pas dans la liste. "
                "Ajoutez-la d'abord dans l'onglet correspondant.")
    if prompt:
        dv.showInputMessage = True
        dv.prompt = prompt
    ws.add_data_validation(dv)
    dv.add(rng)


def build_table(title, columns, nrows, rows=(), tab_color=None):
    """columns : liste de (en-tête, largeur, formule_ou_None, format, note).
    Une formule est un gabarit où {r} = numéro de ligne."""
    ws = wb.create_sheet(title)
    if tab_color:
        ws.sheet_properties.tabColor = tab_color
    for c, (head, width, formula, fmt, note) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=c, value=head)
        cell.font = F_HEAD
        cell.fill = FILL_AUTO if formula else FILL_IN
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        if note:
            cell.comment = Comment(note, "BDD Pubs")
        ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[1].height = 30

    for r in range(2, nrows + 2):
        data = rows[r - 2] if r - 2 < len(rows) else None
        for c, (head, width, formula, fmt, note) in enumerate(columns, 1):
            cell = ws.cell(row=r, column=c)
            if formula:
                cell.value = formula.format(r=r, p=r - 1)
                cell.font = F_AUTO
                cell.fill = FILL_AUTO_CELL
            else:
                cell.font = F_BASE
                if data is not None and c - 1 < len(data) and data[c - 1] is not None:
                    cell.value = data[c - 1]
            if fmt:
                cell.number_format = fmt
    ws.freeze_panes = "B2"
    last_col = get_column_letter(len(columns))
    ws.auto_filter.ref = f"A1:{last_col}{nrows + 1}"
    return ws


def dup_highlight(ws, col, nrows):
    """Surligne en rouge les doublons (noms / ID qui doivent être uniques)."""
    rng = f"{col}2:{col}{nrows + 1}"
    ws.conditional_formatting.add(
        rng, FormulaRule(formula=[f'AND({col}2<>"",COUNTIF(${col}$2:${col}${nrows + 1},{col}2)>1)'],
                         fill=FILL_NO))


def maru_batsu_format(ws, rng, first):
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{first}="{MARU}"'], fill=FILL_OK))
    ws.conditional_formatting.add(rng, FormulaRule(formula=[f'{first}="{BATSU}"'], fill=FILL_NO))


# ---------------------------------------------------------------------------
# Plages utilisées dans les formules
# ---------------------------------------------------------------------------
APP, PUB, JEU, NUM, MAG, SER, PLA, REC = (
    "Apparitions", "Pubs", "Jeux", "Numéros", "Magazines", "Séries", "Plateformes", "Recherche")


def rng(sheet, col, n):
    return f"{q(sheet)}!${col}$2:${col}${n + 1}"


# ---------------------------------------------------------------------------
# Données d'exemple (fictives, à supprimer)
# ---------------------------------------------------------------------------
EX = "EXEMPLE - à supprimer"

plateformes = [
    ("Famicom", "Nintendo"), ("Super Famicom", "Nintendo"), ("Nintendo 64", "Nintendo"),
    ("GameCube", "Nintendo"), ("Wii", "Nintendo"), ("Wii U", "Nintendo"), ("Switch", "Nintendo"),
    ("Game Boy", "Nintendo"), ("Game Boy Color", "Nintendo"), ("Game Boy Advance", "Nintendo"),
    ("Nintendo DS", "Nintendo"), ("Nintendo 3DS", "Nintendo"), ("Virtual Boy", "Nintendo"),
    ("SG-1000", "Sega"), ("Mark III / Master System", "Sega"), ("Mega Drive", "Sega"),
    ("Mega-CD", "Sega"), ("Super 32X", "Sega"), ("Sega Saturn", "Sega"), ("Dreamcast", "Sega"),
    ("Game Gear", "Sega"), ("PC Engine", "NEC"), ("PC Engine CD-ROM²", "NEC"),
    ("PC Engine SuperGrafx", "NEC"), ("PC-FX", "NEC"), ("PlayStation", "Sony"),
    ("PlayStation 2", "Sony"), ("PlayStation 3", "Sony"), ("PlayStation 4", "Sony"),
    ("PlayStation 5", "Sony"), ("PSP", "Sony"), ("PS Vita", "Sony"), ("Neo Geo", "SNK"),
    ("Neo Geo CD", "SNK"), ("Neo Geo Pocket", "SNK"), ("WonderSwan", "Bandai"),
    ("3DO", "Panasonic / 3DO"), ("Xbox", "Microsoft"), ("Xbox 360", "Microsoft"),
    ("MSX", ""), ("PC-8801", "NEC"), ("PC-9801", "NEC"), ("X68000", "Sharp"),
    ("FM Towns", "Fujitsu"), ("PC (Windows)", ""), ("Arcade", ""), ("Multi-plateformes", ""),
]

series = [("Final Fantasy",), ("Dragon Quest",), ("Biohazard",), ("Sakura Taisen",)]

magazines = [
    ("Weekly Famitsu", "ASCII / Enterbrain", "Hebdomadaire"),
    ("Dengeki PlayStation", "MediaWorks", ""),
    ("Sega Saturn Magazine", "SoftBank", ""),
]

numeros = [
    ("Weekly Famitsu", 421, date(1997, 1, 3), EX),
    ("Weekly Famitsu", 425, date(1997, 1, 31), EX),
    ("Weekly Famitsu", 430, date(1997, 3, 7), EX),
    ("Dengeki PlayStation", 38, date(1997, 1, 10), EX),
    ("Sega Saturn Magazine", 5, date(1996, 9, 1), EX),
]

jeux = [
    ("Final Fantasy VII", "ファイナルファンタジーVII", "Final Fantasy", "Square", 1997, EX),
    ("Biohazard 2", "バイオハザード2", "Biohazard", "Capcom", 1998, EX),
    ("Sakura Taisen", "サクラ大戦", "Sakura Taisen", "Sega", 1996, EX),
    ("Dragon Quest VII", "ドラゴンクエストVII エデンの戦士たち", "Dragon Quest", "Enix", 2000, EX),
]

pubs = [
    (1, "Final Fantasy VII", "PlayStation", "Cloud devant Midgar", 2, EX),
    (2, "Final Fantasy VII", "PlayStation", "Aerith, fond fleurs", 1, EX),
    (3, "Biohazard 2", "PlayStation", "Leon & Claire", 2, EX),
    (4, "Sakura Taisen", "Sega Saturn", "Sakura au sabre", 1, EX),
    (5, "Dragon Quest VII", "PlayStation", "Logo + illustration", 2, EX),
]

PUB_LABEL = {i: f"{i} | {j} ({pl}) - {d}" for (i, j, pl, d, n, rq) in pubs}

apparitions = [
    ("Weekly Famitsu", 421, 12, 1, MARU, EX),
    ("Weekly Famitsu", 421, 40, 4, BATSU, EX),
    ("Weekly Famitsu", 425, 8, 1, BATSU, EX),
    ("Weekly Famitsu", 430, 2, 2, MARU, EX),
    ("Dengeki PlayStation", 38, 2, 1, MARU, EX),
    ("Dengeki PlayStation", 38, 100, 3, BATSU, EX),
    ("Sega Saturn Magazine", 5, 1, 4, MARU, EX),
    ("Weekly Famitsu", 600, 4, 5, BATSU, EX),
]

# ---------------------------------------------------------------------------
# Onglet Accueil (rempli à la fin, créé en premier pour être le 1er onglet)
# ---------------------------------------------------------------------------
ws_home = wb.create_sheet("Accueil")
ws_rec = wb.create_sheet(REC)

# ---------------------------------------------------------------------------
# Apparitions : une ligne = une pub trouvée dans un numéro de magazine
# ---------------------------------------------------------------------------
R = q(REC)
match_cond = (
    f'AND(OR({R}!$C$4="",A{{r}}={R}!$C$4),'
    f'OR({R}!$C$5="",B{{r}}&""={R}!$C$5&""),'
    f'OR({R}!$C$6="",IFERROR(YEAR(L{{r}}),0)={R}!$C$6),'
    f'OR({R}!$C$7="",ISNUMBER(SEARCH({R}!$C$7,H{{r}}))),'
    f'OR({R}!$C$8="",J{{r}}={R}!$C$8),'
    f'OR({R}!$C$9="",I{{r}}={R}!$C$9),'
    f'OR({R}!$C$10="",G{{r}}&""={R}!$C$10&""),'
    f'OR({R}!$C$11="",E{{r}}={R}!$C$11),'
    f'OR({R}!$C$12="",ISNUMBER(SEARCH({R}!$C$12,M{{r}}&" "&F{{r}}))))'
)
pub_row = f"MATCH(G{{r}},{rng(PUB, 'A', N_PUB)},0)"


def pub_field(col):
    return (f'=IF(OR(G{{r}}="",G{{r}}="?"),"",'
            f'IFERROR(INDEX({rng(PUB, col, N_PUB)},{pub_row})&"",""))')


app_cols = [
    ("Magazine", 24, None, None, "Choisir dans la liste (onglet Magazines)."),
    ("Numéro", 10, None, None, "Numéro du magazine, tel qu'imprimé (ex. 425 ou 1997-04)."),
    ("Page", 7, None, None, "Page où commence la pub."),
    ("Pub", 55, None, None,
     "Choisir la pub dans la liste (tapez le début : ID ou nom du jeu). "
     "On peut aussi taper directement le n° d'ID de la pub."),
    ("En vente\n○ / ×", 10, None, None, "○ = en vente, × = pas en vente."),
    ("Remarques", 28, None, None, "État, scan fait, prix, etc."),
    ("ID pub", 8,
     '=IF(D{r}="","",IFERROR(VALUE(LEFT(D{r},FIND(" |",D{r}&" |")-1)),"?"))', "0", None),
    ("Jeu", 28,
     f'=IF(G{{r}}="","",IF(G{{r}}="?","⚠ pub inconnue",'
     f'IFERROR(INDEX({rng(PUB, "B", N_PUB)},{pub_row})&"","⚠ pub inconnue")))', None, None),
    ("Plateforme", 16, pub_field("C"), None, None),
    ("Série", 18, pub_field("G"), None, None),
    ("Nb pages", 8,
     f'=IF(OR(G{{r}}="",G{{r}}="?"),"",IFERROR(INDEX({rng(PUB, "E", N_PUB)},{pub_row}),""))',
     "0.#", None),
    ("Date parution", 12,
     f'=IF(A{{r}}="","",IFERROR(1/(1/INDEX({rng(NUM, "C", N_NUM)},'
     f'MATCH(A{{r}}&"|"&B{{r}},{rng(NUM, "F", N_NUM)},0))),""))',
     "yyyy-mm-dd", "Reprise de l'onglet Numéros (si le numéro y est saisi)."),
    ("Description pub", 30, pub_field("D"), None, None),
    ("(technique)", 6, "=N(N{p})+IF(AND(A{r}<>\"\"," + match_cond.replace("AND(", "", 1) + ",1,0)",
     None, "Colonne technique pour l'onglet Recherche. Ne pas modifier."),
]
ws_app = build_table(APP, app_cols, N_APP,
                     [(m, n, p, PUB_LABEL[i], v, rq) for (m, n, p, i, v, rq) in apparitions],
                     tab_color="C00000")
ws_app.column_dimensions["N"].hidden = True
ws_app.freeze_panes = "A2"
for r in range(2, N_APP + 2):
    ws_app[f"E{r}"].alignment = Alignment(horizontal="center")
dropdown(ws_app, f"A2:A{N_APP + 1}", "L_Magazines")
dropdown(ws_app, f"D2:D{N_APP + 1}", "L_Pubs")
dropdown(ws_app, f"E2:E{N_APP + 1}", f'"{MARU},{BATSU}"', strict=True)
maru_batsu_format(ws_app, f"E2:E{N_APP + 1}", "E2")
ws_app.conditional_formatting.add(
    f"H2:H{N_APP + 1}", FormulaRule(formula=['LEFT(H2,1)="⚠"'], fill=FILL_WARN))
# Même magazine + numéro + page saisi deux fois -> orange
ws_app.conditional_formatting.add(
    f"A2:C{N_APP + 1}",
    FormulaRule(formula=[f'AND($A2<>"",$C2<>"",COUNTIFS($A$2:$A${N_APP + 1},$A2,'
                         f'$B$2:$B${N_APP + 1},$B2,$C$2:$C${N_APP + 1},$C2)>1)'],
                fill=FILL_WARN))

# ---------------------------------------------------------------------------
# Pubs : une ligne = un visuel publicitaire distinct
# ---------------------------------------------------------------------------
pub_cols = [
    ("ID", 7, None, "0", "Numéro unique de la pub, à ne jamais réutiliser. "
                         "Le prochain ID libre est affiché à droite (colonne M)."),
    ("Jeu", 28, None, None, "Choisir dans la liste (onglet Jeux)."),
    ("Plateforme", 16, None, None, "Plateforme annoncée sur la pub (onglet Plateformes)."),
    ("Description / visuel", 32, None, None,
     "Ce qui permet de reconnaître cette pub parmi les autres du même jeu."),
    ("Nb pages", 8, None, "0.#", "1, 2 (double page), 0.5 (demi-page)..."),
    ("Remarques", 24, None, None, None),
    ("Série", 18,
     f'=IF(B{{r}}="","",IFERROR(INDEX({rng(JEU, "C", N_JEU)},'
     f'MATCH(B{{r}},{rng(JEU, "A", N_JEU)},0))&"","⚠ jeu inconnu"))', None, None),
    ("Éditeur", 16,
     f'=IF(B{{r}}="","",IFERROR(INDEX({rng(JEU, "D", N_JEU)},'
     f'MATCH(B{{r}},{rng(JEU, "A", N_JEU)},0))&"",""))', None, None),
    ("Nb apparitions", 11,
     f'=IF(A{{r}}="","",COUNTIF({rng(APP, "G", N_APP)},A{{r}}))', "0", None),
    ("Dont en vente", 9,
     f'=IF(A{{r}}="","",COUNTIFS({rng(APP, "G", N_APP)},A{{r}},{rng(APP, "E", N_APP)},"{MARU}"))',
     "0", None),
    ("1re parution", 12,
     f'=IF(A{{r}}="","",IFERROR(1/(1/_xlfn.MINIFS({rng(APP, "L", N_APP)},'
     f'{rng(APP, "G", N_APP)},A{{r}})),""))',
     "yyyy-mm-dd", "Date du plus ancien numéro où la pub apparaît (Excel 2019 / 365)."),
    ("Libellé (liste)", 50,
     '=IF(A{r}="","",A{r}&" | "&B{r}&IF(C{r}="",""," ("&C{r}&")")&IF(D{r}="",""," - "&D{r}))',
     None, "Texte proposé dans la liste déroulante de l'onglet Apparitions."),
]
ws_pub = build_table(PUB, pub_cols, N_PUB, pubs, tab_color="ED7D31")
dropdown(ws_pub, f"B2:B{N_PUB + 1}", "L_Jeux")
dropdown(ws_pub, f"C2:C{N_PUB + 1}", "L_Plateformes")
dup_highlight(ws_pub, "A", N_PUB)
ws_pub.conditional_formatting.add(
    f"G2:G{N_PUB + 1}", FormulaRule(formula=['LEFT(G2,1)="⚠"'], fill=FILL_WARN))
ws_pub["N1"] = "Prochain ID libre →"
ws_pub["N1"].font = F_HEAD
ws_pub["N1"].alignment = Alignment(horizontal="right", vertical="center")
ws_pub["O1"] = f"=MAX({rng(PUB, 'A', N_PUB)})+1"
ws_pub["O1"].font = Font(name=FONT, size=12, bold=True, color="C00000")
ws_pub["O1"].fill = FILL_CRIT
ws_pub["O1"].alignment = Alignment(horizontal="center", vertical="center")
ws_pub.column_dimensions["N"].width = 20

# ---------------------------------------------------------------------------
# Jeux
# ---------------------------------------------------------------------------
jeu_cols = [
    ("Titre", 30, None, None, "Titre unique du jeu (doublons surlignés en rouge)."),
    ("Titre original", 30, None, None, "Titre japonais, facultatif."),
    ("Série", 18, None, None, "Choisir dans la liste (onglet Séries). Laisser vide si aucune."),
    ("Éditeur", 16, None, None, None),
    ("Année", 8, None, "0", None),
    ("Remarques", 24, None, None, None),
    ("Nb pubs\ndifférentes", 11, f'=IF(A{{r}}="","",COUNTIF({rng(PUB, "B", N_PUB)},A{{r}}))', "0", None),
    ("Nb apparitions", 11, f'=IF(A{{r}}="","",COUNTIF({rng(APP, "H", N_APP)},A{{r}}))', "0", None),
    ("Dont en vente", 9,
     f'=IF(A{{r}}="","",COUNTIFS({rng(APP, "H", N_APP)},A{{r}},{rng(APP, "E", N_APP)},"{MARU}"))',
     "0", None),
    ("1re parution", 12,
     f'=IF(A{{r}}="","",IFERROR(1/(1/_xlfn.MINIFS({rng(APP, "L", N_APP)},'
     f'{rng(APP, "H", N_APP)},A{{r}})),""))', "yyyy-mm-dd", None),
]
ws_jeu = build_table(JEU, jeu_cols, N_JEU, jeux, tab_color="70AD47")
dropdown(ws_jeu, f"C2:C{N_JEU + 1}", "L_Series")
dup_highlight(ws_jeu, "A", N_JEU)

# ---------------------------------------------------------------------------
# Numéros (facultatif : sert à connaître la date de chaque numéro)
# ---------------------------------------------------------------------------
num_cols = [
    ("Magazine", 24, None, None, "Choisir dans la liste (onglet Magazines)."),
    ("Numéro", 10, None, None, "Même écriture que dans l'onglet Apparitions."),
    ("Date de parution", 14, None, "yyyy-mm-dd", "Format AAAA-MM-JJ conseillé."),
    ("Remarques", 30, None, None, None),
    ("Nb pubs\nréférencées", 11,
     f'=IF(A{{r}}="","",COUNTIFS({rng(APP, "A", N_APP)},A{{r}},{rng(APP, "B", N_APP)},B{{r}}))',
     "0", None),
    ("(clé)", 6, '=IF(A{r}="","",A{r}&"|"&B{r})', None, "Colonne technique. Ne pas modifier."),
]
ws_num = build_table(NUM, num_cols, N_NUM, numeros, tab_color="5B9BD5")
ws_num.column_dimensions["F"].hidden = True
dropdown(ws_num, f"A2:A{N_NUM + 1}", "L_Magazines")
ws_num.conditional_formatting.add(
    f"A2:B{N_NUM + 1}",
    FormulaRule(formula=[f'AND($F2<>"",COUNTIF($F$2:$F${N_NUM + 1},$F2)>1)'], fill=FILL_NO))

# ---------------------------------------------------------------------------
# Magazines, Séries, Plateformes (listes de référence)
# ---------------------------------------------------------------------------
mag_cols = [
    ("Magazine", 26, None, None, "Nom unique du magazine."),
    ("Éditeur", 20, None, None, None),
    ("Périodicité", 14, None, None, None),
    ("Remarques", 30, None, None, None),
    ("Nb numéros\nrépertoriés", 11, f'=IF(A{{r}}="","",COUNTIF({rng(NUM, "A", N_NUM)},A{{r}}))', "0", None),
    ("Nb apparitions", 11, f'=IF(A{{r}}="","",COUNTIF({rng(APP, "A", N_APP)},A{{r}}))', "0", None),
    ("Dont en vente", 9,
     f'=IF(A{{r}}="","",COUNTIFS({rng(APP, "A", N_APP)},A{{r}},{rng(APP, "E", N_APP)},"{MARU}"))',
     "0", None),
]
ws_mag = build_table(MAG, mag_cols, N_MAG, magazines, tab_color="5B9BD5")
dup_highlight(ws_mag, "A", N_MAG)

ser_cols = [
    ("Série", 26, None, None, "Nom unique de la série."),
    ("Remarques", 30, None, None, None),
    ("Nb jeux", 9, f'=IF(A{{r}}="","",COUNTIF({rng(JEU, "C", N_JEU)},A{{r}}))', "0", None),
    ("Nb pubs\ndifférentes", 11, f'=IF(A{{r}}="","",COUNTIF({rng(PUB, "G", N_PUB)},A{{r}}))', "0", None),
    ("Nb apparitions", 11, f'=IF(A{{r}}="","",COUNTIF({rng(APP, "J", N_APP)},A{{r}}))', "0", None),
]
ws_ser = build_table(SER, ser_cols, N_SERIE, series, tab_color="A5A5A5")
dup_highlight(ws_ser, "A", N_SERIE)

pla_cols = [
    ("Plateforme", 26, None, None, "Nom unique de la plateforme."),
    ("Constructeur", 18, None, None, None),
    ("Remarques", 30, None, None, None),
    ("Nb pubs\ndifférentes", 11, f'=IF(A{{r}}="","",COUNTIF({rng(PUB, "C", N_PUB)},A{{r}}))', "0", None),
    ("Nb apparitions", 11, f'=IF(A{{r}}="","",COUNTIF({rng(APP, "I", N_APP)},A{{r}}))', "0", None),
]
ws_pla = build_table(PLA, pla_cols, N_PLAT, plateformes, tab_color="A5A5A5")
dup_highlight(ws_pla, "A", N_PLAT)

# Listes déroulantes dynamiques
add_list_name("L_Magazines", MAG, "A", N_MAG)
add_list_name("L_Series", SER, "A", N_SERIE)
add_list_name("L_Plateformes", PLA, "A", N_PLAT)
add_list_name("L_Jeux", JEU, "A", N_JEU)
add_list_name("L_Pubs", PUB, "L", N_PUB)

# ---------------------------------------------------------------------------
# Recherche
# ---------------------------------------------------------------------------
ws = ws_rec
ws.sheet_properties.tabColor = "7030A0"
ws["B1"] = "Recherche croisée"
ws["B1"].font = F_TITLE
ws["B2"] = ("Remplissez un ou plusieurs critères (cases jaunes) : les résultats se mettent à jour "
            "tout seuls. Critère vide = ignoré. Tous les critères remplis doivent être vrais.")
ws["B2"].font = F_NOTE

criteria = [
    ("Magazine", "Liste déroulante"),
    ("Numéro", "Exact (ex. 425)"),
    ("Année de parution", "Ex. 1997 (nécessite la date dans Numéros)"),
    ("Jeu (contient)", "Ex. « Final » trouve tous les Final Fantasy"),
    ("Série", "Liste déroulante"),
    ("Plateforme", "Liste déroulante"),
    ("ID pub", "Toutes les parutions d'une même pub"),
    (f"En vente ({MARU} / {BATSU})", "Liste déroulante"),
    ("Mot-clé", "Cherché dans la description de la pub et les remarques"),
]
ws["B3"] = "Critère"
ws["C3"] = "Valeur"
ws["D3"] = "Aide"
for c in ("B3", "C3", "D3"):
    ws[c].font = F_HEAD_W
    ws[c].fill = FILL_TITLE
for i, (lab, aide) in enumerate(criteria):
    r = 4 + i
    ws[f"B{r}"] = lab
    ws[f"B{r}"].font = F_HEAD
    ws[f"C{r}"].fill = FILL_CRIT
    ws[f"C{r}"].font = Font(name=FONT, size=11, bold=True)
    ws[f"C{r}"].border = BORDER
    ws[f"D{r}"] = aide
    ws[f"D{r}"].font = F_NOTE
dropdown(ws, "C4", "L_Magazines")
dropdown(ws, "C7", "L_Jeux")
dropdown(ws, "C8", "L_Series")
dropdown(ws, "C9", "L_Plateformes")
dropdown(ws, "C11", f'"{MARU},{BATSU}"')
for dv in ws.data_validations.dataValidation:
    dv.showErrorMessage = False  # critères : saisie libre autorisée

HDR = 15
FIRST = HDR + 1
LAST = HDR + N_RES
res_cols = [  # (en-tête, colonne source dans Apparitions, largeur, format)
    ("Magazine", "A", 24, None), ("N°", "B", 8, None), ("Date", "L", 12, "yyyy-mm-dd"),
    ("Page", "C", 7, None), ("Jeu", "H", 28, None), ("Plateforme", "I", 16, None),
    ("Série", "J", 18, None), ("ID pub", "G", 8, None), ("Description pub", "M", 30, None),
    ("Nb p.", "K", 7, "0.#"), (f"En vente", "E", 9, None), ("Remarques", "F", 28, None),
]
# Colonne A (cachée) : ligne de la k-ième apparition trouvée
ws.cell(row=HDR, column=1, value="(ligne)").font = F_NOTE
for c, (head, src, width, fmt) in enumerate(res_cols, 2):
    cell = ws.cell(row=HDR, column=c, value=head)
    cell.font = F_HEAD_W
    cell.fill = FILL_TITLE
    cell.alignment = Alignment(horizontal="center")
    ws.column_dimensions[get_column_letter(c)].width = width
ws.column_dimensions["B"].width = 26
ws.column_dimensions["C"].width = 26
ws.column_dimensions["D"].width = 14
ws.column_dimensions["A"].hidden = True

app_n = f"{q(APP)}!$N$1:$N${N_APP + 1}"
for r in range(FIRST, LAST + 1):
    ws.cell(row=r, column=1, value=f'=IFERROR(MATCH({r - HDR},{app_n},0),"")')
    for c, (head, src, width, fmt) in enumerate(res_cols, 2):
        cell = ws.cell(row=r, column=c,
                       value=f'=IF($A{r}="","",INDEX({q(APP)}!${src}$1:${src}${N_APP + 1},$A{r})&"")'
                       if fmt is None else
                       f'=IF($A{r}="","",INDEX({q(APP)}!${src}$1:${src}${N_APP + 1},$A{r}))')
        cell.font = F_BASE
        if fmt:
            cell.number_format = fmt
    ws.cell(row=r, column=12).alignment = Alignment(horizontal="center")
maru_batsu_format(ws, f"L{FIRST}:L{LAST}", f"L{FIRST}")

# Colonnes techniques (cachées) pour compter les valeurs distinctes :
# O = pubs, P = jeux, Q/R = numéros (magazine|n°)
for r in range(FIRST, LAST + 1):
    ws[f"O{r}"] = f'=IF(I{r}="",0,IF(COUNTIF(I${FIRST}:I{r},I{r})=1,1,0))'
    ws[f"P{r}"] = f'=IF(F{r}="",0,IF(COUNTIF(F${FIRST}:F{r},F{r})=1,1,0))'
    ws[f"Q{r}"] = f'=IF(B{r}="","",B{r}&"|"&C{r})'
    ws[f"R{r}"] = f'=IF(Q{r}="",0,IF(COUNTIF(Q${FIRST}:Q{r},Q{r})=1,1,0))'
for col in "OPQR":
    ws.column_dimensions[col].hidden = True

# Synthèse
ws["J3"] = "Synthèse"
ws["J3"].font = F_HEAD_W
ws["J3"].fill = FILL_TITLE
ws["K3"].fill = FILL_TITLE
summary = [
    ("Apparitions trouvées", f"=MAX({app_n})"),
    ("Pubs différentes", f"=SUM(O{FIRST}:O{LAST})"),
    ("Jeux différents", f"=SUM(P{FIRST}:P{LAST})"),
    ("Numéros différents", f"=SUM(R{FIRST}:R{LAST})"),
    (f"Dont en vente ({MARU})", f'=COUNTIF(L{FIRST}:L{LAST},"{MARU}")'),
    ("Total pages de pub", f"=SUM(K{FIRST}:K{LAST})"),
]
for i, (lab, f) in enumerate(summary):
    r = 4 + i
    ws[f"J{r}"] = lab
    ws[f"J{r}"].font = F_HEAD
    ws[f"J{r}"].alignment = Alignment(horizontal="right")
    ws[f"K{r}"] = f
    ws[f"K{r}"].font = Font(name=FONT, size=11, bold=True, color="1F3864")
    ws[f"K{r}"].alignment = Alignment(horizontal="center")
    ws[f"K{r}"].border = BORDER
ws["J11"] = (f'=IF(K4>{N_RES},"⚠ Seuls les {N_RES} premiers résultats sont affichés : '
             f'affinez la recherche.","")')
ws["J11"].font = Font(name=FONT, size=10, bold=True, color="C00000")
ws["B13"] = ("Astuce : pour trouver toutes les parutions d'une pub précise, mettez juste son ID. "
             "Pour la liste des pubs d'un numéro : Magazine + Numéro.")
ws["B13"].font = F_NOTE
ws.freeze_panes = f"B{FIRST}"
ws.auto_filter.ref = None

# ---------------------------------------------------------------------------
# Accueil
# ---------------------------------------------------------------------------
ws = ws_home
ws.sheet_properties.tabColor = "1F3864"
ws.column_dimensions["A"].width = 3
ws.column_dimensions["B"].width = 26
ws.column_dimensions["C"].width = 95
ws["B1"] = "Base de données des pubs de jeux vidéo dans les magazines"
ws["B1"].font = F_TITLE

lines = [
    ("h", "Comment c'est organisé"),
    ("t", "Plateformes", "Liste des consoles / machines (déjà pré-remplie, complétez si besoin)."),
    ("t", "Séries", "Liste des séries de jeux (Final Fantasy, Dragon Quest...)."),
    ("t", "Magazines", "Liste des magazines (Famitsu, Dengeki PlayStation...)."),
    ("t", "Numéros", "Facultatif : un numéro par ligne avec sa date de parution. "
                     "Sert à dater les pubs et à chercher par année."),
    ("t", "Jeux", "Un jeu par ligne : titre, série, éditeur, année. "
                  "Les compteurs (nb de pubs, d'apparitions...) sont calculés."),
    ("t", "Pubs", "Un visuel publicitaire par ligne, avec un ID unique. "
                  "Un même jeu peut avoir plusieurs pubs (visuels différents)."),
    ("t", "Apparitions", "LE carnet de saisie : une ligne = une pub trouvée dans un numéro "
                         "de magazine (magazine, n°, page, pub, en vente ○/×)."),
    ("t", "Recherche", "Recherche croisée : pubs d'un numéro, parutions d'un jeu ou d'une pub, "
                       "par série, plateforme, année, en vente..."),
    ("h", "Saisie au quotidien"),
    ("t", "1. Nouveau jeu ?", "L'ajouter dans Jeux (et sa série dans Séries si elle n'existe pas)."),
    ("t", "2. Nouvelle pub ?", "L'ajouter dans Pubs avec le « Prochain ID libre » affiché en haut à "
                               "droite de l'onglet, et une description qui permet de la reconnaître."),
    ("t", "3. Chaque pub trouvée", "Une ligne dans Apparitions : choisir le magazine, taper le numéro "
                                   "et la page, choisir la pub dans la liste (on peut taper le début "
                                   "du nom du jeu ou juste l'ID), puis ○ ou ×."),
    ("t", "Astuce", "Pour enchaîner les pubs d'un même numéro : Ctrl+D recopie la cellule du dessus "
                    "(magazine, numéro)."),
    ("h", "Codes couleur"),
    ("c", "En-tête jaune", "Colonne à remplir à la main.", FILL_IN),
    ("c", "En-tête / cellules grises", "Calculé automatiquement : ne pas modifier.", FILL_AUTO),
    ("c", "Rouge", "Doublon (nom ou ID déjà utilisé) ou ×.", FILL_NO),
    ("c", "Orange", "Pub / jeu inconnu, ou même magazine + n° + page saisi deux fois.", FILL_WARN),
    ("h", "Bon à savoir"),
    ("t", "Données d'exemple", "Les lignes marquées « EXEMPLE » (Numéros, Jeux, Pubs, Apparitions) "
                               "sont fictives : sélectionnez-les, clic droit > Supprimer."),
    ("t", "Filtres et tris", "Chaque onglet a des filtres (flèches dans l'en-tête) : trier les jeux "
                             "par nb d'apparitions, filtrer les pubs d'un jeu, etc."),
    ("t", "Faire évoluer", "On peut ajouter des colonnes à droite de chaque onglet (format, état, "
                           "prix...). Ne pas renommer les onglets ni supprimer les colonnes grises."),
    ("t", "Capacité", f"Lignes préparées : {N_APP} apparitions, {N_PUB} pubs, {N_JEU} jeux. "
                      "Au-delà, recopier la dernière ligne vers le bas."),
    ("t", "Renommer un jeu", "Si on corrige le titre d'un jeu dans Jeux, le corriger aussi "
                             "dans Pubs (Rechercher/Remplacer)."),
    ("t", "Compatibilité", "Excel 2010 et plus, LibreOffice. La « 1re parution » demande "
                           "Excel 2019 / Microsoft 365 (sinon la colonne reste vide)."),
]
r = 3
for item in lines:
    if item[0] == "h":
        r += 1
        ws[f"B{r}"] = item[1]
        ws[f"B{r}"].font = F_H2
    else:
        ws[f"B{r}"] = item[1]
        ws[f"B{r}"].font = F_HEAD
        ws[f"C{r}"] = item[2]
        ws[f"C{r}"].font = F_BASE
        ws[f"C{r}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws[f"B{r}"].alignment = Alignment(vertical="top")
        if item[0] == "c":
            ws[f"B{r}"].fill = item[3]
    r += 1

r += 1
ws[f"B{r}"] = "Chiffres clés"
ws[f"B{r}"].font = F_H2
r += 1
stats = [
    ("Apparitions", f'=COUNTIF({rng(APP, "A", N_APP)},"?*")'),
    ("Pubs différentes", f"=COUNT({rng(PUB, 'A', N_PUB)})"),
    ("Jeux", f"=SUMPRODUCT(--(LEN({rng(JEU, 'A', N_JEU)})>0))"),
    ("Séries", f"=SUMPRODUCT(--(LEN({rng(SER, 'A', N_SERIE)})>0))"),
    ("Magazines", f"=SUMPRODUCT(--(LEN({rng(MAG, 'A', N_MAG)})>0))"),
    ("Numéros répertoriés", f"=SUMPRODUCT(--(LEN({rng(NUM, 'A', N_NUM)})>0))"),
    (f"Apparitions en vente ({MARU})", f'=COUNTIF({rng(APP, "E", N_APP)},"{MARU}")'),
    ("Prochain ID de pub libre", f"=MAX({rng(PUB, 'A', N_PUB)})+1"),
]
for lab, f in stats:
    ws[f"B{r}"] = lab
    ws[f"B{r}"].font = F_HEAD
    ws[f"C{r}"] = f
    ws[f"C{r}"].font = Font(name=FONT, size=11, bold=True, color="1F3864")
    ws[f"C{r}"].alignment = Alignment(horizontal="left")
    r += 1

wb.active = 0
wb.save(OUT)
print(f"OK : {OUT}")
