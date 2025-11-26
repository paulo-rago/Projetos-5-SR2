import dash
from dash import dcc, html, Input, Output, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json
import base64
from pathlib import Path
import folium
from folium.plugins import HeatMap, MarkerCluster
from pyproj import Transformer
import numpy as np
import re
import hashlib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix, classification_report, 
    roc_curve, auc, precision_recall_curve, average_precision_score
)

# ============================================
# INICIALIZAR APP
# ============================================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True
)

server = app.server

# CSS customizado
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
            }
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            .btn-group > .btn {
                border-radius: 0;
            }
            .btn-group > .btn:first-child {
                border-top-left-radius: 8px;
                border-bottom-left-radius: 8px;
            }
            .btn-group > .btn:last-child {
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            /* Link style for footer */
            .footer-link {
                color: #9CA3AF;
                text-decoration: none;
                margin-bottom: 0.5rem;
                display: block;
                font-size: 0.9rem;
                transition: color 0.2s;
                cursor: pointer;
            }
            .footer-link:hover {
                color: #10B981;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# ============================================
# CARREGAR DADOS E CALCULAR MÉTRICAS
# ============================================

df_geral_file = Path("censo_arboreo_final_geral.csv")
metricas = None
df_geral = None

if df_geral_file.exists():
    print("📊 Carregando dataset completo...")
    df_geral = pd.read_csv(df_geral_file, low_memory=False)
    
    # --- 1. PRÉ-PROCESSAMENTO DE COORDENADAS ---
    try:
        if 'x' in df_geral.columns and 'y' in df_geral.columns:
            try:
                transformer = Transformer.from_crs("EPSG:31985", "EPSG:4326", always_xy=True)
            except:
                transformer = Transformer.from_crs("EPSG:32725", "EPSG:4326", always_xy=True)
            
            lon, lat = transformer.transform(df_geral['x'].values, df_geral['y'].values)
            df_geral['latitude'] = lat
            df_geral['longitude'] = lon
    except Exception as e:
        print(f"⚠️ Erro coordenadas: {e}")

    # --- 2. CÁLCULO DINÂMICO ---
    print("🔄 Calculando métricas...")
    try:
        # Totais Gerais
        total_arvores = len(df_geral)
        
        # ---------------------------------------------------------
        # CÁLCULO DE ESPÉCIES (Relativo ao total com espécie)
        # ---------------------------------------------------------
        top_especies_list = []
        especie_mais_comum = "N/A"
        especie_top_count = 0
        especie_top_pct = 0
        total_com_especie = 0
        num_especies = 0
        
        col_esp = 'nome_popular' if 'nome_popular' in df_geral.columns else ('especie' if 'especie' in df_geral.columns else None)
        
        if col_esp:
            # Conta apenas valores não nulos
            counts_esp = df_geral[col_esp].value_counts()
            num_especies = len(counts_esp)
            total_com_especie = counts_esp.sum() # Denominador correto: Soma das árvores identificadas
            
            if not counts_esp.empty:
                especie_mais_comum = counts_esp.index[0]
                especie_top_count = int(counts_esp.iloc[0])
                
                # Cálculo da porcentagem: (Top 1 / Total Identificadas) * 100
                if total_com_especie > 0:
                    especie_top_pct = (especie_top_count / total_com_especie) * 100
                
                # Monta lista Top 5 com a mesma lógica
                for nome, qtd in counts_esp.head(5).items():
                    pct_item = (qtd / total_com_especie) * 100 if total_com_especie > 0 else 0
                    top_especies_list.append({"nome": nome, "quantidade": int(qtd), "percentual": pct_item})

        # ---------------------------------------------------------
        # FITOSSANIDADE (Doentes+Mortas / Total Avaliadas)
        # ---------------------------------------------------------
        pct_atencao = 0
        total_avaliadas = 0
        
        # Ajuste aqui o nome da coluna conforme seu CSV final (ex: 'fitossanid_grupo' ou 'estado_fitossanitario')
        col_fito = 'fitossanid_grupo' if 'fitossanid_grupo' in df_geral.columns else None

        # Se não achar 'fitossanid_grupo', tenta outras opções comuns
        if not col_fito:
             for c in ['estado_fitossanitario', 'condicao_fisica', 'saude']:
                if c in df_geral.columns:
                    col_fito = c
                    break
        
        if col_fito:
            # 1. Normaliza para evitar erros de maiúsculas/minúsculas
            df_geral[col_fito] = df_geral[col_fito].astype(str).str.strip()
            
            # 2. Define o universo das AVALIADAS (Denominador)
            # Ignora nulos, vazios e quem está marcado explicitamente como "Não avaliada"
            filtro_avaliadas = (
                (df_geral[col_fito].notna()) & 
                (df_geral[col_fito] != '') & 
                (df_geral[col_fito] != 'nan') &
                (df_geral[col_fito] != 'Não avaliada')
            )
            df_avaliadas = df_geral[filtro_avaliadas]
            total_avaliadas = len(df_avaliadas)
            
            # 3. Define o grupo de ATENÇÃO (Numerador)
            # Ajuste os termos conforme os dados do seu Colab ('Injuriada', 'Morta')
            termos_criticos = ['Injuriada', 'Morta', 'Doente', 'Ruim', 'Péssima', 'Critica']
            
            # Filtra quem está na lista de termos críticos DENTRO das avaliadas
            df_criticas = df_avaliadas[df_avaliadas[col_fito].isin(termos_criticos)]
            total_criticas = len(df_criticas)
            
            # 4. Cálculo final
            if total_avaliadas > 0:
                pct_atencao = (total_criticas / total_avaliadas) * 100

        # ---------------------------------------------------------
        # OUTROS CÁLCULOS (Mantidos)
        # ---------------------------------------------------------
        
        # Altura
        altura_media = 0
        altura_max = 0
        col_altura = 'altura' if 'altura' in df_geral.columns else ('altura_total' if 'altura_total' in df_geral.columns else None)
        if col_altura:
            df_geral[col_altura] = pd.to_numeric(df_geral[col_altura].astype(str).str.replace(',', '.'), errors='coerce')
            df_alt_valida = df_geral[(df_geral[col_altura] > 0) & (df_geral[col_altura] < 60)]
            if not df_alt_valida.empty:
                altura_media = df_alt_valida[col_altura].mean()
                altura_max = df_alt_valida[col_altura].max()

        # Plantios Novos
        plantios_desde_2020 = 0
        col_data = 'data_plantio' if 'data_plantio' in df_geral.columns else None
        if col_data:
            df_geral[col_data] = pd.to_datetime(df_geral[col_data], dayfirst=True, errors='coerce')
            plantios_desde_2020 = len(df_geral[df_geral[col_data].dt.year >= 2020])

        # RPA Distribution
        distribuicao_rpa = {}
        if 'rpa' in df_geral.columns:
            rpa_counts = df_geral['rpa'].value_counts()
            for rpa_num, count in rpa_counts.items():
                rpa_key = str(int(rpa_num)) if pd.notna(rpa_num) and str(rpa_num).replace('.','').isdigit() else str(rpa_num)
                distribuicao_rpa[rpa_key] = {"nome": f"RPA {rpa_key}", "quantidade": int(count)}

        metricas = {
            "total_arvores": total_arvores,
            "pct_atencao": pct_atencao,
            "total_avaliadas": int(total_avaliadas),
            "especie_mais_comum": especie_mais_comum,
            "especie_top_count": especie_top_count,
            "especie_top_pct": especie_top_pct,
            "altura_media_m": altura_media,
            "altura_max_m": altura_max,
            "plantios_desde_2020": plantios_desde_2020,
            "num_especies": num_especies,
            "total_com_especie": int(total_com_especie),
            "distribuicao_rpa": distribuicao_rpa,
            "top_especies": top_especies_list
        }

    except Exception as e:
        print(f"❌ Erro calculo: {e}")
        metricas = None

    print(f"✅ Dados carregados!")
else:
    df_geral = None
    print("⚠️ Dataset não encontrado!")

# ============================================
# CORES
# ============================================
COLORS = {
    'primary': '#10B981',
    'primary_dark': '#059669',
    'dark': '#1F2937',
    'gray': '#6B7280',
    'light_gray': '#9CA3AF',
    'border': '#E5E7EB',
    'background': '#F9FAFB',
    'card_bg': '#FFFFFF'
}

RPA_COLORS = {
    'RPA 1': '#D32F2F', 
    'RPA 6': '#F57C00', 
    'RPA 2': '#FBC02D', 
    'RPA 5': '#AED581', 
    'RPA 4': '#43A047', 
    'RPA 3': '#1B5E20'
}

# ============================================
# FUNÇÃO DO FOOTER
# ============================================
def render_footer():
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div(html.I(className="fas fa-tree", style={'color': 'white', 'fontSize': '1.2rem'}), 
                                 style={'width': '40px', 'height': '40px', 'backgroundColor': '#10B981', 'borderRadius': '8px', 
                                        'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'marginRight': '12px'}),
                        html.Div([
                            html.H5("Verdefica", style={'color': 'white', 'fontWeight': 'bold', 'margin': 0, 'fontSize': '1.1rem'}),
                            html.Span("GovTech Dashboard", style={'color': '#9CA3AF', 'fontSize': '0.85rem'})
                        ])
                    ], className="d-flex align-items-center mb-3"),
                    html.P("Sistema de gestão e monitoramento da arborização urbana do Recife, promovendo transparência e participação cidadã.", 
                           style={'color': '#9CA3AF', 'fontSize': '0.9rem', 'lineHeight': '1.6'})
                ], width=12, lg=5, className="mb-4 mb-lg-0"),
                
                dbc.Col([
                    html.H6("Sobre", style={'color': 'white', 'fontWeight': 'bold', 'marginBottom': '1rem'}),
                    html.Div([
                        html.Span("O Projeto", id="link-projeto", className="footer-link"),
                        dbc.Tooltip("Iniciativa para mapear e preservar o patrimônio verde do Recife.", target="link-projeto"),
                        html.Span("Metodologia", id="link-metodologia", className="footer-link"),
                        dbc.Tooltip("Utilizamos inventário contínuo e imagens de satélite para análise.", target="link-metodologia"),
                        html.Span("Transparência", id="link-transparencia", className="footer-link"),
                        dbc.Tooltip("Todos os dados são auditáveis e abertos ao público.", target="link-transparencia"),
                    ])
                ], width=6, md=4, lg=2, className="mb-4"),
                
                dbc.Col([
                    html.H6("Parceiros", style={'color': 'white', 'fontWeight': 'bold', 'marginBottom': '1rem'}),
                    html.Div([
                        html.Span("Prefeitura do Recife", id="link-pref", className="footer-link"),
                        dbc.Tooltip("A Prefeitura é parceira fundamental na execução das políticas públicas.", target="link-pref"),
                        html.Span("Universidades", id="link-uni", className="footer-link"),
                        dbc.Tooltip("UFRPE e UFPE colaboram com pesquisa científica e validação.", target="link-uni"),
                        html.Span("Sociedade Civil", id="link-soc", className="footer-link"),
                        dbc.Tooltip("ONGs e grupos comunitários atuam na fiscalização e plantio.", target="link-soc"),
                    ])
                ], width=6, md=4, lg=2, className="mb-4"),
                
                dbc.Col([
                    html.H6("Recursos", style={'color': 'white', 'fontWeight': 'bold', 'marginBottom': '1rem'}),
                    html.Div([
                        html.Span("Dados Abertos", id="link-dados", className="footer-link"),
                        dbc.Tooltip("Baixe a base completa em CSV ou JSON para suas análises.", target="link-dados"),
                        html.Span("API", id="link-api", className="footer-link"),
                        dbc.Tooltip("Integre nosso sistema com suas aplicações via REST API.", target="link-api"),
                        html.Span("Contato", id="link-contato", className="footer-link"),
                        dbc.Tooltip("Fale com a equipe técnica ou reporte problemas.", target="link-contato"),
                    ])
                ], width=6, md=4, lg=3, className="mb-4"),
            ], className="py-5"),
            
            html.Hr(style={'borderColor': '#374151', 'opacity': 1}),
            
            html.Div("© 2024 Verdefica - Prefeitura do Recife. Todos os direitos reservados.", 
                     style={'color': '#6B7280', 'textAlign': 'center', 'padding': '1.5rem 0', 'fontSize': '0.85rem'})
            
        ], fluid=True, style={'maxWidth': '1400px'})
    ], style={'backgroundColor': '#111827', 'marginTop': 'auto'})

