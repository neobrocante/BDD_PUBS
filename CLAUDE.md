# BDD Pubs : guide pour Claude Code

À lire avant toute modification. **Le travail en cours et à venir est dans
[`docs/FEUILLE_DE_ROUTE.md`](docs/FEUILLE_DE_ROUTE.md)** : commencer par là.

## Le projet en deux mots

Application de référencement des **publicités de jeux vidéo parues dans les magazines japonais**
(Famitsu, Dengeki…), pour un collectionneur. On saisit, pour chaque numéro de magazine, les pubs
qu'il contient (jeu, plateformes, page, photo/scan, en vente ○/×), puis on fait des recherches
croisées (quelles pubs dans tel numéro, où trouver telle pub…).

- **Utilisateurs** : non-développeurs, sous **Windows** (antivirus Avast), parfois sur
  **téléphone Android** (accès par le Wi-Fi). Le propriétaire du dépôt transmet les retours d'un
  testeur qui l'utilise au quotidien avec beaucoup de données (des milliers de scans à terme).
- **Langue** : tout est en **français** (interface, messages, commits, documentation, échanges).
  Expliquer simplement, sans jargon ; dire clairement ce qui a été testé et ce qui ne l'a pas été.

## Organisation du dépôt

```
appli/app.py            serveur (Python, bibliothèque standard UNIQUEMENT) ~2200 lignes
appli/static/app.js     interface (JavaScript sans bibliothèque ni CDN) ~1900 lignes
appli/static/style.css  styles (thème clair/sombre automatique)
appli/static/index.html coquille de la page (chemins absolus /app.js, /style.css)
appli/BDD Pubs.pyw      lanceur sans fenêtre (Python installé)
appli/icone.ico         icône de l'exécutable
appli/README.md         mode d'emploi utilisateur (à tenir à jour)
tests/                  tests (voir plus bas)
.github/workflows/executable-windows.yml  construit + teste + publie l'exécutable Windows
BDD_Pubs.xlsx, generer_bdd_pubs.py        ancienne version « Excel » (historique, ne plus faire évoluer)
```

Branche de travail : `claude/ads-magazine-reference-system-qnxidy` (c'est aussi la branche par
défaut du dépôt). Dépôt **public**.

## Architecture

### Serveur (`appli/app.py`)
- `ThreadingHTTPServer` sur `127.0.0.1:8765` (+ écoute Wi-Fi optionnelle, classe `Network`).
  Une connexion SQLite **par requête** (`connect()`), `PRAGMA foreign_keys=ON`.
- **Schéma** : `SCHEMA_V1`, `SCHEMA_V2`… dans la liste `MIGRATIONS` (numéro dans
  `PRAGMA user_version`). **Pour changer la base : ajouter une étape à la fin de `MIGRATIONS`,
  ne jamais modifier une étape existante.** Puis `SPEC` (règles de saisie des champs), les
  requêtes `list_*`/`detail`/`search`, les exports CSV et le formulaire côté interface.
- Tables : `platforms`, `series`, `magazines`, `issues` (numéros), `games`, `ads` (une pub = un
  visuel), `ad_platforms` (plusieurs plateformes par pub), `appearances` (une pub trouvée dans un
  numéro = « parution »), `images` (rattachées à `ads` / `issues` / `appearances` / `games`).
  `ads.platform_id` est un reste de V1, inutilisé.
- V3 : `issues.date_label` (date telle qu'écrite, « 8 et 15 avril 1997 » ; `issues.date` reste
  la date triable déduite par `parse_issue_date`), `issues.pages`, `issues.owned` (catalogue :
  1 possédé / 0 manquant ; saisir une pub dans un numéro le passe à 1), `games.genre|licence|
  romaji|wikidata`, `magazines.start_year|end_year|total_issues|platform_id`.
- **Projets** : plusieurs bases séparées. Liste dans `data/projets.json`. Le projet de base
  `principal` est à la racine de `data/`, les autres dans `data/projets/<id>/`. Le projet d'une
  requête vient de l'en-tête `X-Projet` (ou `?projet=`), sinon du projet « ouvert au lancement ».
  Contexte par fil d'exécution : `cur()` / `use_project()` / `open_project()`.
  Les images sont servies sous `/p/<id>/images/…` et `/p/<id>/miniatures/…`.
