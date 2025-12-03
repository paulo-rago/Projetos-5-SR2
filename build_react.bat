@echo off
REM Script para fazer build do React e integrar ao projeto Dash (Windows)

echo 🔨 Fazendo build do React...
cd tela

REM Verifica se node_modules existe
if not exist "node_modules" (
    echo 📦 Instalando dependências...
    call npm install
)

REM Faz o build
echo 🏗️  Compilando projeto...
call npm run build

if %errorlevel% equ 0 (
    echo ✅ Build concluído com sucesso!
    echo 📁 Arquivos gerados em: tela_build/
    echo.
    echo 🚀 Agora você pode executar o app.py e acessar a aba 'Tela React'
) else (
    echo ❌ Erro ao fazer build
    exit /b 1
)

