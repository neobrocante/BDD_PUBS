# BDD Pubs : l'application

Application locale (dans le navigateur, sur `http://localhost:8765`) pour référencer les pubs de
jeux vidéo trouvées dans les magazines, avec leurs images.

Rien à installer avec l'exécutable Windows (sinon, Python 3). Pas d'Internet nécessaire, pas de
compte : tout reste sur l'ordinateur (voir « Vos données » plus bas).

## Lancer l'application

### Windows, sans rien installer : `BDD Pubs.exe`

Double-cliquer sur **`BDD Pubs.exe`**. L'application s'ouvre dans le navigateur, sans aucune
fenêtre noire.

- 1er lancement : si Windows affiche « Windows a protégé votre ordinateur », cliquer sur
  « Informations complémentaires » puis « Exécuter quand même » (l'exécutable n'est pas signé).
- Les données sont rangées à part (voir « Vos données » plus bas) : le programme peut être déplacé ou remplacé.
- Pour l'avoir sur le bureau : clic droit sur `BDD Pubs.exe` > « Afficher d'autres options » >
  « Envoyer vers » > « Bureau (créer un raccourci) ».

Où trouver l'exécutable : il est construit automatiquement par GitHub à chaque mise à jour.
Sur la page du dépôt : onglet **Actions** > « Exécutable Windows » > dernière exécution réussie >
en bas, deux versions au choix :

- **BDD-Pubs-Windows** : un seul fichier `BDD Pubs.exe`. Il se décompresse dans un dossier
  temporaire à chaque lancement, ce que les antivirus (Avast…) analysent de près.