# ============================================
# LAYOUT
# ============================================

app.layout = html.Div([
    dbc.Container([
        # --- CABEÇALHO ---
        html.Div([
            html.Div([
                html.H1([
                    html.Span("Verde", style={'fontWeight': '400'}),
                    html.Span("fica", style={'fontWeight': '600'})
                ], style={
                    'color': COLORS['primary'],
                    'margin': 0, 
                    'fontSize': '2rem'
                }),
                html.P("Sistema de Gestão do Censo Arbóreo de Recife", style={
                    'color': COLORS['dark'],
                    'margin': 0,
                    'fontSize': '0.95rem',
                    'fontWeight': '400'
                })
            ])
        ], style={
            'background': 'white',
            'padding': '2rem 2.5rem',
            'borderRadius': '12px',
            'marginBottom': '2rem',
            'boxShadow': '0 4px 6px rgba(0, 0, 0, 0.05)',
            'border': f'1px solid {COLORS["border"]}'
        }),
        
        dcc.Tabs(id='tabs', value='dashboard', children=[
            dcc.Tab(label='Dashboard', value='dashboard'),
            dcc.Tab(label='Análise Estatística', value='analise'),
            dcc.Tab(label='Mapa', value='mapa'),
            dcc.Tab(label='Seletor de Espécies', value='especies'),
            dcc.Tab(label='Análises do Notebook', value='notebook'),
        ]),
        
        html.Div(id='tab-content', style={'marginTop': '2rem', 'marginBottom': '4rem'}),
                 
    ], fluid=True, style={
        'maxWidth': '1400px',
        'backgroundColor': COLORS['background'],
        'minHeight': 'calc(100vh - 300px)',
        'padding': '2rem'
    }),
    
    render_footer()
    
], style={'backgroundColor': COLORS['background']})

# ============================================
# CALLBACKS
# ============================================

@app.callback(
    Output('tab-content', 'children'),
    Input('tabs', 'value')
)
def render_content(tab):
    if tab == 'dashboard':
        return render_dashboard()
    elif tab == 'analise':
        return render_analise()
    elif tab == 'mapa':
        return render_mapa()
    elif tab == 'especies':
        return render_especies()
    elif tab == 'notebook':
        return render_notebook()
    else:
        return dbc.Alert("🚧 Em desenvolvimento...", color="info")

