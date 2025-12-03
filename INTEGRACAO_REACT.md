# Integração da Tela React

A tela React foi integrada ao projeto Dash sem alterar nenhum código anterior.

## Como usar

### 1. Fazer build do React

**Linux/Mac:**
```bash
./build_react.sh
```

**Windows:**
```bash
build_react.bat
```

**Ou manualmente:**
```bash
cd tela
npm install  # apenas na primeira vez
npm run build
```

### 2. Executar o app Dash

```bash
python app.py
```

### 3. Acessar a tela React

Após executar o app, acesse a aba **"Tela React"** no dashboard Dash.

Ou acesse diretamente: `http://localhost:8050/tela-react/`

## Estrutura

- **`tela/`** - Código fonte do React
- **`tela_build/`** - Arquivos compilados do React (gerado após o build)
- **`app.py`** - App Dash com integração do React (nova aba e rotas adicionadas)

## Notas

- O build do React gera os arquivos estáticos na pasta `tela_build/`
- A tela React é servida através do Flask na rota `/tela-react/`
- Nenhum código anterior foi alterado, apenas adicionadas novas funcionalidades

