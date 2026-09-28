#!/bin/bash
# Double-cliquer sur ce fichier (Mac) ou le lancer dans un terminal (Linux).
cd "$(dirname "$0")" || exit 1
if command -v python3 > /dev/null; then
  python3 app.py "$@"
else
  echo "Python 3 est introuvable : https://www.python.org/downloads/"
  read -r -p "Appuyez sur Entrée pour fermer..."
fi