@app.callback(
    Output('tabs', 'value'),
    [Input('btn-ir-mapa', 'n_clicks'),
     Input('btn-ver-todas', 'n_clicks')],
    prevent_initial_call=True
)
def navegar_pelo_dashboard(btn_mapa, btn_especies):
    ctx = callback_context
    if not ctx.triggered:
        return dash.no_update
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    clicks = ctx.triggered[0]['value']

    if not clicks or clicks == 0:
        return dash.no_update
    
    if button_id == 'btn-ir-mapa':
        return 'mapa'
    elif button_id == 'btn-ver-todas':
        return 'especies'
        
    return dash.no_update

# ============================================
# FUNÇÕES DE RENDERIZAÇÃO (DASHBOARD)
# ============================================

def render_dashboard():
    if metricas is None:
        return dbc.Alert("❌ Erro ao calcular métricas! Verifique se o arquivo CSV está correto.", color="danger")
    
    # Cálculo de Texto Dinâmico
    rpa_data = metricas.get('distribuicao_rpa', {})
    if rpa_data:
        total_arvores_rpa = sum(d['quantidade'] for d in rpa_data.values())
        
        # Maior RPA
        max_key = max(rpa_data, key=lambda k: rpa_data[k]['quantidade'])
        max_nome = rpa_data[max_key]['nome'].split('-')[0].strip()
        max_qtd = rpa_data[max_key]['quantidade']
        max_pct = (max_qtd / total_arvores_rpa) * 100
        
        # Menor RPA
        min_key = min(rpa_data, key=lambda k: rpa_data[k]['quantidade'])
        min_nome = rpa_data[min_key]['nome'].split('-')[0].strip()
        min_qtd = rpa_data[min_key]['quantidade']
        min_pct = (min_qtd / total_arvores_rpa) * 100
        
        texto_analise = f"Análise: A {max_nome} concentra {max_pct:.1f}% ({max_qtd:,}) das árvores. A {min_nome} possui apenas {min_pct:.1f}% ({min_qtd:,})."
    else:
        texto_analise = "Análise indisponível (sem dados de RPA)."

    card_style = {
        'height': '100%',
        'borderRadius': '12px',
        'border': f'1px solid {COLORS["border"]}',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.08)',
        'transition': 'transform 0.2s, box-shadow 0.2s'
    }
    
    cards = dbc.Row([
        # 1. Total
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div("📊", style={'fontSize': '2.5rem', 'marginBottom': '0.5rem'}),
                    html.H2(f"{metricas['total_arvores']:,}", style={'color': COLORS['dark'], 'marginBottom': '0.25rem', 'fontWeight': '700', 'fontSize': '1.75rem'}),
                    html.P("Total de árvores", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': 0, 'fontWeight': '500'}),
                    html.P("cadastradas", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.15rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=True, className="mb-3"),
        
        # 2. Atenção
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div("⚠️", style={'fontSize': '2.5rem', 'marginBottom': '0.5rem'}),
                    html.H2(f"{metricas['pct_atencao']:.1f}%", style={'color': COLORS['dark'], 'marginBottom': '0.25rem', 'fontWeight': '700', 'fontSize': '1.75rem'}),
                    html.P("Precisam atenção", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': 0, 'fontWeight': '500'}),
                    html.P(f"de {metricas.get('total_avaliadas', 0):,} avaliadas", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.15rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=True, className="mb-3"),
        
        # 3. Espécie Mais Comum
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div("🌳", style={'fontSize': '2.5rem', 'marginBottom': '0.5rem'}),
                    html.H4(metricas['especie_mais_comum'], style={'color': COLORS['dark'], 'marginBottom': '0.25rem', 'fontSize': '1.1rem', 'fontWeight': '700'}),
                    html.P("Espécie mais comum", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': 0, 'fontWeight': '500'}),
                    html.P(f"{metricas['especie_top_count']:,} ({metricas['especie_top_pct']:.1f}%)", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.15rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=True, className="mb-3"),
        
        # 4. Altura Média
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div("📏", style={'fontSize': '2.5rem', 'marginBottom': '0.5rem'}),
                    html.H2(f"{metricas.get('altura_media_m', 0):.2f}m", style={'color': COLORS['dark'], 'marginBottom': '0.25rem', 'fontWeight': '700', 'fontSize': '1.75rem'}),
                    html.P("Altura média", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': 0, 'fontWeight': '500'}),
                    html.P(f"máx: {metricas.get('altura_max_m', 0):.1f}m", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.15rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=True, className="mb-3"),
        
        # 5. Plantios
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div("🌱", style={'fontSize': '2.5rem', 'marginBottom': '0.5rem'}),
                    html.H2(f"{metricas.get('plantios_desde_2020', 0):,}", style={'color': COLORS['dark'], 'marginBottom': '0.25rem', 'fontWeight': '700', 'fontSize': '1.75rem'}),
                    html.P("Plantios novos", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': 0, 'fontWeight': '500'}),
                    html.P("desde 2020", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.15rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=True, className="mb-3"),
    ], className="mb-4")
    
    grafico_rpa = criar_grafico_rpa()
    mini_mapa_html = gerar_mini_mapa()
    
    secao_meio = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Mapa Geral - Arborização", className="m-0", style={'fontWeight': 'bold'}),
                    dbc.Badge("Mapa de Calor", color="success", className="ms-2")
                ], style={'background': 'white', 'borderBottom': 'none', 'padding': '1.5rem'}),
                
                dbc.CardBody([
                    html.Div([
                        html.Iframe(srcDoc=mini_mapa_html, style={'width': '100%', 'height': '100%', 'border': 'none'})
                    ], style={'height': '300px', 'borderRadius': '12px', 'overflow': 'hidden', 'marginBottom': '1rem'}),
                    
                    dbc.Button("Ver mapa detalhado da cidade", id='btn-ir-mapa', color="success", className="w-100 py-2", style={'fontWeight': '600'})
                ], style={'padding': '0 1.5rem 1.5rem 1.5rem'})
            ], style=card_style)
        ], width=12, lg=7, className="mb-4"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("Distribuição por RPA", className="m-0", style={'fontWeight': 'bold'}),
                ], style={'background': 'white', 'borderBottom': 'none', 'padding': '1.5rem'}),
                
                dbc.CardBody([
                    html.Div([
                        dbc.Label("Visualização:", className="me-2", style={'fontWeight': '600', 'color': COLORS['dark']}),
                        dbc.RadioItems(
                            id='tipo-grafico',
                            options=[
                                {'label': html.Span(['Barras'], className="ms-1"), 'value': 'barras'},
                                {'label': html.Span(['Pizza'], className="ms-1"), 'value': 'pizza'}
                            ],
                            value='barras',
                            className="btn-group",
                            inputClassName="btn-check",
                            labelClassName="btn btn-outline-success",
                            labelCheckedClassName="active",
                            inline=True
                        ),
                    ], className="mb-3 d-flex align-items-center"),
                    
                    dcc.Graph(id='grafico-rpa', figure=grafico_rpa, config={'displayModeBar': False}, style={'height': '300px'}),
                    
                    dbc.Alert(texto_analise, color="light", style={'fontSize': '0.9rem', 'marginTop': '1rem'})
                ], style={'padding': '0 1.5rem 1.5rem 1.5rem'})
            ], style=card_style)
        ], width=12, lg=5, className="mb-4")
    ])

    top_especies = criar_top_especies() if metricas.get('top_especies') else None
    
    return html.Div([
        html.H3("Indicadores Principais", className="mb-4"),
        cards,
        html.Hr(),
        secao_meio,
        html.Hr() if top_especies else None,
        top_especies if top_especies else None
    ])

