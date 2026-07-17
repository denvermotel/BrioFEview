#!/bin/bash
# Avvio di BrioFEview su macOS (per test, senza installer).
#
# Prima volta:
#   1. installare Python 3.11+ (https://www.python.org o: brew install python)
#   2. rendere eseguibile questo file:  chmod +x avvia_briofeview.command
#   3. al primo avvio le dipendenze vengono installate automaticamente
#
# Doppio clic dal Finder oppure da terminale: ./avvia_briofeview.command [file.xml]

set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || { echo "Python 3 non trovato. Installalo da python.org"; read -r -p "Premi Invio per chiudere..."; exit 1; }

# ambiente virtuale locale per non toccare il Python di sistema
if [ ! -d ".venv" ]; then
    echo "Prima esecuzione: creo l'ambiente virtuale e installo le dipendenze..."
    "$PY" -m venv .venv
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install -r requirements.txt
fi

exec ./.venv/bin/python -m visualizzatore "$@"