- **Emplacement des données** (`DATA_DIR`) : fixe, **jamais à côté du programme** —
  `%LOCALAPPDATA%\BDD Pubs\data` (Windows), `~/Library/Application Support/BDD Pubs/data` (Mac),
  `~/.local/share/bdd-pubs/data` (Linux). Variable `BDD_PUBS_DATA` pour l'imposer (tests).
  Au démarrage, `auto_migrate()` reprend (copie) les données d'une ancienne version si
  l'emplacement fixe est vide.
- **Protection des données** : sauvegarde automatique quotidienne (`auto_backup`, `backup_loop`)
  dans `Documents\BDD Pubs - sauvegardes` (modifiable, variable `BDD_PUBS_SAUVEGARDES` pour les
  tests) : bases datées (30 gardées) + photos copiées une seule fois (incrémental). Copie de base à
  chaque démarrage (`backup_on_start`). « Tout exporter / Tout restaurer » (ZIP de tous les
  projets). Avant toute restauration/reprise : `safety_copy()`.
- **Une seule instance** : au lancement, `running_instance()` interroge `/api/ping`. Même version
  (`BUILD`) et même dossier → on rouvre juste l'onglet ; sinon on demande à l'autre de s'arrêter
  (`/api/quitter`) et on prend sa place. **Augmenter `APP_VERSION` à chaque livraison.**