def gerar_mini_mapa():
    if df_geral is None: return ""
    df_sample = df_geral.sample(n=min(2000, len(df_geral)))
    m = folium.Map(location=[-8.05, -34.90], zoom_start=11, control_scale=False, zoom_control=False)
    try:
        if 'latitude' in df_sample.columns and 'longitude' in df_sample.columns:
            coords = df_sample[['latitude', 'longitude']].dropna().values.tolist()
            HeatMap(coords, radius=10, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(m)
    except Exception as e:
        print(f"Erro no mini mapa: {e}")
    return m._repr_html_()

def criar_grafico_rpa(tipo='barras'):
    if not metricas or not metricas.get('distribuicao_rpa'):
        return go.Figure()
    
    rpa_data = metricas['distribuicao_rpa']
    keys_sorted = sorted(rpa_data.keys(), key=lambda k: rpa_data[k]['quantidade'])
    
    nomes_full = [rpa_data[key]['nome'] for key in keys_sorted]
    nomes_short = [n.split('-')[0].strip() for n in nomes_full]
    counts = [rpa_data[key]['quantidade'] for key in keys_sorted]
    cores = [RPA_COLORS.get(n, '#999') for n in nomes_short]
    
    if tipo == 'barras':
        fig = go.Figure(go.Bar(
            x=counts, y=nomes_short, orientation='h',
            marker_color=cores,
            text=[f'{c:,}' for c in counts], textposition='auto'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, ticksuffix="   "),
            plot_bgcolor='white'
        )
    else:
        fig = go.Figure(go.Pie(
            labels=nomes_short, values=counts, marker_colors=cores,
            hole=0.6, textinfo='label+percent', textposition='inside'
        ))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10), showlegend=False)
    
    return fig

@app.callback(Output('grafico-rpa', 'figure'), Input('tipo-grafico', 'value'))
def atualizar_grafico_rpa(tipo):
    return criar_grafico_rpa(tipo)

def criar_top_especies():
    arquivos_fotos = {
        "Ipê-Rosa": "especies/ipe-rosa.png", "Ipê-rosa": "especies/ipe-rosa.png",
        "Mororó": "especies/mororo.png",
        "Ipê-Roxo": "especies/ipe-roxo.png", "Ipê-roxo": "especies/ipe-roxo.png",
        "Sabonete": "especies/sabonete.png",
        "Sapoti-do-mangue": "especies/sapoti-do-mangue.png"
    }
    fotos_fallback = {"Ipê-Rosa": "https://images.unsplash.com/photo-1602391833977-358a52198938?w=400"}
    
    cards = []
    for i, esp in enumerate(metricas['top_especies'][:5]):
        nome = esp['nome']
        foto_url = None
        arquivo_local = arquivos_fotos.get(nome)
        if arquivo_local and Path(arquivo_local).exists():
            try:
                with open(arquivo_local, 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode()
                    foto_url = f"data:image/png;base64,{img_base64}"
            except:
                foto_url = fotos_fallback.get(nome, "https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=400")
        else:
            foto_url = fotos_fallback.get(nome, "https://images.unsplash.com/photo-1502082553048-f009c37129b9?w=400")
        
        card = dbc.Col([
            dbc.Card([
                dbc.CardImg(src=foto_url, top=True, style={'height': '180px', 'objectFit': 'cover'}),
                dbc.CardBody([
                    html.H2(f"{i+1}º", style={'color': COLORS['primary'], 'textAlign': 'center', 'margin': 0}),
                    html.H6(nome, style={'textAlign': 'center', 'marginTop': '0.5rem'}),
                    html.P(f"{esp['quantidade']:,} árvores", style={'textAlign': 'center', 'color': COLORS['gray'], 'fontSize': '0.875rem', 'margin': 0}),
                    html.P(f"{esp['percentual']:.1f}%", style={'textAlign': 'center', 'color': COLORS['primary'], 'fontWeight': 'bold', 'fontSize': '0.875rem'})
                ])
            ], style={'transition': 'transform 0.3s', 'cursor': 'pointer'})
        ], width=12, sm=6, md=2)
        cards.append(card)
    
    return html.Div([
        html.H4("Top 5 Espécies Mais Comuns", className="mb-3"),
        html.P(f"Percentual entre as {metricas.get('total_com_especie', 0):,} árvores com espécie cadastrada", style={'color': COLORS['gray'], 'fontSize': '0.875rem'}),
        dbc.Row(cards, className="mb-4 justify-content-center"),
        dbc.Button("Ver todas as espécies", id="btn-ver-todas", color="success", className="mt-3")
    ])

def render_mapa():
    return dbc.Row([
        dbc.Col([
            html.Div([
                html.H5("Filtros e camadas", style={'fontWeight': '600', 'marginBottom': '1.5rem'}),
                html.Div([
                    html.P("Total de árvores", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': '0.25rem'}),
                    html.H3(f"{len(df_geral):,}" if df_geral is not None else "---", 
                            style={'color': COLORS['primary'], 'fontWeight': '700', 'marginBottom': '1.5rem'})
                ]),
                html.Hr(),
                html.Div([
                    html.Label("Tipo de visualização", style={'fontWeight': '600', 'marginBottom': '0.75rem', 'display': 'block'}),
                    dcc.RadioItems(
                        id='tipo-mapa',
                        options=[{'label': ' Mapa de Calor', 'value': 'heatmap'}, {'label': ' Marcadores', 'value': 'markers'}],
                        value='heatmap',
                        style={'marginBottom': '1.5rem'}
                    )
                ]),
                html.Hr(),
                html.Div([
                    html.Label("Região (RPA)", style={'fontWeight': '600', 'marginBottom': '0.75rem', 'display': 'block'}),
                    dcc.Checklist(
                        id='filtro-rpa',
                        options=[
                            {'label': ' RPA 1 - Centro', 'value': '1'},
                            {'label': ' RPA 2 - Norte', 'value': '2'},
                            {'label': ' RPA 3 - Noroeste', 'value': '3'},
                            {'label': ' RPA 4 - Oeste', 'value': '4'},
                            {'label': ' RPA 5 - Sudoeste', 'value': '5'},
                            {'label': ' RPA 6 - Sul', 'value': '6'},
                        ],
                        value=['1', '2', '3', '4', '5', '6'],
                        style={'marginBottom': '1.5rem'}
                    )
                ]),
                html.Hr(),
                dbc.Button("🗺️ Gerar Mapa", id='btn-gerar-mapa', color="success", className="w-100 mb-2", size="lg"),
                dbc.Button("🔄 Limpar Filtros", id='btn-limpar-filtros', color="secondary", outline=True, className="w-100", size="sm"),
            ], style={
                'background': 'white', 'padding': '1.5rem', 'borderRadius': '12px',
                'boxShadow': '0 1px 3px rgba(0,0,0,0.08)', 'height': '100%'
            })
        ], width=12, lg=3, className="mb-3"),
        
        dbc.Col([
            html.Div([
                html.Div([
                    html.H5("Mapa de Arborização de Recife", style={'fontWeight': '600', 'margin': 0}),
                    html.Div([
                        dbc.Badge("Mapa de Calor", id='badge-tipo-mapa', color="success", className="me-2"),
                        dbc.Badge("Todas RPAs", id='badge-rpas', color="info"),
                    ], style={'display': 'flex', 'gap': '0.5rem'})
                ], style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'marginBottom': '1rem', 'padding': '1rem', 'background': 'white', 'borderRadius': '12px 12px 0 0', 'borderBottom': f'1px solid {COLORS["border"]}'}),
                
                dcc.Loading(type="circle", children=[
                    html.Div(id='mapa-info', style={'padding': '1rem', 'background': 'white'}),
                    html.Iframe(id='mapa-iframe', style={'width': '100%', 'height': '600px', 'border': 'none', 'background': '#f0f0f0'})
                ]),
            ], style={'background': 'white', 'borderRadius': '12px', 'boxShadow': '0 1px 3px rgba(0,0,0,0.08)', 'overflow': 'hidden'})
        ], width=12, lg=9)
    ])

@app.callback(
    [Output('mapa-iframe', 'srcDoc'), Output('mapa-info', 'children'), Output('badge-tipo-mapa', 'children'), Output('badge-rpas', 'children')],
    [Input('btn-gerar-mapa', 'n_clicks')],
    [Input('tipo-mapa', 'value'), Input('filtro-rpa', 'value')]
)
def atualizar_mapa_folium(n_clicks, tipo_mapa, rpas_selecionadas):
    if not n_clicks: return "", dbc.Alert("👆 Clique no botão 'Gerar Mapa' para visualizar", color="info"), "Mapa de Calor", "Todas RPAs"
    if df_geral is None: return "", dbc.Alert("❌ Dataset não encontrado!", color="danger"), "Erro", "Erro"
    try:
        df_mapa = df_geral.copy()
        
        if rpas_selecionadas and 'rpa' in df_mapa.columns:
            rpas_int = [int(r) for r in rpas_selecionadas]
            df_mapa = df_mapa[df_mapa['rpa'].isin(rpas_int)].copy()
            
        df_mapa = df_mapa[
            (df_mapa['latitude'].between(-8.2, -7.9)) & 
            (df_mapa['longitude'].between(-35.1, -34.8))
        ].copy()
        
        total_pontos = len(df_mapa)
        if total_pontos == 0: return "", dbc.Alert("❌ Nenhum ponto encontrado!", color="warning"), tipo_mapa, f"{len(rpas_selecionadas)} RPAs"
        
        mapa = folium.Map(location=[-8.05, -34.93], zoom_start=11, tiles='OpenStreetMap', control_scale=True)
        badge_tipo = "Mapa de Calor" if tipo_mapa == 'heatmap' else "Marcadores"
        badge_rpas = "Todas RPAs" if len(rpas_selecionadas) == 6 else f"{len(rpas_selecionadas)} RPA(s)"
        
        if tipo_mapa == 'heatmap':
            coordenadas = df_mapa[['latitude', 'longitude']].dropna().values.tolist()
            HeatMap(coordenadas, radius=10, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 0.8: 'yellow', 1.0: 'red'}).add_to(mapa)
            info = dbc.Alert([html.Strong(f"✅ {total_pontos:,} árvores "), html.Span("visualizadas")], color="success")
        else:
            marker_cluster = MarkerCluster(name="Árvores", overlay=True, control=True, show=True).add_to(mapa)
            
            if total_pontos > 10000:
                df_sample = df_mapa.sample(n=10000, random_state=42)
                info = dbc.Alert([html.Strong(f"📍 10.000 de {total_pontos:,} árvores "), html.Span("(amostra para performance)")], color="warning")
            else:
                df_sample = df_mapa
                info = dbc.Alert([html.Strong(f"✅ {total_pontos:,} árvores "), html.Span("visualizadas")], color="success")

            for idx, row in df_sample.iterrows():
                folium.CircleMarker(location=[row['latitude'], row['longitude']], radius=4, color='green', fill=True, fillColor='green', fillOpacity=0.7, weight=1).add_to(marker_cluster)
                
        return mapa._repr_html_(), info, badge_tipo, badge_rpas
    except Exception as e: return "", dbc.Alert(f"❌ Erro: {str(e)}", color="danger"), "Erro", "Erro"

