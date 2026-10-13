# Feuille de route BDD Pubs

> Pour la session Claude Code qui reprend : lire d'abord [`CLAUDE.md`](../CLAUDE.md), lancer
> `bash tests/lancer_tests.sh` (tout doit passer), puis traiter les points ci-dessous **dans
> l'ordre conseillé**, un lot à la fois : code + tests + mode d'emploi + `APP_VERSION` + push,
> puis cocher la case ici. Poser les « questions ouvertes » au propriétaire **avant** de coder les
> points concernés (il répond en français, à l'oral, souvent sur téléphone : questions courtes).

État au 13/10/2026 : version `2026.10.13.2`, tous les tests passent, release publiée.

## Demandes du testeur (reçues le 13/10/2026)

Liste d'origine, telle que transmise :

> Lecture romaji automatique · Graphiques de complétude · Connecté à une base de données de jeux si
> possible (désactivable) : voir API · Compteur de nombre de pages (avec moyenne par magazine par
> exemple) · Ajouter des filtres pour des statistiques (éditeur / type de jeu / année / licence /
> plateforme...) · Si possible, proposer un onglet « liste de magazines » où il y aurait une base de
> données (que je pourrais remplir quand je le peux) avec la liste de magazines / publications qui
> ont existé au Japon, même si je ne les ai pas. Ça permet aussi de voir à quel niveau on est dans
> la collection (genre « il me manque encore 100 magazines de Sega Saturn magazine » etc) · Applet à
> réduire pour le faire tenir sur une page d'un 14 pouces · Fonction d'import à inclure ·
> « Publicités » au lieu de « Parutions » dans l'onglet « magazines » · Bug de fermeture quand on
> laisse trop longtemps sans toucher au programme · Fonction retour (par exemple quand on se trompe
> sur le nombre de pages d'une pub, et qu'on veut modifier ça, après la modification on doit
> retourner dans l'onglet magazine, puis numéro, etc.) · Miniature photo qui coupe un peu trop les
> photos : revoir ça ? Ou au moins proposer qu'en cliquant dessus, il y ait la photo non tronquée ·
> Possibilité de mettre une date plus complexe pour les magazines (exemple, il y a pas mal de
> magazines hebdomadaires au Japon qui ont des dates du style 8 et 15 avril car ce sont des numéros
> spéciaux qui courent sur deux semaines, comme les magazines juillet-août en France)

Consigne du propriétaire : **pas d'IA si on peut s'en passer** (aucun point ci-dessous n'en a besoin).

## Ordre conseillé

### Lot 1 : corrections rapides d'ergonomie

Fait le 13/10 (`2026.10.13.1`, test `tests/ui/portable.js`). Bilan : vignettes en `contain` +
clic → photo entière ; « ← Retour » sur les fiches ; « ✎ pub » dans les tableaux de parutions, la
fenêtre d'une parution et l'aperçu de la saisie ; affichage resserré sous 1500 px de large ou
850 px de haut, saisie rapide sur 3 lignes compactes avec barre « Enregistrer » toujours visible ;
version affichée en haut à droite. Pour le bug de fermeture : demander au testeur la version
affichée (doit être ≥ 2026.09.30).

- [x] **« Publicités » au lieu de « Parutions » côté magazines.** Pages `pageMagazines`,
  `pageMagazine`, `pageIssue` (en-têtes de colonnes, tuiles, textes). Garder « parution » ailleurs
  sauf avis contraire (c'est le terme interne : une pub trouvée dans un numéro).
- [x] **Miniatures qui coupent les photos.** Passer les vignettes en `object-fit: contain` (fond
  neutre) : `.ad-card .img img`, `.gallery img`, `.ad-tile .im img`, `.thumb-img`, `.opt-thumb`.
  Et un clic sur toute vignette ouvre la photo entière (`lightbox`). Sur la carte de la page Pubs
  (qui est un lien), l'image ouvre la photo, le reste de la carte ouvre la fiche. Vérifier par
  capture avec une image très allongée (scan double page) et une très haute.
- [x] **Fonction retour / modifier sur place.** (a) Bouton « ← Retour » (`history.back()`) dans
  l'en-tête des fiches (pub, jeu, magazine, numéro) quand on vient d'une autre page de l'appli.
  (b) Pouvoir corriger la pub (nb de pages, description, plateformes…) **sans quitter la page
  courante** : bouton « ✎ Modifier la pub » dans la fenêtre de modification d'une parution
  (`openAppearanceForm`), dans l'aperçu de la saisie rapide (`showAd`) et dans les lignes des
  tableaux (`appTable`) → ouvre `openAdForm` en fenêtre, puis rafraîchit la page en place.
- [x] **Tenir sur un écran 14 pouces** (≈ 1280×720 à 1366×768 utiles). Densifier : marges, tailles
  de police et de boutons, en-tête sur une ligne (menu plus compact, éventuellement icônes +
  libellés courts), saisie rapide et grille de miniatures visibles sans défiler. Tester par
  captures en 1280×720 et 1366×768 (et vérifier que rien ne déborde sur téléphone :
  `tests/ui/affichage.js`). Option à envisager : bouton « affichage compact » mémorisé.
- [x] **Bug de fermeture après une longue inactivité.** Normalement **corrigé** le 30/09
  (`2026.09.30` : l'appli reste lancée jusqu'à « Quitter », la page se reconnecte seule).
  Le testeur utilise peut-être une version antérieure. À faire : afficher le **numéro de version**
  dans l'appli (pied de page ou page Export, valeur `APP_VERSION` via `/api/ping`) pour pouvoir le
  lui demander ; s'il a la dernière version et que ça arrive encore, lui demander ce qu'il voit
  exactement (message « BDD Pubs est arrêtée » ? onglet rechargé ? PC en veille ?) et le contenu
  de `%LOCALAPPDATA%\BDD Pubs\data\journal.txt`.

### Lot 2 : dates de magazines plus riches

- [x] **Dates du type « 8 et 15 avril 1997 », « juillet-août 1996 ».** Garder `issues.date`
  (AAAA, AAAA-MM ou AAAA-MM-JJ : sert au tri, au filtre par année, aux statistiques) et ajouter
  une colonne `issues.date_label` (texte libre, affiché tel quel). Dans les formulaires, **un seul
  champ « Date de parution » en texte libre** : le serveur en déduit `date` (premier jour reconnu)
  et garde le texte d'origine dans `date_label` si ce n'est pas déjà une date ISO. Analyseur à
  écrire (français : noms de mois, « et », « - », « / », jj/mm/aaaa, aaaa-mm-jj ; tests unitaires
  sur une vingtaine de formes). Afficher `date_label || date` partout (tableaux, fiches, CSV).
  Migration `SCHEMA_V3` (voir le lot 3 pour regrouper les colonnes ajoutées).

### Lot 3 : statistiques, pages, complétude, catalogue de magazines

Fait le 13/10 avec le lot 2 (`2026.10.13.2`, migration `SCHEMA_V3` qui ajoute aussi `games.romaji`
et `games.wikidata` pour le lot 5). Tests : `tests/test_api.py` (analyseur de dates sur ~20 formes,
statistiques, catalogue, mise à jour d'une base V2) et `tests/ui/catalogue_stats.js`.
Réalisé : page **Statistiques** (`/api/stats?par=…` + filtres de `search_where`), page
**Catalogue** (`#/catalogue`, `/api/magazines/<id>/generer`), pages de pub et moyenne par numéro
(fiches magazine/numéro, liste des magazines), jauge + barres par année (CSS, sans bibliothèque :
la compétence `dataviz` n'était pas disponible dans la session). L'accueil ne compte que les
numéros possédés. Le menu « Séries & plateformes » s'appelle maintenant « Listes ».

Ces points partagent les mêmes ajouts au modèle de données : les concevoir ensemble, **une seule
migration** (`SCHEMA_V3`, avec `date_label` du lot 2 si pas encore fait).

Ajouts proposés :
- `games.genre` (« type de jeu » : RPG, action, simulation…, liste libre avec suggestions des
  valeurs déjà utilisées), `games.licence` (licence / franchise au sens large : Dragon Ball,
  Gundam, Disney… — distincte de la « série » de jeux).
- `issues.pages` (nombre de pages du numéro), `issues.owned` (1 = possédé, 0 = connu mais pas
  possédé ; défaut 1 pour l'existant et la saisie rapide).
- `magazines` : `start_year`, `end_year`, `total_issues` (nombre de numéros parus, si connu),
  éventuellement `platform` (magazine dédié à une console).

Points de la liste :
- [x] **Compteur de pages** : total des pages de pub (somme de `ads.pages` sur les parutions),
  moyenne de pages de pub par numéro et par magazine, part de la pagination si `issues.pages` est
  renseigné. Affichage : fiche magazine, fiche numéro, page Statistiques.
- [x] **Statistiques avec filtres** : nouvelle page « Statistiques » (menu) avec filtres combinables
  (éditeur, genre, année de sortie du jeu / année de parution, licence, série, plateforme,
  magazine, en vente) et regroupements (par éditeur, par plateforme, par année, par magazine…) :
  nombre de pubs, de parutions, de pages. Réutiliser le moteur de `search()` pour les filtres.
- [x] **Graphiques de complétude** : par magazine, numéros possédés / numéros parus
  (`total_issues` ou numéros du catalogue), par année ; jauges et barres. Charger d'abord la
  compétence `dataviz` avant d'écrire les graphiques. **Sans bibliothèque externe** (SVG fait
  main dans `app.js`), lisibles en thème clair et sombre.
- [x] **Onglet « Liste de magazines » (catalogue)** : tous les magazines qui ont existé, même non
  possédés ; pour chacun, la liste des numéros connus avec leur état possédé / manquant, et
  « il me manque N numéros ». Outil « Générer les numéros 1 à N » (crée des numéros `owned=0`),
  bascule possédé/manquant d'un clic. La saisie rapide marque un numéro « possédé » quand on y
  saisit une pub. Le testeur remplira lui-même le catalogue (ne pas inventer de liste de magazines
  ou de numéros) ; l'import (lot 4) servira à le remplir en masse.

### Lot 4 : import

- [ ] **Fonction d'import.** Déjà là : import d'un projet exporté (ZIP) et « Tout restaurer ».
  Manque : **import de listes depuis Excel/CSV** (jeux, magazines + numéros du catalogue,
  parutions). Proposition : page « Importer » : choisir le type, déposer un fichier `.csv`
  (séparateur `;` ou `,` détecté, UTF-8 avec ou sans BOM) **ou `.xlsx`** (lecture minimale avec
  `zipfile` + XML, sans dépendance), aperçu des premières lignes avec correspondance des colonnes,
  création des éléments manquants (magazine, jeu, plateforme…), rapport « N créés, N déjà
  présents, N erreurs ». Mêmes colonnes que les exports CSV (aller-retour possible).
  **Question ouverte** : le testeur a-t-il un fichier à importer (son ancien Excel ?) — demander
  un exemple pour calibrer.

### Lot 5 : données externes

- [ ] **Lecture romaji automatique** : remplir automatiquement un champ « titre en romaji »
  (`games.romaji`) à partir du titre original japonais, modifiable ; recherche aussi sur ce champ.
  Kana → romaji : table maison (Hepburn), sans dépendance. Kanji → romaji : il faut un
  dictionnaire ; candidat `pykakasi` (disponible sur PyPI depuis l'environnement ; **licence
  GPL v3**, à signaler au propriétaire puisque le dépôt est public et l'exe distribué) ; il serait
  embarqué dans l'exe (`pip install` dans le workflow) et **facultatif** pour le `.pyw`
  (appli fonctionnelle sans, romaji partiel). Alternative sans licence GPL : `cutlet` + `fugashi`
  + `unidic-lite` (plus lourd).
  **Question ouverte** : quel champ doit recevoir le romaji (titre original seulement ?) et
  système souhaité (Hepburn ?).
- [ ] **Base de données de jeux en ligne (désactivable)** : à la création d'un jeu, proposer des
  fiches trouvées en ligne pour pré-remplir titre, titre japonais, éditeur, année, série,
  plateformes, genre. Source proposée : **Wikidata** (gratuit, sans clé, données CC0 ; API
  `wbsearchentities` puis `wbgetentities` : P400 plateforme, P123 éditeur, P577 date, P179 série,
  P136 genre, libellé `ja`). Alternatives à clé : IGDB (compte Twitch), MobyGames (payant), RAWG.
  Réglage « Rechercher les jeux en ligne » (désactivé par défaut ?), appels faits par le serveur
  (pas le navigateur), délai court, échec silencieux hors ligne. **Wikidata est bloqué depuis
  l'environnement Claude Code web** : écrire les tests avec des réponses enregistrées
  (fichiers JSON d'exemple) et faire valider en vrai par le propriétaire.
  **Question ouverte** : activée par défaut ou non ? La couverture des jeux japonais anciens par
  Wikidata est inégale : prévenir le testeur.

## Déjà fait (historique résumé)

- 27/09 : modèle Excel, puis application locale (Python + SQLite + interface web), images,
  recherche croisée, exports CSV, sauvegarde ZIP.
- 28/09 : lancement sans fenêtre (`.pyw`, `.exe` via GitHub Actions), plusieurs plateformes par
  pub, simplification des images dans la saisie rapide.
- 29/09 : projets (projet de base, démo, export/import), remplacement automatique d'une ancienne
  version lancée, plus d'accès au registre, version « dossier » de l'exe, correction de la boucle
  « Jeu obligatoire » sur Android, saisie « jeu puis miniature », release à lien fixe.
- 30/09 : l'appli reste lancée jusqu'à « Quitter » ; Tout exporter / Tout restaurer.
- 06/10 : données à un emplacement fixe, reprise automatique des anciennes données, sauvegarde
  automatique quotidienne (incrémentale pour les photos), restauration en un clic.
- 13/10 : `CLAUDE.md`, cette feuille de route, tests automatiques dans `tests/`.
- 13/10 : lot 1 (ergonomie, écran de portable, retour, modifier la pub sur place, version affichée).
- 13/10 : lots 2 et 3 (dates libres, statistiques, compteur de pages, catalogue et complétude).