- L'application **reste lancée** jusqu'au bouton « Quitter » (pas d'arrêt quand on ferme
  l'onglet : les navigateurs endorment les onglets inactifs). `--arret-auto` pour l'ancien mode.
- Routes : `/api/<table>[/<id>]` (CRUD générique sur `SPEC`), `/api/search` (filtres dans
  `search_where`, partagés avec `/api/stats?par=…`), `/api/magazines/<id>/generer` (catalogue),
  `/api/import/lire|appliquer` (classe `Importer`, `read_xlsx` maison), `/api/romaji[/remplir]`,
  `/api/enligne?q=` (Wikidata, `search_games_online`), `/api/reglages`, `/api/dashboard`,
  `/api/meta`, `/api/images`, `/api/export/<nom>.csv`, `/api/projets/...` (liste, création,
  `import`, `<id>/export.zip`, `tout.zip`, `restaurer`), `/api/donnees/...` (état, `sauvegarder`,
  `dossier`, `restaurer`, `recherche`, `reprendre`), `/api/ping|bye|quitter|reseau`.

### Interface (`appli/static/app.js`)
- Application d'une page, routeur sur le `#` (`ROUTES`), chaque page = `async function pageXxx(view)`.
- Composants maison : `combo()` (liste avec recherche + création à la volée), `formModal()`,
  `platformPicker()`, `galleryBlock()`, `dropzone()` (glisser-déposer / Ctrl+V), `lightbox()`,
  `appTable()` (tableau des parutions).
- Le projet de l'onglet vient de l'adresse `/p/<id>/` (constante `PROJ`), envoyé en `X-Projet`.
- Miniatures **fabriquées par le navigateur** (canvas, 520 px) et envoyées avec l'original
  (base64 en JSON).
- Saisie rapide (`pageEntry`) : magazine + numéro, puis **jeu → grille des miniatures de ses pubs
  → on touche la bonne** (ou « Nouvelle pub »), page, en vente ○/×. Elle doit tenir sur un écran
  1280×720 (test `tests/ui/portable.js`, styles « portable » sous 1500 px / 850 px).
- Pages ajoutées le 13/10 : `pageCatalogue` / `pageCatalogueMag`, `pageStats`, `importBlock`
  (page Import / Export), bouton `backBtn()` dans les fils d'Ariane, `editAdInPlace()`.

## Règles à respecter (leçons apprises, ne pas les défaire)

1. **Aucune dépendance** : serveur en bibliothèque standard Python, interface sans bibliothèque ni
   CDN (fonctionne hors ligne, l'exécutable reste simple). Si une dépendance devient vraiment
   nécessaire (ex. lecture romaji), elle doit être **facultative** (l'appli marche sans).
2. **Les données de l'utilisateur sont sacrées** : jamais d'écrasement sans copie de sécurité,
   jamais de données dans le ZIP publié (le workflow le vérifie), migrations uniquement par ajout.
3. **Pas d'accès au registre Windows ni au système** (un écran bleu lié à un pilote d'antivirus a
   eu lieu chez l'utilisateur) : ne pas utiliser le module `mimetypes` (table `CONTENT_TYPES` à la
   place), pas de `subprocess`/`ctypes`/`winreg`.
4. **Écrans tactiles** : dans `combo()`, le choix se fait sur `click` (pas `mousedown`) ; un
   événement `input` qui ne change pas le texte ne désélectionne pas (claviers Android) ; ne pas
   redonner le focus automatiquement sur téléphone (`TOUCH`).
5. **Connexions HTTP réutilisées** : si une route ne lit pas le corps de la requête, la connexion
   est fermée (`_consumed` dans `dispatch`) ; sinon la requête suivante est faussée.
6. Pas d'IA si on peut s'en passer (demande explicite du propriétaire).
7. Textes visibles : français simple ; « Publicités »/« pubs » côté magazines (voir feuille de route).

## Lancer, tester

```bash
python3 appli/app.py --no-browser --demo --port 8765     # appli avec données d'exemple
BDD_PUBS_DATA=/tmp/x BDD_PUBS_SAUVEGARDES=/tmp/y python3 appli/app.py --no-browser --demo   # base jetable
bash tests/lancer_tests.sh        # TOUS les tests (API + navigateur) sur une base temporaire
bash tests/lancer_tests.sh api    # tests API seulement
```

- `tests/test_api.py` : API complète (recherche, règles, images, exports, projets, Tout
  exporter/restaurer, sauvegarde automatique, reprise d'anciennes données dans un faux dossier
  utilisateur).
- `tests/ui/*.js` : Playwright (Chromium) — saisie rapide sur ordinateur et téléphone (dont le cas
  « clavier Android »), projets, affichage sans débordement sur téléphone. Playwright est
  installé globalement dans l'environnement Claude Code web (`npm root -g`).
- **Lancer tous les tests avant chaque livraison**, et ajouter un test pour chaque nouvelle
  fonction ou bug corrigé. Regarder aussi les captures d'écran quand l'interface change.

## Livrer une version

1. Augmenter `APP_VERSION` dans `appli/app.py` (sinon une ancienne instance lancée n'est pas remplacée).
2. Mettre à jour `appli/README.md` (mode d'emploi) et `docs/FEUILLE_DE_ROUTE.md` (cases cochées).
3. Commit en français, puis `git push -u origin claude/ads-magazine-reference-system-qnxidy`.
4. Le workflow GitHub construit l'exécutable Windows (fichier unique + version « dossier »), le
   **démarre et le teste sur Windows**, vérifie qu'aucune donnée n'est dans le paquet, puis
   remplace la release « derniere-version ». Lien fixe pour les utilisateurs :
   https://github.com/neobrocante/BDD_PUBS/releases/latest — vérifier que le workflow est vert.

## Limites de l'environnement Claude Code web (constatées)

- Wikidata (`www.wikidata.org`, `query.wikidata.org`) est **bloqué** par le proxy : la recherche
  en ligne n'est testée qu'avec `tests/wikidata_faux.json` (variable `BDD_PUBS_WIKIDATA_FAUX`,
  posée par `lancer_tests.sh`). PyPI est accessible (`pykakasi`, facultatif, s'y trouve).
- Le téléchargement des artefacts GitHub Actions est bloqué : on ne peut pas récupérer l'`.exe`
  construit ; on se fie au test Windows du workflow.
- Pas d'ordinateur Windows : les chemins `%LOCALAPPDATA%` / `Documents` ne sont testés que via
  leurs équivalents Linux (et le workflow Windows démarre l'exe avec `BDD_PUBS_DATA` imposé).