@app.callback(Output('filtro-rpa', 'value'), Input('btn-limpar-filtros', 'n_clicks'))
def limpar_filtros(n_clicks):
    return ['1', '2', '3', '4', '5', '6']

# ============================================
# FUNÇÃO PARA TREINAR CLASSIFICADOR
# ============================================

def treinar_classificador():
    """Treina um classificador para identificar árvores grandes (copa > 6m) baseado no CAP"""
    if df_geral is None:
        return None
    
    try:
        # Prepara dados: filtra apenas registros com copa e cap válidos
        df_class = df_geral.copy()
        df_class = df_class[
            (df_class['copa'].notna()) & 
            (df_class['copa'] > 0) & 
            (df_class['copa'] < 30) &  # Remove outliers
            (df_class['cap'].notna()) & 
            (df_class['cap'] > 0) & 
            (df_class['cap'] < 5)  # Remove outliers
        ].copy()
        
        if len(df_class) < 50:
            return None
        
        # Define classe: Copa > 6m é "Grande" (1), senão "Normal" (0)
        df_class['classe'] = (df_class['copa'] > 6).astype(int)
        
        # Feature: CAP em metros
        X = df_class[['cap']].values
        y = df_class['classe'].values
        
        # Divide em treino e teste
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
        
        # Treina classificador (Regressão Logística)
        clf = LogisticRegression(random_state=42, max_iter=1000)
        clf.fit(X_train, y_train)
        
        # Predições
        y_pred = clf.predict(X_test)
        y_prob = clf.predict_proba(X_test)[:, 1]
        
        # Calcula métricas
        cm = confusion_matrix(y_test, y_pred)
        report = classification_report(y_test, y_pred, target_names=['Normal', 'Grande'], output_dict=True)
        
        # Curvas ROC e Precision-Recall
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        roc_auc = auc(fpr, tpr)
        
        precision, recall, _ = precision_recall_curve(y_test, y_prob)
        pr_auc = average_precision_score(y_test, y_prob)
        
        return {
            'confusion_matrix': cm,
            'classification_report': report,
            'roc_curve': {'fpr': fpr, 'tpr': tpr, 'auc': roc_auc},
            'pr_curve': {'precision': precision, 'recall': recall, 'auc': pr_auc},
            'y_test': y_test,
            'y_pred': y_pred,
            'y_prob': y_prob
        }
    except Exception as e:
        print(f"⚠️ Erro ao treinar classificador: {e}")
        return None

# ============================================
# FUNÇÃO DE RENDERIZAÇÃO DA ANÁLISE
# ============================================

