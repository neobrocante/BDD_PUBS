# BDD Pubs : l'application

Application locale (dans le navigateur, sur `http://localhost:8765`) pour référencer les pubs de
jeux vidéo trouvées dans les magazines, avec leurs images.

Aucune installation à part **Python 3** (gratuit). Pas d'Internet nécessaire, pas de compte :
tout reste sur l'ordinateur, dans le dossier `data`.

## Installation (une seule fois)

1. Installer Python 3 : <https://www.python.org/downloads/>
   - Sous Windows, **cocher « Add python.exe to PATH »** au début de l'installation.
2. Copier ce dossier `appli` où vous voulez (Documents, bureau…).

## Lancer

- **Windows** : double-cliquer sur `Lancer BDD Pubs (Windows).bat`
- **Mac** : double-cliquer sur `Lancer BDD Pubs (Mac-Linux).command`
  (la 1re fois : clic droit > Ouvrir, pour passer l'avertissement de sécurité)
- **Ou**, dans un terminal : `python app.py`

Une fenêtre noire s'ouvre (c'est le serveur, la laisser ouverte) et le navigateur s'ouvre sur
l'application. Pour arrêter : fermer la fenêtre noire.

## Ce qu'on peut faire

| Page | Pour quoi faire |
|---|---|
| **Saisie rapide** | Choisir un magazine + un numéro, puis enchaîner les pubs trouvées dedans : pub, page, en vente ○/×, remarques, photo. Les magazines, numéros, jeux, séries et pubs manquants se créent au passage. |
| **Recherche** | Recherche croisée : magazine, numéro, année, jeu, série, plateforme, n° de pub, en vente, mot-clé. Statistiques + export CSV du résultat. |
| **Pubs** | Galerie de toutes les pubs (un visuel = une pub, avec un n° unique). Fiche : images, et **tous les magazines où on la trouve**. |
| **Jeux** | Liste triable (nb de pubs, de parutions, 1re parution). Fiche : toutes ses pubs et toutes ses parutions. |
| **Magazines** | Magazines > numéros > **les pubs de chaque numéro**, avec la couverture. |
| **Séries & plateformes** | Les listes de référence (plateformes japonaises déjà remplies). |
| **Export** | CSV pour Excel (toutes les tables) et **sauvegarde complète en ZIP** (base + images). |

### Images

Sur chaque pub, numéro (couverture) ou parution (photo de l'exemplaire) :
**glisser-déposer**, **cliquer** pour choisir un fichier, ou **coller** une capture (Ctrl+V).
Les miniatures sont créées automatiquement ; un clic sur une image l'affiche en grand (flèches
← → pour passer à la suivante). L'étoile ★ choisit l'image principale.

### Saisie au clavier

Dans la saisie rapide : taper le nom du jeu dans « Pub » → `Entrée` pour choisir → `Tab` →
page → `Entrée` pour enregistrer. Le magazine et le numéro restent en place pour la pub suivante.

## Utiliser le téléphone pour prendre les pubs en photo

Lancer avec l'option réseau : `python app.py --reseau`. L'adresse à ouvrir sur le téléphone
(même Wi-Fi) s'affiche dans la fenêtre noire, par ex. `http://192.168.1.20:8765`. Dans le
champ image, le téléphone propose alors d'utiliser l'appareil photo.
(À ne faire que sur un réseau de confiance : il n'y a pas de mot de passe.)

## Sauvegardes

- À chaque démarrage, une copie de la base est faite dans `data/sauvegardes` (15 dernières).
- Page **Export** > « Télécharger la sauvegarde » : un ZIP avec tout (base + images), à garder
  ailleurs (clé USB, cloud…).
- **Restaurer / changer d'ordinateur** : fermer l'application, dézipper la sauvegarde dans le
  dossier de l'application (elle contient le dossier `data`), relancer.

## Pour aller plus loin (technique)

- `app.py` : serveur Python, bibliothèque standard uniquement ; base SQLite `data/bdd_pubs.sqlite`.
- `static/` : l'interface (HTML/CSS/JavaScript, sans dépendance ni connexion Internet).
- Options : `--port 8766`, `--no-browser`, `--reseau`, `--demo` (données d'exemple si la base est vide).
  Variable `BDD_PUBS_DATA` pour placer les données ailleurs.
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
