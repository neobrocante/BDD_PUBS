# BDD Pubs : l'application

Application locale (dans le navigateur, sur `http://localhost:8765`) pour référencer les pubs de
jeux vidéo trouvées dans les magazines, avec leurs images.

Rien à installer avec l'exécutable Windows (sinon, Python 3). Pas d'Internet nécessaire, pas de
compte : tout reste sur l'ordinateur, dans le dossier `data`.

## Lancer l'application

### Windows, sans rien installer : `BDD Pubs.exe`

Double-cliquer sur **`BDD Pubs.exe`**. L'application s'ouvre dans le navigateur, sans aucune
fenêtre noire.

- 1er lancement : si Windows affiche « Windows a protégé votre ordinateur », cliquer sur
  « Informations complémentaires » puis « Exécuter quand même » (l'exécutable n'est pas signé).
- Les données sont dans le dossier `data`, créé à côté de l'exécutable : garder les deux ensemble.
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

Pour passer de l'une à l'autre en gardant ses données : fermer l'application, puis copier le
dossier `data` à côté du nouveau `BDD Pubs.exe`.

### Avec Python installé : `BDD Pubs.pyw`

1. Installer Python 3 : <https://www.python.org/downloads/>
   (sous Windows, **cocher « Add python.exe to PATH »**).
2. Double-cliquer sur **`BDD Pubs.pyw`** : même fonctionnement que l'exécutable, sans fenêtre noire.

Sur Mac : double-cliquer sur `Lancer BDD Pubs (Mac-Linux).command` (la 1re fois : clic droit >
Ouvrir). Ou, dans un terminal : `python3 app.py`.

### Arrêt

Rien à faire : **l'application s'arrête toute seule quand on ferme son dernier onglet**
(quelques secondes après ; recharger la page ou ouvrir un 2e onglet ne l'arrête pas).
On peut aussi cliquer sur **⏻ Quitter** en haut à droite.
Double-cliquer alors qu'elle tourne déjà rouvre simplement l'onglet.

## Ce qu'on peut faire

| Page | Pour quoi faire |
|---|---|
| **Saisie rapide** | Choisir un magazine + un numéro, puis enchaîner les pubs trouvées dedans : pub, page, en vente ○/×, remarques, photo. Les magazines, numéros, jeux, séries et pubs manquants se créent au passage. |
| **Recherche** | Recherche croisée : magazine, numéro, année, jeu, série, plateforme, n° de pub, en vente, mot-clé. Statistiques + export CSV du résultat. |
| **Pubs** | Galerie de toutes les pubs (un visuel = une pub, avec un n° unique, une ou **plusieurs plateformes** cochées). Fiche : images, et **tous les magazines où on la trouve**. |
| **Jeux** | Liste triable (nb de pubs, de parutions, 1re parution). Fiche : toutes ses pubs et toutes ses parutions. |
| **Magazines** | Magazines > numéros > **les pubs de chaque numéro**, avec la couverture. |
| **Séries & plateformes** | Les listes de référence (plateformes japonaises déjà remplies). |
| **Export** | CSV pour Excel (toutes les tables) et **sauvegarde complète en ZIP** (base + images). |

### Images

L'image d'une pub se met **sur la pub** : une même pub parue dans 5 magazines n'a besoin que
d'une image, visible depuis ses 5 parutions.

- Nouvelle pub : zone « Image de la pub » dans sa fenêtre de création.
- Pub existante sans image : dans la saisie rapide, une zone apparaît dans son aperçu
  (sinon, depuis sa fiche).
- Couverture d'un numéro : dans la saisie rapide (à droite) ou sur la fiche du numéro.
- Photo de *votre* exemplaire (état, pour la vente), facultatif : bouton ✎ d'une parution.

Glisser-déposer, cliquer pour choisir un fichier, ou coller une capture (Ctrl+V). Les miniatures
sont créées automatiquement ; un clic sur une image l'affiche en grand (flèches ← →). L'étoile ★
choisit l'image principale.

### Saisie rapide : le jeu, puis la pub reconnue à sa miniature

1. Taper les premières lettres du **jeu** (les titres qui commencent par ces lettres viennent en
   premier). Jeu inconnu : « ＋ Nouveau jeu », puis la fenêtre « Nouvelle pub » s'ouvre d'elle-même.
2. Les **miniatures de toutes les pubs de ce jeu** s'affichent : toucher celle qu'on reconnaît
   (🔍 pour l'agrandir), ou « ＋ Nouvelle pub » si c'en est une autre.
3. Page, en vente ○/×, remarques, **Enregistrer**. Le magazine et le numéro restent en place
   pour la pub suivante.

Au clavier : lettres du jeu → `Entrée` → `Tab` jusqu'à la miniature → `Entrée` → page → `Entrée`.

## Projets

Menu **📁** en haut à gauche. Au lancement, l'application ouvre toujours le même projet
(au départ : « Projet principal », renommable) ; rien à choisir.

Page **Projets** : créer un projet vide, créer le **projet de démonstration** (exemples fictifs,
avec affiches), renommer, choisir le projet ouvert au lancement, **exporter** un projet seul
(ZIP : base + images), **importer** un ZIP exporté (ou une sauvegarde complète), supprimer un
projet (sauf le projet de base). Chaque onglet reste sur son projet (adresse `/p/<projet>/`).

Sur le disque : le projet de base est directement dans `data/`, les autres dans
`data/projets/<projet>/`, la liste dans `data/projets.json`.

## Utiliser le téléphone pour prendre les pubs en photo

Page **Export** > cocher « Rendre l'application accessible depuis le téléphone ». L'adresse à
ouvrir sur le téléphone (même Wi-Fi) s'affiche, par ex. `http://192.168.1.20:8765`. Dans les
champs image, le téléphone propose alors l'appareil photo. Le réglage est retenu pour les
lancements suivants. (Pas de mot de passe : à n'activer que sur un réseau de confiance.)

## Sauvegardes

- À chaque démarrage, une copie de la base est faite dans `data/sauvegardes` (15 dernières).
- Page **Export** > « Télécharger la sauvegarde » : un ZIP avec tout (base + images), à garder
  ailleurs (clé USB, cloud…).
- **Restaurer / changer d'ordinateur** : fermer l'application, dézipper la sauvegarde dans le
  dossier de l'application (elle contient le dossier `data`), relancer.

## Pour aller plus loin (technique)

- `app.py` : serveur Python, bibliothèque standard uniquement ; base SQLite `data/bdd_pubs.sqlite`.
- `static/` : l'interface (HTML/CSS/JavaScript, sans dépendance ni connexion Internet).
- Options : `--port 8766`, `--no-browser` (et pas d'arrêt automatique), `--sans-arret-auto`,
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