def render_analise():
    """Renderiza a seção de análise estatística com classificador"""
    
    resultados = treinar_classificador()
    
    if resultados is None:
        return html.Div([
            html.H3("📈 Análise Estatística de Classificadores", className="mb-4"),
            dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "Não foi possível treinar o classificador. Verifique se há dados suficientes com informações de CAP e Copa."
            ], color="warning")
        ])
    
    cm = resultados['confusion_matrix']
    report = resultados['classification_report']
    roc_data = resultados['roc_curve']
    pr_data = resultados['pr_curve']
    
    # Extrai métricas
    accuracy = report['accuracy']
    precision_grande = report['Grande']['precision']
    recall_grande = report['Grande']['recall']
    f1_grande = report['Grande']['f1-score']
    precision_normal = report['Normal']['precision']
    recall_normal = report['Normal']['recall']
    f1_normal = report['Normal']['f1-score']
    
    card_style = {
        'height': '100%',
        'borderRadius': '12px',
        'border': f'1px solid {COLORS["border"]}',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.08)',
        'transition': 'transform 0.2s, box-shadow 0.2s'
    }
    
    # Cards de métricas
    metricas_cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{accuracy:.1%}", style={'color': COLORS['primary'], 'fontWeight': '700', 'marginBottom': '0.5rem'}),
                    html.P("Acurácia", style={'color': COLORS['gray'], 'fontSize': '0.9rem', 'margin': 0}),
                    html.P("Taxa de acerto geral", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.25rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{precision_grande:.1%}", style={'color': COLORS['primary'], 'fontWeight': '700', 'marginBottom': '0.5rem'}),
                    html.P("Precisão (Grande)", style={'color': COLORS['gray'], 'fontSize': '0.9rem', 'margin': 0}),
                    html.P("Confiança no alerta", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.25rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{recall_grande:.1%}", style={'color': COLORS['primary'], 'fontWeight': '700', 'marginBottom': '0.5rem'}),
                    html.P("Recall (Grande)", style={'color': COLORS['gray'], 'fontSize': '0.9rem', 'margin': 0}),
                    html.P("Sensibilidade", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.25rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=6, lg=3, className="mb-3"),
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{f1_grande:.1%}", style={'color': COLORS['primary'], 'fontWeight': '700', 'marginBottom': '0.5rem'}),
                    html.P("F1-Score (Grande)", style={'color': COLORS['gray'], 'fontSize': '0.9rem', 'margin': 0}),
                    html.P("Média harmônica", style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.25rem'})
                ], style={'textAlign': 'center', 'padding': '1.5rem'})
            ], style=card_style)
        ], width=12, md=6, lg=3, className="mb-3"),
    ], className="mb-4")
    
    # Matriz de Confusão
    fig_cm = go.Figure(data=go.Heatmap(
        z=cm,
        x=['Normal (Previsto)', 'Grande (Previsto)'],
        y=['Normal (Real)', 'Grande (Real)'],
        colorscale='Blues',
        text=cm,
        texttemplate='%{text}',
        textfont={"size": 16},
        showscale=True
    ))
    fig_cm.update_layout(
        title='Matriz de Confusão',
        height=400,
        margin=dict(l=0, r=0, t=50, b=0)
    )
    
    # Curva ROC
    fig_roc = go.Figure()
    fig_roc.add_trace(go.Scatter(
        x=roc_data['fpr'],
        y=roc_data['tpr'],
        mode='lines',
        name=f'ROC (AUC = {roc_data["auc"]:.3f})',
        line=dict(color=COLORS['primary'], width=3)
    ))
    fig_roc.add_trace(go.Scatter(
        x=[0, 1],
        y=[0, 1],
        mode='lines',
        name='Linha de Referência',
        line=dict(color='gray', dash='dash', width=2)
    ))
    fig_roc.update_layout(
        title=f'Curva ROC (AUC = {roc_data["auc"]:.3f})',
        xaxis_title='Taxa de Falsos Positivos',
        yaxis_title='Taxa de Verdadeiros Positivos',
        height=400,
        margin=dict(l=0, r=0, t=50, b=0),
        hovermode='closest'
    )
    
    # Curva Precision-Recall
    fig_pr = go.Figure()
    fig_pr.add_trace(go.Scatter(
        x=pr_data['recall'],
        y=pr_data['precision'],
        mode='lines',
        name=f'Precision-Recall (AP = {pr_data["auc"]:.3f})',
        line=dict(color=COLORS['primary'], width=3),
        fill='tozeroy'
    ))
    fig_pr.update_layout(
        title=f'Curva Precision-Recall (AP = {pr_data["auc"]:.3f})',
        xaxis_title='Recall',
        yaxis_title='Precisão',
        height=400,
        margin=dict(l=0, r=0, t=50, b=0),
        hovermode='closest'
    )
    
    # Análise textual
    analise_textual = html.Div([
        html.H5("📊 Análise das Métricas", className="mb-3", style={'fontWeight': '700'}),
        html.Div([
            html.P([
                html.Strong("Acurácia ({:.1%}): ".format(accuracy)),
                "É a taxa de acerto geral do modelo. De cada 100 árvores, o modelo acerta a classificação de {:.0f}. ".format(accuracy * 100),
                "É uma métrica útil, mas pode ser enganosa quando há desbalanceamento de classes."
            ], style={'marginBottom': '1rem', 'lineHeight': '1.8'}),
            
            html.P([
                html.Strong("Precisão ({:.1%}): ".format(precision_grande)),
                "Quando o modelo diz que uma árvore é GRANDE, ele está correto em {:.1%} das vezes. ".format(precision_grande),
                "Uma precisão alta significa que a prefeitura pode confiar nos alertas do sistema, evitando gastos com vistorias desnecessárias."
            ], style={'marginBottom': '1rem', 'lineHeight': '1.8'}),
            
            html.P([
                html.Strong("Recall ({:.1%}): ".format(recall_grande)),
                "Das árvores que realmente são grandes, o modelo consegue detectar {:.1%}. ".format(recall_grande),
                "Esta é uma métrica crítica para segurança pública - um recall baixo significa que muitas árvores grandes passam despercebidas, "
                "aumentando o risco de quedas e acidentes."
            ], style={'marginBottom': '1rem', 'lineHeight': '1.8'}),
            
            html.P([
                html.Strong("F1-Score ({:.1%}): ".format(f1_grande)),
                "É a média harmônica entre precisão e recall, oferecendo um equilíbrio entre as duas métricas. "
                "Um F1-score alto indica que o modelo tem bom desempenho tanto em evitar falsos alarmes quanto em detectar árvores grandes."
            ], style={'marginBottom': '1rem', 'lineHeight': '1.8'}),
            
            html.Hr(),
            
            html.H6("💡 Implicações Práticas", className="mt-3 mb-2", style={'fontWeight': '700', 'color': COLORS['primary']}),
            html.P([
                "O modelo desenvolvido demonstra alta capacidade técnica (AUC de {:.3f}) para distinguir o porte das árvores apenas pelo diâmetro do tronco (CAP). ".format(roc_data['auc']),
                "Atualmente, ele opera com uma precisão de {:.1%}, o que significa que é eficiente em direcionar equipes de poda sem desperdiçar recursos com vistorias desnecessárias. ".format(precision_grande),
                "No entanto, na configuração atual, o sistema prioriza a economia de recursos e acaba não detectando cerca de {:.1%} das árvores de grande porte (Recall de {:.1%}). ".format(
                    (1 - recall_grande) * 100, recall_grande
                ),
                "Para fins de segurança pública (evitar queda de árvores), recomenda-se um ajuste no sistema para torná-lo mais sensível, "
                "aceitando-se um leve aumento nas vistorias em troca de garantir que nenhuma árvore grande passe despercebida."
            ], style={'lineHeight': '1.8', 'fontStyle': 'italic', 'color': COLORS['dark']})
        ], style={'padding': '1.5rem', 'background': COLORS['background'], 'borderRadius': '8px'})
    ])
    
    return html.Div([
        html.H3("📈 Análise Estatística de Classificadores", className="mb-4"),
        html.P(
            "Avaliação de desempenho de classificador para identificar árvores grandes (copa > 6m) baseado no CAP (Circunferência à Altura do Peito).",
            style={'color': COLORS['gray'], 'fontSize': '0.95rem', 'marginBottom': '2rem'}
        ),
        
        metricas_cards,
        
        html.Hr(className="my-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=fig_cm, config={'displayModeBar': False})
                    ])
                ], style=card_style)
            ], width=12, lg=4, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=fig_roc, config={'displayModeBar': False})
                    ])
                ], style=card_style)
            ], width=12, lg=4, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=fig_pr, config={'displayModeBar': False})
                    ])
                ], style=card_style)
            ], width=12, lg=4, className="mb-4"),
        ], className="mb-4"),
        
        html.Hr(className="my-4"),
        
        analise_textual
    ])
