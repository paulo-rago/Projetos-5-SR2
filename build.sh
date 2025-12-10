#!/bin/bash

# Script de build para deploy no Render
# Instala dependências Python, Node.js e faz build do React

set -e  # Para o script se houver erro

echo "🔨 Iniciando build para produção..."

# 1. Instalar dependências Python
echo "📦 Instalando dependências Python..."
pip install -r requirements.txt

# 2. Instalar Node.js se não estiver disponível
if ! command -v node &> /dev/null; then
    echo "📦 Instalando Node.js..."
    # Render já tem Node.js disponível, mas verificamos
    node --version || echo "⚠️ Node.js não encontrado"
fi

# 3. Instalar dependências do React
echo "📦 Instalando dependências React..."
cd tela
npm install --production=false

# 4. Fazer build do React
echo "🏗️  Fazendo build do React..."
npm run build

# 5. Verificar se o build foi bem-sucedido
if [ ! -d "../tela_build" ] || [ ! -f "../tela_build/index.html" ]; then
    echo "❌ Erro: Build do React falhou!"
    exit 1
fi

echo "✅ Build do React concluído com sucesso!"

# 6. Voltar para a raiz
cd ..

echo "✅ Build completo! Pronto para deploy."

