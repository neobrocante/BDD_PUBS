# BDD Pubs : base des publicités de jeux vidéo dans les magazines

Deux versions :

- **L'application** (dossier [`appli/`](appli/README.md)) : application locale dans le navigateur,
  avec images, saisie rapide, recherche croisée, exports et sauvegardes. **Version recommandée.**
- **Le fichier Excel** (`BDD_Pubs.xlsx`), décrit ci-dessous, pour qui préfère rester dans un tableur.

---

Un simple fichier Excel (`BDD_Pubs.xlsx`), à ouvrir dans Excel ou LibreOffice, sans rien installer.
Il sert à référencer à la main les pubs trouvées dans les magazines (Famitsu, etc.) et à les
retrouver par recherche croisée.

## Le principe : une « vraie » base, mais dans Excel

Au lieu d'un grand tableau « une colonne par magazine », les infos sont réparties dans
plusieurs onglets reliés entre eux par des listes déroulantes. Chaque info n'est saisie
qu'une seule fois.

```
Plateformes ─┐
Séries ──────┼─> Jeux ──> Pubs ──> Apparitions <── Numéros <── Magazines
             └──────────────┘        (carnet de saisie)
```

| Onglet | Une ligne = | Remarque |
|---|---|---|
| **Accueil** | – | Mode d'emploi + chiffres clés |
| **Recherche** | – | Recherche croisée, résultats automatiques |
| **Apparitions** | une pub trouvée dans un numéro | magazine, n°, page, pub, en vente ○/× |
| **Pubs** | un visuel publicitaire | ID unique ; un jeu peut avoir plusieurs pubs |
| **Jeux** | un jeu | titre, titre original, série, éditeur, année |
| **Numéros** | un numéro de magazine | facultatif : sa date de parution |
| **Magazines / Séries / Plateformes** | une valeur de liste | plateformes déjà pré-remplies |

Les colonnes grises sont calculées automatiquement (série, plateforme, nb d'apparitions,
1re parution, compteurs...). Seules les colonnes à en-tête jaune se remplissent à la main.

## Ce que ça permet

- **Quelles pubs dans tel numéro ?** Recherche : Magazine + Numéro.
- **Où trouver les pubs d'un jeu ?** Recherche : Jeu (ou Série). L'onglet Jeux donne aussi le
  nombre de pubs différentes, le nombre d'apparitions et la 1re parution.
- **Dans quels magazines trouve-t-on telle pub ?** Recherche : ID pub. L'onglet Pubs donne le
  nombre d'apparitions de chaque pub.
- **Qu'est-ce que j'ai en vente ?** Recherche : En vente = ○ (combinable avec le reste).
- Filtres par année, plateforme, mot-clé dans la description ; synthèse (nb de pubs, jeux,
  numéros différents, pages de pub).

Tous les onglets ont des filtres automatiques pour trier (par ex. les jeux par nombre
d'apparitions). Les doublons (même jeu, même ID de pub, même page saisie deux fois) sont
surlignés en couleur.

## Saisie au quotidien

1. Nouveau jeu : une ligne dans **Jeux**.
2. Nouveau visuel de pub : une ligne dans **Pubs**, avec le « Prochain ID libre » affiché en haut
   à droite de l'onglet.
3. Chaque pub trouvée dans un magazine : une ligne dans **Apparitions**. La liste déroulante
   « Pub » affiche `ID | Jeu (Plateforme) - description` ; on peut aussi taper directement l'ID.

Les lignes marquées « EXEMPLE » sont fictives et sont à supprimer.

## Limites, et quand passer à une vraie appli

Le classeur est prévu pour 5 000 apparitions, 3 000 pubs et 3 000 jeux (au-delà, il suffit de
recopier la dernière ligne vers le bas). À 20-30 pubs par semaine, ça fait plusieurs années.

Une application avec une base de données deviendra utile pour stocker des **scans / photos** des
pubs, pour travailler **à plusieurs en même temps**, ou pour dépasser quelques dizaines de milliers
de lignes. Comme chaque onglet est déjà une table propre (une ligne = un enregistrement), il
suffira alors d'exporter chaque onglet en CSV pour l'importer tel quel.

## Compatibilité

Excel 2010 et plus, LibreOffice Calc. La colonne « 1re parution » utilise `MINIFS` (Excel 2019 /
Microsoft 365 / LibreOffice) et reste vide sur les versions plus anciennes.

## Regénérer / modifier le modèle

Le fichier est produit par `generer_bdd_pubs.py` (Python 3 + `openpyxl`) :

```bash
pip install openpyxl
python3 generer_bdd_pubs.py BDD_Pubs.xlsx
```

Attention : regénérer crée un fichier **vide** (avec les exemples). Pour faire évoluer un fichier
déjà rempli, ajoutez plutôt des colonnes directement dans Excel, à droite des onglets.