def render_especies(): return html.Div([html.H3("Seletor de Espécies"), dbc.Alert("🚧 Em desenvolvimento...", color="info")])

# ============================================
# FUNÇÃO PARA GERAR DESCRIÇÃO DO GRÁFICO
# ============================================

def gerar_descricao_grafico(codigo, titulo_markdown, num_axes):
    """Gera uma descrição descritiva sobre o que o gráfico mostra"""
    
    descricao = "Este gráfico evidencia "
    
    # Palavras-chave para identificar tipos de análise
    if 'hist' in codigo or 'histogram' in codigo:
        if 'altura' in codigo:
            descricao += "a distribuição das alturas das árvores no Recife"
        elif 'dap' in codigo:
            descricao += "a distribuição do DAP (diâmetro à altura do peito) das árvores"
        elif 'copa' in codigo:
            descricao += "a distribuição do tamanho das copas das árvores"
        elif 'rpa' in codigo:
            descricao += "a distribuição das árvores por RPA (Região Político-Administrativa)"
        else:
            descricao += "a distribuição de uma característica das árvores no Recife"
    
    elif 'bar' in codigo or 'barplot' in codigo:
        if 'especie' in codigo or 'nome_popular' in codigo:
            descricao += "a quantidade de árvores por espécie no Recife"
        elif 'rpa' in codigo:
            descricao += "a quantidade de árvores por RPA no Recife"
        elif 'bairro' in codigo:
            descricao += "a quantidade de árvores por bairro no Recife"
        else:
            descricao += "a comparação de quantidades entre diferentes categorias"
    
    elif 'pie' in codigo or 'pizza' in codigo:
        if 'especie' in codigo or 'nome_popular' in codigo:
            descricao += "a proporção de árvores por espécie no Recife"
        elif 'rpa' in codigo:
            descricao += "a proporção de árvores por RPA no Recife"
        else:
            descricao += "a proporção de distribuição de árvores por categoria"
    
    elif 'scatter' in codigo or 'scatterplot' in codigo:
        if 'altura' in codigo and 'dap' in codigo:
            descricao += "a relação entre altura e DAP das árvores"
        else:
            descricao += "a relação entre duas variáveis das árvores"
    
    elif 'box' in codigo or 'boxplot' in codigo:
        descricao += "a distribuição e variabilidade de características das árvores"
    
    elif 'heatmap' in codigo or 'heat map' in codigo:
        descricao += "a concentração e distribuição espacial das árvores no Recife"
    
    elif num_axes > 3:
        descricao += "múltiplas análises estatísticas sobre diferentes características das árvores no Recife"
    
    elif 'distribu' in codigo or 'distribuição' in codigo:
        descricao += "a distribuição espacial ou estatística das árvores no Recife"
    
    elif 'fitossanid' in codigo or 'saude' in codigo or 'condicao' in codigo:
        descricao += "a condição fitossanitária das árvores no Recife"
    
    elif 'especie' in codigo or 'nome_popular' in codigo:
        descricao += "informações sobre as espécies de árvores no Recife"
    
    elif 'rpa' in codigo:
        descricao += "a distribuição das árvores por RPA no Recife"
    
    elif titulo_markdown:
        # Usa o título markdown se disponível
        descricao = f"Este gráfico evidencia {titulo_markdown.lower()}"
    
    else:
        descricao += "características e padrões das árvores no Recife"
    
    return descricao

# ============================================
# FUNÇÃO PARA EXTRAIR IMAGENS DO NOTEBOOK
# ============================================

def extrair_imagens_notebook():
    """Extrai todas as imagens PNG dos outputs do notebook junto com descrições"""
    notebook_path = Path("notebook/Verdefica_Unificado_12nov2025.ipynb")
    imagens = []
    imagens_vistas = set()  # Para detectar duplicatas
    
    # Contadores para filtrar gráficos específicos
    contador_rpa = 0  # Gráficos sobre quantidade de árvores por RPA
    
    if not notebook_path.exists():
        return imagens
    
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        cells = nb.get('cells', [])
        
        for cell_idx, cell in enumerate(cells):
            if cell.get('cell_type') == 'code':
                outputs = cell.get('outputs', [])
                
                # Analisa o código da célula para entender o que o gráfico mostra
                source_code = cell.get('source', [])
                if isinstance(source_code, list):
                    codigo_completo = ''.join(source_code).lower()
                else:
                    codigo_completo = str(source_code).lower()
                
                # Busca títulos/descrições em células markdown anteriores
                titulo_markdown = None
                for i in range(max(0, cell_idx - 3), cell_idx):
                    prev_cell = cells[i]
                    if prev_cell.get('cell_type') == 'markdown':
                        source = prev_cell.get('source', [])
                        if isinstance(source, list):
                            texto = ''.join(source).strip()
                        else:
                            texto = str(source).strip()
                        # Remove formatação markdown
                        texto_limpo = texto.replace('**', '').replace('##', '').replace('#', '').strip()
                        # Pega títulos de seção (geralmente mais descritivos)
                        if len(texto_limpo) > 10 and len(texto_limpo) < 100:
                            titulo_markdown = texto_limpo
                            break
                
                for output_idx, output in enumerate(outputs):
                    if output.get('output_type') == 'display_data':
                        data = output.get('data', {})
                        if 'image/png' in data:
                            img_data = data['image/png']
                            
                            # Verifica se a imagem já foi adicionada (remove duplicatas)
                            # Usa hash MD5 completo da imagem para detectar duplicatas exatas
                            # img_data já é uma string base64, então codificamos para bytes
                            img_hash = hashlib.md5(img_data.encode('utf-8') if isinstance(img_data, str) else img_data).hexdigest()
                            if img_hash in imagens_vistas:
                                continue  # Pula imagens duplicadas
                            imagens_vistas.add(img_hash)
                            
                            # Pega o texto/plain para detectar múltiplos eixos
                            titulo = None
                            num_axes = 1
                            if 'text/plain' in data:
                                text_plain = data['text/plain']
                                if isinstance(text_plain, list) and len(text_plain) > 0:
                                    titulo = text_plain[0]
                                    # Detecta múltiplos eixos: "with X Axes"
                                    match = re.search(r'with (\d+) Axes?', titulo)
                                    if match:
                                        num_axes = int(match.group(1))
                            
                            # Gera descrição baseada no código e contexto
                            descricao = gerar_descricao_grafico(codigo_completo, titulo_markdown, num_axes)
                            
                            # Filtros para remover gráficos específicos
                            deve_remover = False
                            
                            # 1. Remove gráfico com 3 eixos sobre distribuição do tamanho das copas
                            # Descrição: "a distribuição do tamanho das copas das árvores"
                            if num_axes == 3 and 'distribuição do tamanho das copas' in descricao.lower():
                                deve_remover = True
                            
                            # 2. Remove gráfico com 1 eixo sobre "relação entre duas variáveis"
                            # Descrição: "a relação entre duas variáveis das árvores"
                            if num_axes == 1 and 'relação entre duas variáveis das árvores' in descricao.lower():
                                deve_remover = True
                            
                            # 3. Remove dois gráficos sobre quantidade de árvores por RPA
                            # Descrição: "a quantidade de árvores por RPA no Recife"
                            if 'quantidade de árvores por rpa no recife' in descricao.lower():
                                contador_rpa += 1
                                if contador_rpa <= 2:  # Remove os 2 primeiros
                                    deve_remover = True
                            
                            # 4. Remove gráfico sobre proporção de árvores por RPA
                            # Descrição: "a proporção de árvores por RPA no Recife"
                            if 'proporção de árvores por rpa no recife' in descricao.lower():
                                deve_remover = True
                            
                            if deve_remover:
                                continue  # Pula este gráfico
                            
                            imagens.append({
                                'imagem': img_data,
                                'titulo': titulo or f'Gráfico {len(imagens) + 1}',
                                'descricao': descricao,
                                'num_axes': num_axes,
                                'cell_idx': cell_idx,
                                'output_idx': output_idx
                            })
    except Exception as e:
        print(f"⚠️ Erro ao ler notebook: {e}")
    
    return imagens

