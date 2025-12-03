#!/bin/bash

# Script para executar o app Dash com o ambiente virtual ativado

cd "$(dirname "$0")"

# Ativa o ambiente virtual
source venv/bin/activate

# Executa o app
python app.py

