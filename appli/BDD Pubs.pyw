# BDD Pubs : double-cliquer sur ce fichier pour lancer l'application (Windows, avec Python installé).
# Aucune fenêtre noire : l'application s'ouvre dans le navigateur et s'arrête toute seule
# quand on ferme son dernier onglet (ou avec le bouton « Quitter »).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app  # noqa: E402

app.main([])
