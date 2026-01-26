#!/bin/bash
set -e

PROJECT_DIR="/" #COLOQUE AQUI O CAMINHO PARA A PASTA DO DAILY-REQUESTS-REPORT
PYTHON="/usr/bin/python3"

cd "$PROJECT_DIR"

# Carrega as variáveis do .env
export $(grep -v '^#' .env | xargs)

# Executa o projeto
"$PYTHON" -m scripts.run
