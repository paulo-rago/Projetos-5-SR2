#!/bin/bash

# Script para fazer build do React e integrar ao projeto Dash

echo "🔨 Fazendo build do React..."
cd tela

# Verifica se node_modules existe
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependências..."
    npm install
fi

# Faz o build
echo "🏗️  Compilando projeto..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Build concluído com sucesso!"
    echo "📁 Arquivos gerados em: tela_build/"
    echo ""
    echo "🚀 Agora você pode executar o app.py e acessar a aba 'Tela React'"
else
    echo "❌ Erro ao fazer build"
    exit 1
fi