- **BDD-Pubs-Windows-dossier** (conseillée si l'antivirus fait des histoires) : un dossier
  `BDD Pubs` contenant `BDD Pubs.exe` et ses fichiers. Même utilisation (double-clic sur
  `BDD Pubs.exe`), démarrage plus rapide, rien de décompressé à chaque lancement.

**Lien fixe vers la dernière version** : chaque mise à jour est aussi publiée dans la release
« dernière version » du dépôt : <https://github.com/neobrocante/BDD_PUBS/releases/latest>
(téléchargement direct : `…/releases/latest/download/BDD-Pubs-Windows-dossier.zip`).
Tant que le dépôt est privé, seuls les comptes GitHub qui y ont accès peuvent l'ouvrir.

Les deux versions utilisent les mêmes données (rangées à part) : on peut passer de l'une à l'autre.

### Avec Python installé : `BDD Pubs.pyw`

1. Installer Python 3 : <https://www.python.org/downloads/>
   (sous Windows, **cocher « Add python.exe to PATH »**).
2. Double-cliquer sur **`BDD Pubs.pyw`** : même fonctionnement que l'exécutable, sans fenêtre noire.

Sur Mac : double-cliquer sur `Lancer BDD Pubs (Mac-Linux).command` (la 1re fois : clic droit >
Ouvrir). Ou, dans un terminal : `python3 app.py`.

### Arrêt

L'application **reste lancée** (en arrière-plan, sans fenêtre) jusqu'à ce qu'on clique sur
**⏻ Quitter** en haut à droite, ou jusqu'à l'arrêt de l'ordinateur. On peut donc fermer l'onglet
et revenir plus tard directement sur <http://localhost:8765> (le garder en favori).
Au repos, elle ne consomme quasiment rien (environ 30 Mo de mémoire).

Double-cliquer alors qu'elle tourne déjà rouvre simplement l'onglet. Si une page est restée
ouverte pendant que l'application était arrêtée, elle se reconnecte toute seule dès la relance.

## Ce qu'on peut faire

| Page | Pour quoi faire |
|---|---|
| **Saisie rapide** | Choisir un magazine + un numéro, puis enchaîner les pubs trouvées dedans : pub, page, en vente ○/×, remarques, photo. Les magazines, numéros, jeux, séries et pubs manquants se créent au passage. |
| **Recherche** | Recherche croisée : magazine, numéro, année, jeu, série, plateforme, n° de pub, en vente, mot-clé. Statistiques + export CSV du résultat. |
| **Pubs** | Galerie de toutes les pubs (un visuel = une pub, avec un n° unique, une ou **plusieurs plateformes** cochées). Fiche : images, et **tous les magazines où on la trouve**. |
| **Jeux** | Liste triable (nb de pubs, de parutions, 1re parution). Fiche : toutes ses pubs et toutes ses parutions. |
| **Magazines** | Magazines > numéros > **les publicités de chaque numéro**, avec la couverture. Pages de pub au total et **en moyenne par numéro**, complétude de la collection. |
| **Catalogue** | **Tous les magazines parus, même ceux que vous n'avez pas** : nombre de numéros parus, numéros possédés / manquants, « il me manque N numéros » (liste copiable). |
| **Stats** | Chiffres regroupés par magazine, plateforme, éditeur, type de jeu, licence, série, année… avec filtres combinables et barres. |
| **Listes** | Séries et plateformes (plateformes japonaises déjà remplies). |
| **Import / Export** | **Importer** des listes Excel (.xlsx) ou CSV ; exports CSV pour Excel (toutes les tables) et **sauvegarde complète en ZIP** (base + images). |

### Images

L'image d'une pub se met **sur la pub** : une même pub parue dans 5 magazines n'a besoin que
d'une image, visible depuis ses 5 parutions.

- Nouvelle pub : zone « Image de la pub » dans sa fenêtre de création.
- Pub existante sans image : dans la saisie rapide, une zone apparaît dans son aperçu
  (sinon, depuis sa fiche).
- Couverture d'un numéro : dans la saisie rapide (à droite) ou sur la fiche du numéro.
- Photo de *votre* exemplaire (état, pour la vente), facultatif : bouton ✎ d'une parution.

Glisser-déposer, cliquer pour choisir un fichier, ou coller une capture (Ctrl+V). Les miniatures
sont créées automatiquement et montrent l'image **entière** (sans la couper) ; un clic sur une
miniature l'affiche en grand (flèches ← →). L'étoile ★ choisit l'image principale.

### Corriger sans se perdre

- **← Retour** (en haut des fiches) : revient à la page précédente.
- **✎ pub** dans les tableaux de pubs d'un numéro, d'un jeu… : corrige la pub elle-même (nombre
  de pages, description, plateformes) dans une fenêtre, **sans quitter la page**. Même chose avec
  « ✎ modifier cette pub » dans la saisie rapide, et dans la fenêtre ✎ d'une parution.
- Le **numéro de version** est affiché en haut à droite (à donner en cas de souci).

Sur un petit écran (portable 14 pouces), l'affichage se resserre tout seul : la saisie rapide
tient à l'écran et le bouton « Enregistrer » reste toujours visible en bas.

### Saisie rapide : le jeu, puis la pub reconnue à sa miniature

1. Taper les premières lettres du **jeu** (les titres qui commencent par ces lettres viennent en
   premier). Jeu inconnu : « ＋ Nouveau jeu », puis la fenêtre « Nouvelle pub » s'ouvre d'elle-même.
2. Les **miniatures de toutes les pubs de ce jeu** s'affichent : toucher celle qu'on reconnaît
   (🔍 pour l'agrandir), ou « ＋ Nouvelle pub » si c'en est une autre.
3. Page, en vente ○/×, remarques, **Enregistrer**. Le magazine et le numéro restent en place
   pour la pub suivante.

Au clavier : lettres du jeu → `Entrée` → `Tab` jusqu'à la miniature → `Entrée` → page → `Entrée`.

### Dates de parution

Le champ « Date de parution » accepte la date **telle qu'elle est écrite sur le magazine** :
`8 et 15 avril 1997`, `juillet-août 1996`, `1997年4月8・15日号`, `08/04/1997`, `1997-04-08`…
Le texte est affiché tel quel ; l'application en déduit le premier jour (ou mois) pour trier et
pour les statistiques par année. Seule obligation : l'année doit y figurer.

### Catalogue : savoir ce qui manque

1. Page **Catalogue** > « ＋ Ajouter un magazine » (ou un magazine existant) > **✎ Modifier** :
   indiquer le **nombre de numéros parus** (et, si on veut, les années et la console du magazine).
2. « **Générer** » les numéros de 1 à N : ils sont créés comme **manquants**.
3. Toucher un numéro pour le marquer **possédé ✓** (ou manquant). Saisir une pub dans un numéro le
   marque possédé automatiquement.
4. La jauge montre la complétude, avec des barres par année ; en bas, « **Il me manque** : 1-4,
   6-12 » (bouton « Copier » pour l'envoyer à un vendeur).

Les magazines ne sont pas pré-remplis : c'est à vous de compléter le catalogue au fil de l'eau.

### Jeux : type, licence, romaji, recherche en ligne

Fiche d'un jeu : **type de jeu** (RPG, action…) et **licence** (Dragon Ball, Gundam… : différente
de la série de jeux). Les valeurs déjà utilisées sont proposées en tapant. Elles servent de filtres
dans la Recherche, la liste des Jeux et les Statistiques.

- **Lecture romaji** : remplie toute seule d'après le titre original (`ファイナルファンタジーVII` →
  `fainarufantajī VII`), modifiable. Les kana sont toujours lus ; les **kanji** ne le sont que si
  le module facultatif `pykakasi` est installé (sinon ils restent tels quels, à compléter à la
  main). Page Jeux : « あ→a Remplir les romaji » pour les jeux déjà saisis. La recherche trouve
  aussi les jeux par leur romaji.
- **🔎 Chercher ce jeu en ligne** (sous le titre, dans la fiche d'un jeu) : propose les fiches de
  **Wikidata** (base libre et gratuite, sans compte) ; toucher la bonne remplit les cases vides
  (titre japonais, éditeur, année, type, série) sans rien remplacer. Seul le titre cherché est
  envoyé, uniquement au clic. Désactivable : page Import / Export. Les jeux japonais peu connus
  n'y figurent pas toujours.

### Importer depuis Excel ou CSV

Page **Import / Export** > « Choisir un fichier… » (`.xlsx` ou `.csv`) :

1. L'application devine ce que contient le fichier (parutions, jeux, magazines, numéros du
   catalogue, pubs) et à quoi correspond chaque colonne, d'après les titres de colonnes. On peut
   corriger ces choix ; un aperçu des premières lignes est affiché.
2. **Vérifier** : montre ce qui serait créé ou complété, et les lignes à problème (avec leur
   numéro), **sans rien enregistrer**.
3. **Importer** : les magazines, numéros, jeux, séries, plateformes et pubs manquants sont créés.
   Ce qui existe déjà n'est **jamais remplacé** (seules les cases vides sont complétées) ; importer
   deux fois le même fichier ne crée pas de doublons. Une copie de la base est faite juste avant.

L'**ancien fichier Excel « BDD Pubs »** est reconnu : tous ses onglets sont importés d'un coup
(les lignes « EXEMPLE » sont ignorées). Les fichiers `.xls` ou `.ods` sont à enregistrer d'abord
au format `.xlsx` (« Enregistrer sous » dans Excel ou LibreOffice).

## Projets

Menu **📁** en haut à gauche. Au lancement, l'application ouvre toujours le même projet
(au départ : « Projet principal », renommable) ; rien à choisir.

Page **Projets** : créer un projet vide, créer le **projet de démonstration** (exemples fictifs,
avec affiches), renommer, choisir le projet ouvert au lancement, **exporter** un projet seul
(ZIP : base + images), **importer** un ZIP exporté (ou une sauvegarde complète), supprimer un
projet (sauf le projet de base). Chaque onglet reste sur son projet (adresse `/p/<projet>/`).

Sur le disque : le projet de base est directement dans `data/`, les autres dans
`data/projets/<projet>/`, la liste dans `data/projets.json`.

## Vos données : où elles sont, comment elles sont protégées

- **Emplacement fixe**, indépendant du programme : `%LOCALAPPDATA%\BDD Pubs\data` sous Windows
  (`~/Library/Application Support/BDD Pubs/data` sur Mac, `~/.local/share/bdd-pubs/data` sous Linux).
  Mettre à jour, déplacer ou supprimer le programme n'y touche pas.
- **Reprise automatique** : les anciennes versions rangeaient les données à côté du programme. Au
  premier lancement d'une nouvelle version, si l'emplacement fixe est vide, les données sont
  **copiées** depuis la version encore lancée, le dossier du programme, ou le Bureau /
  Téléchargements / Documents. L'ancien dossier n'est pas modifié (une note y est déposée).
  Bouton « Retrouver d'anciennes données… » (page Projets) pour chercher à la main.
- **Sauvegarde automatique quotidienne** dans `Documents\BDD Pubs - sauvegardes` (dossier
  modifiable : clé USB, OneDrive…) : la base de tous les projets chaque jour (30 jours gardés,
  quelques Mo) et une copie des photos, où **seules les nouvelles photos sont ajoutées** (le
  dossier pèse environ le poids des photos, une seule fois). Restauration en un clic à la date
  voulue (page Projets).
- Avant toute restauration ou reprise, les données actuelles sont d'abord sauvegardées.

## Mettre à jour, changer d'ordinateur

- **Mettre à jour** : lancer la nouvelle version, où qu'elle soit dézippée. Le ZIP téléchargé ne
  contient **jamais** de données, et la nouvelle version remplace d'elle-même l'ancienne si elle
  tourne encore.
- **Tout exporter** (page Projets) : un seul ZIP avec tous les projets et toutes les photos.
- **Tout restaurer** (page Projets) : remet tout exactement comme dans ce ZIP.
- **Importer un projet** : ajoute un projet exporté seul, à côté des projets existants.

## Utiliser le téléphone pour prendre les pubs en photo

Page **Export** > cocher « Rendre l'application accessible depuis le téléphone ». L'adresse à
ouvrir sur le téléphone (même Wi-Fi) s'affiche, par ex. `http://192.168.1.20:8765`. Dans les
champs image, le téléphone propose alors l'appareil photo. Le réglage est retenu pour les
lancements suivants. (Pas de mot de passe : à n'activer que sur un réseau de confiance.)

## Sauvegardes

Voir « Vos données » plus haut : sauvegarde automatique quotidienne, restauration à une date,
« Tout exporter / Tout restaurer ». En plus, une copie de chaque base est faite à chaque démarrage
dans le sous-dossier `sauvegardes` des données (15 dernières).

## Pour aller plus loin (technique)

Architecture, règles de développement et tests : voir `CLAUDE.md` à la racine du dépôt.

- `app.py` : serveur Python, bibliothèque standard uniquement ; base SQLite `data/bdd_pubs.sqlite`.
- `static/` : l'interface (HTML/CSS/JavaScript, sans dépendance ni connexion Internet).
- Options : `--port 8766`, `--no-browser`, `--arret-auto` (s'arrêter quand plus aucun onglet n'est ouvert),
  `--reseau`, `--demo` (données d'exemple dans le projet ouvert au lancement, s'il est vide).
  Variable `BDD_PUBS_DATA` pour placer les données ailleurs. Sans fenêtre (`.pyw` / `.exe`), les
  messages vont dans `data/journal.txt`.
- L'exécutable Windows est construit par `.github/workflows/executable-windows.yml` (PyInstaller),
  qui vérifie aussi qu'il démarre et répond avant de le publier.
- Ajouter un champ : ajouter une étape `ALTER TABLE …` à la liste `MIGRATIONS` de `app.py`
  (elle est appliquée une seule fois, au démarrage suivant), puis le champ dans `SPEC` et dans
  le formulaire correspondant de `static/app.js`.
- Modèle de données :

```
magazines ─< numéros ─< parutions >─ pubs >─ jeux >─ séries
                                      │
                                      └──> plateformes

images : rattachées à une pub, un numéro (couverture), une parution ou un jeu
```