# ============================================
# FUNÇÃO DE RENDERIZAÇÃO DO NOTEBOOK
# ============================================

def render_notebook():
    """Renderiza a seção com os resultados do notebook"""
    imagens = extrair_imagens_notebook()
    
    if not imagens:
        return html.Div([
            html.H3("📓 Análises do Notebook", className="mb-4"),
            dbc.Alert([
                html.I(className="fas fa-info-circle me-2"),
                "Nenhuma imagem encontrada no notebook. Verifique se o arquivo existe e contém outputs de gráficos."
            ], color="info")
        ])
    
    card_style = {
        'height': '100%',
        'borderRadius': '12px',
        'border': f'1px solid {COLORS["border"]}',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.08)',
        'transition': 'transform 0.2s, box-shadow 0.2s',
        'overflow': 'hidden'
    }
    
    cards = []
    for idx, img_info in enumerate(imagens):
        img_base64 = img_info['imagem']
        titulo = img_info['titulo']
        descricao = img_info.get('descricao')
        num_axes = img_info.get('num_axes', 1)
        
        # Limpa o título removendo tags HTML e caracteres especiais
        titulo_limpo = titulo.replace('<Figure size ', '').replace(' with ', ' - ').replace(' Axes>', ' eixos').replace(' Axe>', ' eixo').replace('>', '')
        if titulo_limpo.startswith('<'):
            titulo_limpo = f"Visualização {idx + 1}"
        
        # Gráficos com múltiplos eixos (subplots) ocupam largura total
        # Se tiver mais de 1 eixo, usa largura total (12), senão usa metade (6)
        col_width = 12 if num_axes > 1 else 6
        
        # Verifica se o gráfico está sozinho na linha
        esta_sozinho = False
        if num_axes == 1:
            # Verifica o gráfico anterior
            anterior_tem_1_eixo = False
            if idx > 0:
                anterior_num_axes = imagens[idx - 1].get('num_axes', 1)
                anterior_tem_1_eixo = anterior_num_axes == 1
            
            # Verifica o próximo gráfico
            proximo_tem_1_eixo = False
            if idx < len(imagens) - 1:
                proximo_num_axes = imagens[idx + 1].get('num_axes', 1)
                proximo_tem_1_eixo = proximo_num_axes == 1
            
            # Está sozinho se:
            # - É o primeiro E o próximo não tem 1 eixo (ou não existe)
            # - O anterior não tem 1 eixo E o próximo não tem 1 eixo (ou não existe)
            # - É o último E o anterior não tem 1 eixo
            if idx == 0:
                esta_sozinho = not proximo_tem_1_eixo
            elif idx == len(imagens) - 1:
                esta_sozinho = not anterior_tem_1_eixo
            else:
                esta_sozinho = not anterior_tem_1_eixo and not proximo_tem_1_eixo
        
        # Verifica se é o gráfico específico sobre distribuição das alturas
        eh_grafico_alturas = num_axes == 1 and descricao and 'distribuição das alturas das árvores' in descricao.lower()
        
        # Offset para centralizar se estiver sozinho (offset de 3 = centraliza coluna de 6)
        # Centraliza apenas o gráfico de alturas quando tiver 1 eixo
        if eh_grafico_alturas:
            offset = 3  # Centraliza gráfico de alturas
        elif esta_sozinho and num_axes == 1:
            offset = 3
        else:
            offset = 0
        
        # Ajusta altura máxima baseado no número de eixos
        max_height = '1000px' if num_axes > 3 else ('900px' if num_axes > 1 else '600px')
        
        # Conteúdo do card
        card_content = []
        
        # Header com título
        card_content.append(
            dbc.CardHeader([
                html.H6(titulo_limpo, className="m-0", style={'fontWeight': '600', 'fontSize': '0.95rem'})
            ], style={'background': 'white', 'borderBottom': f'1px solid {COLORS["border"]}', 'padding': '1rem'})
        )
        
        # Descrição (sempre exibida, pois sempre é gerada)
        descricao_limpa = descricao.replace('**', '').replace('##', '').replace('#', '').strip() if descricao else "Este gráfico evidencia características das árvores no Recife"
        card_content.append(
            dbc.CardBody([
                html.P(
                    descricao_limpa,
                    style={
                        'color': COLORS['gray'],
                        'fontSize': '0.9rem',
                        'lineHeight': '1.6',
                        'marginBottom': '1rem',
                        'fontStyle': 'italic'
                    }
                )
            ], style={'padding': '1rem 1.5rem 0.5rem 1.5rem'})
        )
        
        # Imagem
        card_content.append(
            dbc.CardBody([
                html.Img(
                    src=f"data:image/png;base64,{img_base64}",
                    style={
                        'width': '100%',
                        'height': 'auto',
                        'objectFit': 'contain',
                        'borderRadius': '8px',
                        'maxHeight': max_height
                    }
                )
            ], style={'padding': '1.5rem', 'textAlign': 'center'})
        )
        
        # Aplica offset se necessário para centralizar
        col_class = f"mb-4"
        if offset > 0:
            col_class += f" offset-lg-{offset}"
        
        card = dbc.Col([
            dbc.Card(card_content, style=card_style)
        ], width=12, lg=col_width, className=col_class)
        cards.append(card)
    
    return html.Div([
        html.Div([
            html.H3("📓 Análises do Notebook", className="mb-2", style={'color': COLORS['dark'], 'fontWeight': '700'}),
            html.P(
                f"Visualizações e gráficos gerados durante a análise dos dados do censo arbóreo. Total de {len(imagens)} visualização(ões) encontrada(s).",
                style={'color': COLORS['gray'], 'fontSize': '0.95rem', 'marginBottom': '2rem'}
            )
        ], style={'marginBottom': '1.5rem'}),
        dbc.Row(cards, className="g-4")
    ])

if __name__ == '__main__':
    app.run(debug=True, port=8050)