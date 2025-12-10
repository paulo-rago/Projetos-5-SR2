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
from flask import send_file
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

df_geral_file = Path("censo_arboreo_final_geral.csv")
metricas = None
df_geral = None

COLUNAS_ESSENCIAIS = [
    'x', 'y', 'nome_popular', 'especie', 'fitossanid_grupo', 
    'estado_fitossanitario', 'condicao_fisica', 'saude', 
    'altura', 'altura_total', 'data_plantio', 'rpa', 
    'copa', 'cap',
    'bairro'
]

if df_geral_file.exists():
    print("📊 Carregando dataset completo (apenas colunas essenciais) para otimizar RAM...")
    
    try:
        # Carrega apenas as colunas que existem no CSV e que são essenciais
        df_completo = pd.read_csv(df_geral_file, low_memory=False)
        colunas_existentes = [col for col in COLUNAS_ESSENCIAIS if col in df_completo.columns]
        df_geral = df_completo[colunas_existentes].copy()
        del df_completo
        
    except Exception as e:
        print(f"❌ Erro ao ler CSV com colunas essenciais: {e}")
        df_geral = None # Se falhar, define como None
        
    if df_geral is not None and len(df_geral) > 0:
        # --- 1. PRÉ-PROCESSAMENTO DE COORDENADAS ---
        try:
            if 'x' in df_geral.columns and 'y' in df_geral.columns:
                try:
                    # Tenta CRS 31985 (Sul)
                    transformer = Transformer.from_crs("EPSG:31985", "EPSG:4326", always_xy=True)
                except:
                    # Tenta CRS 32725 (Recife/Zona 25S)
                    transformer = Transformer.from_crs("EPSG:32725", "EPSG:4326", always_xy=True)
                
                # Aplica transformação e lida com NaNs/Infinitos
                x_validos = df_geral['x'].fillna(0).values
                y_validos = df_geral['y'].fillna(0).values

                lon, lat = transformer.transform(x_validos, y_validos)
                
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
            total_criticas = 0 # <--- ADICIONADO: Inicializa total de árvores críticas
            
            # Ajuste aqui o nome da coluna conforme seu CSV final
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
                total_criticas = len(df_criticas) # <--- Calcula o total de críticas
                
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
                "total_criticas": int(total_criticas),
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
        print("⚠️ Dataset não encontrado ou vazio!")

# ============================================
# CORES (mantido o original)
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
# FUNÇÃO DO FOOTER (mantida a original)
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
# LAYOUT (mantido o original)
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
            dcc.Tab(label='Seletor de Espécies', value='tela-react'),
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
# CALLBACKS (mantidos os originais)
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
    elif tab == 'tela-react':
        return render_tela_react()
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
        return 'tela-react'
        
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
        
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.Div("⚠️", style={'fontSize': '2.5rem', 'marginBottom': '0.5rem'}),
                    html.H2(f"{metricas['pct_atencao']:.1f}%", style={'color': COLORS['dark'], 'marginBottom': '0.25rem', 'fontWeight': '700', 'fontSize': '1.75rem'}),  
                    html.P("das árvores estão doentes ou mortas", style={'color': COLORS['gray'], 'fontSize': '0.875rem', 'marginBottom': 0, 'fontWeight': '500'}),
                    html.P(
                        f"{metricas.get('total_criticas', 0):,} de {metricas.get('total_avaliadas', 0):,} avaliadas", 
                        style={'color': COLORS['light_gray'], 'fontSize': '0.75rem', 'marginTop': '0.15rem'}
                    )
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
                    
                    dcc.Graph(id='grafico-rpa', figure=criar_grafico_rpa(), config={'displayModeBar': False}, style={'height': '300px'}),
                    
                    dbc.Alert(texto_analise, color="light", style={'fontSize': '0.9rem', 'marginTop': '1rem'})
                ], style={'padding': '0 1.5rem 1.5rem 1.5rem'})
            ], style=card_style)
        ], width=12, lg=5, className="mb-4")
    ])

    top_especies = criar_top_especies() if metricas and metricas.get('top_especies') else None
    
    return html.Div([
        html.H3("Indicadores Principais", className="mb-4"),
        cards,
        html.Hr(),
        secao_meio,
        html.Hr() if top_especies else None,
        top_especies if top_especies else None
    ])

def gerar_mini_mapa():
    """Gera o HTML do mapa de calor para o Dashboard (amostragem leve)"""
    if df_geral is None: return ""
    
    # Amostragem leve para o mini-mapa
    df_sample = df_geral.sample(n=min(2000, len(df_geral)), random_state=42)
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
    """
    Atualiza o mapa Folium. 
    🌟 OTIMIZAÇÃO 3: Implementa limite estrito de 1000 pontos para qualquer visualização de mapa.
    """
    if not n_clicks: return "", dbc.Alert("👆 Clique no botão 'Gerar Mapa' para visualizar", color="info"), "Mapa de Calor", "Todas RPAs"
    if df_geral is None or len(df_geral) == 0: return "", dbc.Alert("❌ Dataset não encontrado ou vazio!", color="danger"), "Erro", "Erro"
    
    # 🌟 LIMITE MÁXIMO DE PONTOS PARA QUALQUER VISUALIZAÇÃO NO MAPA DETALHADO
    MAX_POINTS = 1000 
    
    try:
        df_mapa = df_geral.copy()
        
        # 1. Aplicar filtro de RPA
        if rpas_selecionadas and 'rpa' in df_mapa.columns:
            rpas_int = [int(r) for r in rpas_selecionadas]
            df_mapa = df_mapa[df_mapa['rpa'].isin(rpas_int)].copy()
            
        # 2. Aplicar filtro de coordenadas (limite da cidade)
        df_mapa = df_mapa[
            (df_mapa['latitude'].between(-8.2, -7.9)) & 
            (df_mapa['longitude'].between(-35.1, -34.8))
        ].copy()
        
        total_pontos = len(df_mapa)
        if total_pontos == 0: 
            return "", dbc.Alert("❌ Nenhum ponto encontrado com os filtros aplicados!", color="warning"), tipo_mapa, f"{len(rpas_selecionadas)} RPAs"
        
        # 3. Aplicar amostragem estrita de 1000 pontos
        df_amostra = df_mapa
        amostra_info = ""
        info_color = "success"
        
        if total_pontos > MAX_POINTS:
            # Reduz para 1000 pontos para evitar estouro de memória/tempo limite
            df_amostra = df_mapa.sample(n=MAX_POINTS, random_state=42)
            amostra_info = html.Span(f" (Exibindo amostra de {MAX_POINTS:,} pontos)")
            info_color = "danger" 
        
        # Gerar o mapa usando a amostra
        mapa = folium.Map(location=[-8.05, -34.93], zoom_start=11, tiles='OpenStreetMap', control_scale=True)
        badge_tipo = "Mapa de Calor" if tipo_mapa == 'heatmap' else "Marcadores"
        badge_rpas = "Todas RPAs" if len(rpas_selecionadas) == 6 else f"{len(rpas_selecionadas)} RPA(s)"
        
        if tipo_mapa == 'heatmap':
            # Usa a amostra para o HeatMap
            coordenadas = df_amostra[['latitude', 'longitude']].dropna().values.tolist()
            HeatMap(coordenadas, radius=10, blur=15, gradient={0.4: 'blue', 0.65: 'lime', 0.8: 'yellow', 1.0: 'red'}).add_to(mapa)
            info = dbc.Alert([html.Strong(f"✅ {total_pontos:,} árvores "), amostra_info], color=info_color)
        else:
            # Usa a amostra para os Marcadores (cluster)
            marker_cluster = MarkerCluster(name="Árvores", overlay=True, control=True, show=True).add_to(mapa)
            
            for idx, row in df_amostra.iterrows():
                # Loop por 1000 pontos é aceitável para o browser
                folium.CircleMarker(location=[row['latitude'], row['longitude']], radius=4, color='green', fill=True, fillColor='green', fillOpacity=0.7, weight=1).add_to(marker_cluster)
                
            info = dbc.Alert([html.Strong(f"✅ {total_pontos:,} árvores "), amostra_info], color=info_color)
            
        return mapa._repr_html_(), info, badge_tipo, badge_rpas
    except Exception as e: 
        return "", dbc.Alert(f"❌ Erro ao gerar mapa: {str(e)}", color="danger"), "Erro", "Erro"

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
# ANÁLISE ESTATÍSTICA - Gráficos sem descrições, apenas com IDs
# ============================================

# ============================================
# FUNÇÃO DE RENDERIZAÇÃO DA ANÁLISE
# ============================================

def render_analise():
    """Renderiza a seção de análise estatística com gráficos do notebook"""
    
    return html.Div([
        html.H3("📈 Análise Estatística", className="mb-4", style={'color': COLORS['dark'], 'fontWeight': '700'}),
        
        # Conteúdo dos gráficos do notebook
        _render_notebook_graficos()
    ])

def _render_notebook_graficos():
    """Função auxiliar para renderizar os gráficos do notebook"""
    imagens = extrair_imagens_notebook()
    
    if not imagens:
        return dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            "Nenhuma imagem encontrada no notebook. Verifique se o arquivo existe e contém outputs de gráficos."
        ], color="info")
    
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
        grafico_id = img_info.get('id', f"GRAFICO_{idx + 1}")
        num_axes = img_info.get('num_axes', 1)
        
        # Largura da coluna
        col_width = 12 if num_axes > 1 else 6
        
        # Offset para centralizar gráficos sozinhos
        offset = 0
        if num_axes == 1:
            esta_sozinho = False
            if idx == 0:
                esta_sozinho = len(imagens) == 1 or imagens[idx + 1].get('num_axes', 1) != 1
            elif idx == len(imagens) - 1:
                esta_sozinho = imagens[idx - 1].get('num_axes', 1) != 1
            else:
                esta_sozinho = imagens[idx - 1].get('num_axes', 1) != 1 and imagens[idx + 1].get('num_axes', 1) != 1
            
            if esta_sozinho:
                offset = 3
        
        # Altura máxima
        max_height = '1000px' if num_axes > 3 else ('900px' if num_axes > 1 else '600px')
        
        # Conteúdo do card
        card_content = []
        
        # Header com ID do gráfico
        card_content.append(
            dbc.CardHeader([
                html.H6(grafico_id, className="m-0", style={'fontWeight': '600', 'fontSize': '0.95rem'})
            ], style={'background': 'white', 'borderBottom': f'1px solid {COLORS["border"]}', 'padding': '1rem'})
        )
        
        # Imagem
        card_body_content = [
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
        ]
        
        # Adiciona análise específica para GRAFICO_015
        if grafico_id == 'GRAFICO_015':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'Este gráfico apresenta as espécies com maior altura média entre as árvores registradas no Bairro do Recife.\nA ordem mostra que:\n\nSapotí-do-mangue — maior altura média (~4 m).\n\nPalmeira-imperial — próxima de 4 m também.\n\nPau-ferro — atinge média pouco abaixo de 3,5 m.\n\nIpê-roxo — altura média intermediária (~3 m).\n\nIpê-amarelo — entre as menores médias (~2,5 m).'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'Há diferença entre frequência (Gráfico 014) e porte médio (Gráfico 015):\n\nAlgumas espécies são numerosas, mas não necessariamente altas (ex.: ipê-amarelo é muito frequente, mas com menor altura média).\n\nOutras possuem poucos indivíduos, porém atingem porte mais elevado (ex.: sapotí-do-mangue).\n\nA palmeira-imperial aparece entre as mais altas, condizente com sua morfologia característica.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A variação na altura média tem impacto direto em:\n\nsombreamento,\n\nconforto térmico,\n\nocupação de espaço urbano,\n\nadequação a calçadas e fiação,\n\nplanejamento de vias arborizadas.\n\nEspécies mais altas, como palmeiras e sapotí-do-mangue, tendem a oferecer mais benefícios ambientais, mas exigem maior planejamento no plantio.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os dados indicam quais espécies:\n\ncontribuem mais para cobertura vegetal vertical,\n\ndemandam espaço adequado para pleno desenvolvimento,\n\npodem ser priorizadas em áreas amplas e evitadas em áreas restritas.\n\nA combinação entre a análise de frequência e altura média é essencial para planejar plantios equilibrados e garantir o desenvolvimento saudável do patrimônio arbóreo.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_014
        if grafico_id == 'GRAFICO_014':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico apresenta as espécies arbóreas mais comuns registradas no Bairro do Recife.\nAs espécies com maior número de indivíduos são:\n\nPau-ferro — espécie mais frequente, com cerca de 37 registros.\n\nIpê-amarelo — segunda mais presente.\n\nPalmeira-imperial — também aparece em grande quantidade.\n\nSapotí-do-mangue — distribuição significativa.\n\nIpê-roxo — frequência baixa em comparação às demais.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'O predomínio de pau-ferro e ipê-amarelo indica preferência por espécies nativas ou adaptadas ao clima e às condições urbanas do Recife.\nA presença relevante da palmeira-imperial, apesar de não ser nativa, mostra seu uso tradicional em vias e espaços públicos.\n\nA baixa quantidade de ipê-roxo pode indicar:\n\nmenor uso recente em plantios,\n\nmaior mortalidade,\n\ndisponibilidade reduzida na arborização da região.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'Conhecer as espécies mais frequentes ajuda a entender:\n\na composição florística da arborização local;\n\na diversidade, que impacta na resiliência contra pragas e doenças;\n\na predominância de espécies adaptadas ao espaço urbano.\n\nO fato de poucas espécies dominarem o cenário pode indicar baixa diversidade, o que aumenta risco de vulnerabilidade fitossanitária.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'O resultado apoia decisões sobre:\n\ndiversificação de espécies em novos plantios,\n\nreposição adequada quando houver remoções,\n\nestratégias de conservação e manejo das espécies dominantes.\n\nO equilíbrio entre espécies frequentes e a introdução controlada de novas espécies pode melhorar a qualidade e resiliência da arborização urbana.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_012
        if grafico_id == 'GRAFICO_012':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico apresenta a distribuição das alturas das árvores no Recife, revelando que a maior parte dos indivíduos registrados possui baixa estatura, concentrando-se majoritariamente entre 0 e 4 metros. À medida que a altura aumenta, a frequência de árvores diminui de forma acentuada.\nIsso evidencia um perfil arbóreo predominantemente composto por espécies jovens, de pequeno porte ou recentemente plantadas.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A distribuição claramente assimétrica indica que o patrimônio arbóreo da área analisada é formado majoritariamente por árvores baixas, com poucos exemplares de grande porte.\nA presença reduzida de árvores altas (acima de 10 m) pode refletir fatores como:\n\nlimitações estruturais e urbanas (calçadas estreitas, fiação aérea),\n\npredominância de espécies de porte pequeno/médio em plantios recentes,\n\nsubstituição ou remoção de árvores antigas,\n\nprocessos de poda intensiva.\n\nA curva suavizada ajuda a visualizar essa tendência, reforçando que a distribuição não é uniforme e que há um declínio progressivo na frequência conforme a altura aumenta.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'Compreender a distribuição de alturas é importante porque:\n\nauxilia no planejamento de novas arborizações, indicando onde há predominância de árvores jovens ou de baixo porte;\n\norienta decisões sobre espaçamento, escolha de espécies e infraestrutura necessária;\n\npermite identificar o estado de maturidade do conjunto arbóreo da região;\n\nsinaliza a necessidade de estratégias de manejo para favorecer o crescimento saudável e o desenvolvimento de exemplares de maior porte, essenciais para sombreamento e conforto térmico.\n\nÁrvores mais altas oferecem benefícios ambientais maiores (sombra, resfriamento, captura de carbono), mas a baixa proporção delas indica que esses serviços podem estar subdimensionados.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'A configuração observada sugere que a arborização da área analisada passa por uma fase de renovação ou expansão recente, marcada por indivíduos jovens de menor porte.\nIsso pode orientar:\n\nações de monitoramento de crescimento ao longo dos próximos anos,\n\npolíticas de plantio que incluam espécies capazes de atingir maior porte, quando compatível com o espaço urbano,\n\nesforços para garantir condições adequadas (solo, irrigação, manejo) que permitam que os exemplares existentes atinjam plenamente seu desenvolvimento.\n\nEntender o perfil altimétrico das árvores é essencial para um planejamento urbano que maximize os benefícios ambientais e garanta um manejo adequado do patrimônio arbóreo do Recife.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_008
        if grafico_id == 'GRAFICO_008':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'Os gráficos apresentam a distribuição espacial das árvores mapeadas na cidade do Recife, mostrando sua localização tanto em coordenadas geográficas (longitude e latitude) quanto em coordenadas projetadas (x e y, sistema UTM).\nEles permitem visualizar a área urbana coberta pelo levantamento e identificar a densidade espacial dos pontos onde existem registros de arborização.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A visualização evidencia como as árvores estão distribuídas pelo território recifense, destacando regiões com maior ou menor concentração de registros.\nA comparação entre o sistema geográfico e o sistema projetado demonstra que a conversão de coordenadas mantém a forma e a posição espacial, permitindo validar a consistência dos dados.\n\nEsses mapas não mostram informações específicas das árvores (como espécies, altura ou estado), mas sim a abrangência e a continuidade do levantamento espacial.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'Do ponto de vista de gestão urbana, compreender a distribuição espacial das árvores é fundamental para:\n\nidentificar áreas com maior adensamento arbóreo,\n\nreconhecer regiões carentes de arborização,\n\napoiar o planejamento de novos plantios,\n\norientar ações de manutenção e monitoramento do patrimônio arbóreo.\n\nEsse tipo de mapeamento é essencial para políticas públicas de arborização, infraestrutura verde e qualidade ambiental.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os gráficos confirmam que o levantamento cobre boa parte da malha urbana, permitindo análises posteriores mais detalhadas, como diversidade de espécies, saúde das árvores e prioridades de intervenção.\nCom base na distribuição espacial observada, é possível:\n\nplanejar de forma mais eficiente corredores verdes,\n\npriorizar áreas com baixa cobertura vegetal,\n\napoiar ações de manejo e conservação.\n\nA representação espacial é, portanto, um passo inicial crucial para qualquer projeto de gestão e análise da arborização urbana.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_006
        if grafico_id == 'GRAFICO_006':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O conjunto de gráficos avalia se os resíduos de um modelo de regressão atendem aos pressupostos básicos:\n(1) média zero, (2) variância constante (homocedasticidade) e (3) distribuição aproximadamente normal.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': '1️⃣ Resíduos vs Valores Preditos\n\nO que o gráfico mostra:\nO gráfico exibe os resíduos distribuídos em relação aos valores preditos da variável resposta (Copa).\nA linha pontilhada representa o nível zero do resíduo.\n\nInterpretação:\nObserva-se um padrão triangular/abaulado, onde a dispersão dos resíduos aumenta conforme o valor predito cresce.\nIsso indica heterocedasticidade: os erros não possuem variância constante.\nHá faixas diagonais com maior densidade de pontos, sugerindo possíveis restrições nas variáveis ou agrupamentos naturais dos dados.\nA média dos resíduos parece estar próxima de zero, mas a variabilidade não é uniforme.\n\nConclusão:\nO modelo parece apresentar violação da homocedasticidade, o que reduz a qualidade das inferências estatísticas (ex.: intervalos de confiança e testes).\n\n2️⃣ Histograma dos Resíduos\n\nO que o gráfico mostra:\nO histograma apresenta a distribuição dos resíduos, juntamente com uma curva suavizada (KDE).\n\nInterpretação:\nA distribuição é aproximadamente simétrica, mas não perfeitamente normal.\nHá leve concentração na região central (entre -2 e 2), mas também existe:\ncauda mais alongada à direita,\nalguns valores mais extremos (outliers) tanto à direita quanto à esquerda.\nA forma geral é parecida com uma normal, mas com pequenas distorções.\n\nConclusão:\nOs resíduos mostram uma quase-normalidade, mas com pequenas assimetrias e presença de valores extremos.\nIsso não invalida o modelo, porém indica que o ajuste não é perfeito.\n\n3️⃣ Q-Q Plot (Normalidade)\n\nO que o gráfico mostra:\nO Q-Q plot compara os quantis dos resíduos com os quantis esperados de uma distribuição normal.\n\nInterpretação:\nA parte central dos pontos está bem alinhada com a linha teórica → boa aderência à normalidade nesta região.\nNas extremidades (caudas), os pontos se afastam da linha:\nCauda inferior mais dispersa,\nCauda superior com resíduos mais altos que o esperado.\nIsso confirma a presença de pequenas distorções na normalidade, principalmente nos valores extremos.\n\nConclusão:\nA distribuição dos resíduos é quase normal, mas com desvios nas caudas, o que confirma o visto no histograma.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A avaliação dos pressupostos de regressão é fundamental para:\n\nvalidar a confiabilidade das inferências estatísticas do modelo,\n\nidentificar limitações que podem afetar a qualidade das predições,\n\nguiar melhorias no modelo (transformações, remoção de outliers, modelos alternativos).\n\nAs violações observadas (especialmente a heterocedasticidade) indicam que o modelo requer ajustes ou considerações metodológicas adicionais para garantir resultados mais robustos.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os resultados indicam que:\n\nO modelo apresenta violação da homocedasticidade, reduzindo a confiabilidade dos intervalos de confiança e testes de hipótese.\n\nOs resíduos seguem aproximadamente uma distribuição normal, mas com pequenas assimetrias e presença de outliers.\n\nO Q-Q plot confirma desvios nas caudas da distribuição.\n\nRecomendações:\n\nConsiderar transformações nas variáveis (log, raiz quadrada) para estabilizar a variância.\n\nInvestigar e possivelmente remover outliers ou tratar valores extremos.\n\nAvaliar modelos alternativos (regressão robusta, modelos não-paramétricos) que sejam menos sensíveis a violações de pressupostos.\n\nApesar das limitações identificadas, o modelo pode ser útil para análises exploratórias e compreensão de tendências gerais, mas requer cautela na interpretação de resultados inferenciais.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_005
        if grafico_id == 'GRAFICO_005':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico apresenta a relação entre o CAP (circunferência do tronco) e o diâmetro da copa das árvores da arborização urbana do Recife, considerando a exclusão de valores extremos (outliers). A linha de regressão resultante mostra uma relação positiva mais consistente, indicando que o aumento do CAP está associado ao aumento do diâmetro da copa de forma mais regular.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'Com a remoção dos outliers, observa-se uma distribuição mais homogênea dos dados e um ajuste linear mais estável. Isso indica que parte da grande variabilidade observada anteriormente estava associada a árvores atípicas, possivelmente em condições de estresse urbano, podas severas ou espécies com padrões de crescimento distintos. Ainda assim, permanece uma dispersão moderada, o que mostra que fatores locais continuam influenciando o desenvolvimento da copa.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A análise sem outliers permite projeções mais realistas do crescimento médio das árvores em ambiente urbano. Esse resultado é especialmente útil para o planejamento da arborização do Recife, pois fornece uma estimativa mais confiável do comportamento típico das árvores em condições comuns. Árvores com copas mais amplas continuam sendo essenciais para o sombreamento, conforto térmico e regulação microclimática, enquanto a compreensão dessa relação ajuda a reduzir conflitos com fiação, calçadas e edificações.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os resultados indicam que o CAP é um indicador consistente do potencial de expansão da copa quando considerados indivíduos com crescimento dentro do padrão esperado. A exclusão dos outliers reforça a importância de análises técnicas cuidadosas para evitar distorções na tomada de decisão. A compreensão dessa relação contribui para uma gestão mais eficiente, preventiva e sustentável da arborização urbana do Recife.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_003
        if grafico_id == 'GRAFICO_003':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico apresenta a relação entre o CAP (circunferência do tronco) e o diâmetro da copa das árvores da arborização urbana do Recife. A presença da linha de regressão indica uma tendência positiva: à medida que o CAP aumenta, o diâmetro da copa também tende a crescer, evidenciando um padrão geral de desenvolvimento estrutural das árvores.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A linha de regressão reforça a existência de uma correlação positiva entre o tamanho do tronco e o tamanho da copa, embora os pontos estejam bastante dispersos. Isso mostra que, apesar da tendência geral, árvores com o mesmo CAP podem apresentar copas de tamanhos diferentes. Essa heterogeneidade pode estar relacionada a fatores como espécie, podas frequentes, limitações de espaço urbano, compactação do solo e condições ambientais típicas do Recife, como clima quente e alta umidade.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'Os resultados têm alta relevância para o planejamento da arborização urbana. Árvores com copas mais desenvolvidas contribuem para o sombreamento das vias, redução da temperatura e melhoria do conforto térmico. Entretanto, o gráfico também indica que o crescimento da copa nem sempre acompanha de forma proporcional o aumento do tronco, o que reforça a necessidade de manejo adequado para evitar conflitos com fiação elétrica, fachadas e calçadas. A linha de tendência auxilia na previsão do comportamento médio das árvores ao longo do tempo.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'A análise demonstra que o CAP é um bom indicador do potencial de expansão da copa, mas não deve ser utilizado de forma isolada. A variabilidade observada reforça a importância de avaliações individuais e de políticas de manejo contínuo na arborização do Recife. O uso da regressão linear contribui para projeções mais realistas do crescimento das árvores e para decisões mais seguras sobre plantio, poda e escolha de espécies no ambiente urbano.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_002
        if grafico_id == 'GRAFICO_002':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico de dispersão evidencia a relação entre o diâmetro do tronco (CAP) e o diâmetro da copa das árvores avaliadas na arborização urbana do Recife. Observa-se uma tendência geral de crescimento conjunto: árvores com troncos mais espessos tendem a apresentar copas mais amplas, embora haja variações importantes entre indivíduos.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A relação positiva entre o CAP e o diâmetro da copa indica que o desenvolvimento estrutural das árvores na cidade segue um padrão esperado, em que o crescimento do tronco acompanha a expansão da copa. No entanto, a dispersão dos pontos mostra que essa relação não é uniforme, sugerindo influência de fatores como espécie, podas, disponibilidade de espaço, condições do solo e estresse urbano. Árvores com CAP semelhante podem apresentar copas de tamanhos bastante distintos, o que reforça a importância de avaliar cada exemplar individualmente.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A compreensão dessa relação é fundamental para o planejamento da arborização urbana no Recife. Árvores com copas mais amplas tendem a contribuir mais para o sombreamento das vias, redução da temperatura superficial e melhoria do microclima. Ao mesmo tempo, copas muito desenvolvidas, quando associadas a árvores em espaços restritos, podem gerar conflitos com fiações, calçadas e edificações. O gráfico mostra que nem sempre um tronco mais espesso resulta em copas proporcionalmente maiores, o que destaca a necessidade de manejo específico conforme o contexto urbano.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os padrões observados indicam que o CAP, embora seja um bom indicativo do porte da árvore, não deve ser utilizado de forma isolada para decisões de manejo. A variabilidade encontrada reforça a importância de inspeções técnicas periódicas e de um planejamento cuidadoso da escolha de espécies para calçadas e vias públicas no Recife. Compreender a relação entre tronco e copa contribui para uma arborização mais segura, funcional e ambientalmente eficiente no espaço urbano.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_001
        if grafico_id == 'GRAFICO_001':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'Os histogramas mostram a distribuição das alturas, CAP e copas das árvores do Recife em diferentes etapas de limpeza e transformação dos dados. As visualizações permitem observar valores originais, dados com divisões para ajuste de escala e versões filtradas sem zeros ou valores inconsistentes.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A análise das distribuições revela padrões importantes:\n\nAltura\n\nA distribuição original apresenta valores fora do padrão (outliers muito altos), o que justifica os ajustes posteriores.\n\nApós dividir valores por 100 e remover alturas iguais a zero, a distribuição se torna mais realista e compatível com a arborização urbana, concentrada principalmente entre 5 e 15 metros.\n\nO histograma final (altura_df_mod) indica um conjunto de árvores predominantemente de porte médio, com poucos indivíduos muito altos.\n\nCAP\n\nOs dados originais de CAP mostram valores extremamente elevados, alguns excedendo 400 cm, indicando erros de catalogação ou medidas excepcionais.\n\nApós remover CAP igual a zero e ajustar medições, a distribuição se estabiliza, concentrando-se entre 50 e 150 cm, condizente com troncos de árvores adultas.\n\nO padrão final reflete uma mistura de espécies jovens e adultas, típica de áreas urbanas com reposições contínuas.\n\nCopa\n\nA distribuição original evidencia valores desproporcionalmente altos em alguns registros, sugerindo anomalias.\n\nApós remover copas zeradas ou inconsistentes e filtrar valores acima de 20 m, a distribuição passa a refletir copas predominantemente entre 2 e 12 metros, que é compatível com o padrão de ruas e praças urbanas.\n\nO histograma final (copa_mod3) apresenta forte assimetria, indicando grande diversidade de espécies e condições de poda.\n\nConclusão analítica\n\nAs transformações aplicadas revelam que os dados brutos continham ruído significativo. Após limpeza e filtragem, emergem padrões que representam melhor a realidade da arborização do Recife: árvores majoritariamente de porte médio, com copa moderada e CAP variando amplamente conforme espécie e idade.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A compreensão das distribuições é fundamental para:\n\nplanejar intervenções adequadas (como poda, remoção de risco e plantio);\n\ndimensionar equipes e custos de manutenção;\n\nidentificar espécies dominantes e sua maturidade;\n\ncorrigir inconsistências no censo arbóreo, melhorando diagnósticos futuros;\n\navaliar riscos estruturais, já que árvores com grande CAP ou copa ampla demandam atenção especial.\n\nA predominância de árvores de porte médio indica uma arborização relativamente jovem ou manejada frequentemente, o que pode impactar benefícios ambientais como sombra e conforto térmico.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'As versões filtradas dos dados representam melhor a realidade urbana e devem ser usadas para análises estatísticas ou modelagens preditivas.\n\nA remoção de valores zero e a correção de escalas são passos essenciais para evitar distorções em análises posteriores, como correlações ou regressões.\n\nÁrvores de porte grande são minoria — fato que pode orientar reposições e planejamentos de espécies mais adequadas ao espaço disponível.\n\nA análise detalhada das distribuições permite identificar erros de medição, outliers e padrões estruturais, contribuindo para uma gestão arbórea mais estratégica, segura e eficiente.\n\nSíntese:\nA organização dimensional do acervo arbóreo é essencial para orientar políticas públicas, garantir manejo preventivo e ampliar os benefícios ambientais nas áreas urbanas do Recife.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_007
        if grafico_id == 'GRAFICO_007':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O conjunto de gráficos apresenta a avaliação de um modelo de classificação usado para distinguir árvores com copa normal e copa grande no Recife. A matriz de confusão quantifica os acertos e erros, enquanto as curvas ROC e Precision-Recall mostram o desempenho geral em diferentes limiares de decisão.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'Matriz de confusão\n\nNa base de teste:\n\n181 árvores com copa normal foram classificadas corretamente.\n\n46 árvores com copa grande foram identificadas corretamente.\n\n11 falsos positivos ocorreram (árvores normais classificadas como grandes).\n\n29 falsos negativos ocorreram (árvores grandes classificadas como normais).\n\nO número relativamente alto de falsos negativos sugere que o modelo é conservador: tende a rotular uma árvore como "grande" apenas quando há alta confiança, privilegiando a precisão sobre o recall.\n\nDesempenho geral (ROC e Precision-Recall)\n\nA curva ROC apresenta AUC = 0.93, indicando excelente capacidade discriminativa.\n\nA curva Precision-Recall mostra AP = 0.84, reafirmando bom desempenho mesmo com possível desbalanceamento entre classes.\n\nEsses resultados indicam que o modelo mantém bom equilíbrio entre erro e acerto, e que o limiar de decisão pode ser ajustado sem perda drástica de desempenho.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A classificação do porte da copa tem aplicações diretas na gestão urbana:\n\nPriorização de podas e vistorias, especialmente para árvores grandes que podem representar risco em áreas adensadas.\n\nRacionalização de equipes e recursos, direcionando intervenções para locais de maior probabilidade de ocorrência de copas grandes.\n\nApoio ao planejamento urbano, ao identificar padrões de desenvolvimento arbóreo em diferentes bairros.\n\nAlém disso, o bom desempenho do modelo reforça a utilidade de métricas dendrométricas—especialmente CAP e DAP como indicadores estruturais.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os resultados sugerem que:\n\nO CAP continua sendo um forte preditor do porte da copa e se mostra adequado como variável explicativa.\n\nO modelo é tecnicamente robusto, mas seu limiar pode — e deve — ser ajustado conforme o objetivo operacional:\n\nMaior recall caso a prioridade seja não deixar árvores grandes passarem despercebidas, aumentando segurança em vias públicas.\n\nMaior precisão caso se deseje evitar inspeções desnecessárias e otimizar custos.\n\nRecomendação\n\nPara aplicações voltadas à segurança e prevenção de riscos, recomenda-se ajustar o limiar para aumentar o recall, mesmo que isso gere leve aumento nos falsos positivos.\nIsso reduz a chance de árvores grandes deixarem de ser inspecionadas, o que é crucial em áreas urbanas vulneráveis a quedas, ventos fortes e estresse ambiental.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_018
        if grafico_id == 'GRAFICO_019':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico apresenta a matriz de correlação entre três medidas dendrométricas — Altura, Copa e DAP — referentes às árvores de um bairro do Recife. Ele mostra o quanto cada par de variáveis está linearmente associado.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A correlação evidencia que:\n\nAltura × DAP → r = 0.75\nHá uma correlação forte, indicando que árvores mais altas tendem a apresentar troncos de maior diâmetro. Isso é esperado em árvores urbanas onde o crescimento vertical costuma acompanhar o espessamento do tronco.\n\nAltura × Copa → r = 0.48\nA relação é moderada, sugerindo que a expansão da copa não depende apenas da altura da árvore, mas também de fatores como espécie, idade, podas e limitações do ambiente urbano.\n\nCopa × DAP → r = 0.48\nTambém apresenta correlação moderada, indicando que o desenvolvimento da copa não cresce necessariamente na mesma proporção do diâmetro do tronco — novamente refletindo influência de manejo e restrições do espaço urbano.\n\nEssas correlações estão alinhadas ao comportamento esperado em áreas urbanas, onde podas e infraestrutura condicionam o crescimento natural das árvores.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'Compreender essas relações é fundamental para:\n\nplanejar podas de maneira adequada, evitando cortes excessivos em árvores que já possuem copa reduzida;\n\nprever riscos estruturais, já que troncos mais espessos (DAP maior) estão associados ao maior porte geral das árvores;\n\norientar ações de manejo e plantio, como escolha de espécies compatíveis com o espaço disponível.\n\nA correlação forte entre altura e DAP reforça que essas variáveis podem ser usadas para modelagem preditiva e estimativa de biomassa ou estabilidade da árvore.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'A análise de correlação mostra que:\n\nO DAP é uma métrica confiável para prever outras características estruturais.\n\nA copa, por ter correlação moderada, depende fortemente do manejo urbano (podas, conflitos com infraestrutura, espaço para crescimento).\n\nEssas relações ajudam a identificar onde o manejo precisa ser aprimorado e quais áreas podem ser priorizadas no planejamento de arborização.\n\nConclusão: compreender a correlação entre medidas dendrométricas permite um manejo mais eficiente, segura melhor alocação de recursos e contribui para um planejamento urbano ambientalmente mais sustentável e estrategicamente orientado.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_019
        if grafico_id == 'GRAFICO_020':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'O gráfico mostra a relação entre a altura das árvores e a amplitude da copa em um bairro do Recife.\nA linha tracejada representa a tendência média dessa relação.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'A correlação observada (r = 0.48) é moderada, indicando que:\n\nÁrvores mais altas tendem a desenvolver copas maiores, mas essa relação não é tão forte ou direta quanto a relação entre altura e DAP.\n\nA dispersão dos pontos é ampla, principalmente em árvores de médio porte, mostrando que fatores externos influenciam muito o tamanho da copa.\n\nEssa variabilidade é esperada no ambiente urbano, onde o espaço disponível, as podas, a espécie e a competição por luz influenciam fortemente o desenvolvimento lateral da copa.\n\nO ponto muito acima do padrão (copa ≈ 100 m²) sugere a presença de uma espécie excepcionalmente ampla ou um caso pontual de árvore muito desenvolvida.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'A relação entre altura e copa tem impacto direto na gestão urbana:\n\nPlanejamento de podas e controle de interferências: copas maiores têm maior probabilidade de entrar em conflito com fiação, fachadas e vias.\n\nOferta de benefícios ambientais: árvores com copas amplas oferecem mais sombra, redução de temperatura e conforto térmico.\n\nPrevisão limitada: devido à correlação moderada, a altura sozinha não é suficiente para estimar com precisão o tamanho da copa — reforçando a necessidade de medições independentes e inspeções presenciais.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'A análise indica que:\n\nA altura fornece apenas um indicador parcial do tamanho da copa.\n\nO manejo urbano precisa considerar múltiplos fatores — especialmente espécie e histórico de podas — para prever adequadamente o comportamento da copa.\n\nEstratégias de arborização devem priorizar espécies compatíveis com o espaço disponível, evitando que copas se tornem desproporcionalmente grandes em locais estreitos.\n\nA correlação moderada justifica o uso de modelos mais completos, incorporando outras variáveis dendrométricas para melhorar previsões.\n\nConclusão: A relação Altura × Copa apresenta tendência positiva, mas com grande variabilidade. Isso reforça que a gestão da arborização urbana deve ser baseada em medições específicas da copa, e não apenas em proxies como altura ou DAP.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        # Adiciona análise específica para GRAFICO_020
        if grafico_id == 'GRAFICO_021':
            # Análise estruturada por seções
            secoes_analise = [
                {
                    'titulo': 'O que o gráfico evidencia',
                    'conteudo': 'Este gráfico apresenta a relação entre a altura das árvores e o diâmetro à altura do peito (DAP) em um bairro do Recife.\nA linha tracejada representa a tendência linear observada na amostra.'
                },
                {
                    'titulo': 'Interpretação e análise',
                    'conteudo': 'O padrão visível no gráfico mostra uma correlação forte (r = 0.75) entre altura e DAP. Isso significa que:\n\nÁrvores mais altas tendem a ter troncos mais espessos.\n\nO crescimento vertical está fortemente associado ao crescimento radial (espessamento do tronco).\n\nEmbora exista variação natural entre espécies e condições urbanas, o alinhamento geral dos pontos confirma um padrão estrutural consistente.\n\nA dispersão crescente em alturas maiores é esperada, pois espécies diferentes atingem proporções distintas mesmo em condições urbanas semelhantes.'
                },
                {
                    'titulo': 'Impactos e relevância',
                    'conteudo': 'Compreender essa relação é fundamental para o manejo urbano:\n\nEstimativa rápida do porte estrutural: o DAP pode ser usado como indicador confiável da altura provável de uma árvore quando medições completas não são possíveis.\n\nPlanejamento de podas e segurança: árvores com DAP elevado tendem a apresentar maior massa e exigem maior atenção em inspeções, especialmente em áreas com risco de queda.\n\nModelagem preditiva: a força da correlação justifica o uso de modelos estatísticos que utilizem o DAP para estimar biomassa, risco estrutural ou necessidade de manutenção.'
                },
                {
                    'titulo': 'Implicações práticas e conclusões',
                    'conteudo': 'Os resultados sugerem que o DAP é uma métrica robusta para representar o porte da árvore e apoiar decisões técnicas no contexto urbano.\n\nConclusões práticas:\n\nO DAP pode auxiliar na priorização de vistorias, concentrando esforços em árvores com maior potencial de massa e impacto urbano.\n\nA relação forte entre altura e DAP contribui para modelos de previsão de crescimento e para diagnósticos estruturais.\n\nDados dessa natureza são importantes para políticas públicas de arborização, permitindo gestão preventiva, eficiente e baseada em evidências.'
                }
            ]
            
            # Adiciona separador antes da análise
            card_body_content.append(html.Hr(style={'margin': '2rem 0', 'borderColor': COLORS['border']}))
            
            # Adiciona cada seção da análise
            for secao in secoes_analise:
                card_body_content.append(
                    html.Div([
                        html.H5(secao['titulo'], style={
                            'fontWeight': '700',
                            'color': COLORS['primary'],
                            'marginBottom': '1rem',
                            'fontSize': '1.1rem',
                            'marginTop': '0'
                        }),
                        html.P(
                            secao['conteudo'],
                            style={
                                'whiteSpace': 'pre-line',
                                'lineHeight': '1.8',
                                'color': COLORS['dark'],
                                'marginBottom': '1.5rem',
                                'textAlign': 'justify'
                            }
                        )
                    ], style={'marginBottom': '1.5rem', 'textAlign': 'left'})
                )
        
        card_content.append(
            dbc.CardBody(card_body_content, style={'padding': '1.5rem', 'textAlign': 'center'})
        )
        
        # Aplica offset
        col_class = "mb-4"
        if offset > 0:
            col_class += f" offset-lg-{offset}"
        
        card = dbc.Col([
            dbc.Card(card_content, style=card_style)
        ], width=12, lg=col_width, className=col_class)
        cards.append(card)
    
    return html.Div([
        html.P(
            f"Visualizações e gráficos gerados durante a análise dos dados do censo arbóreo. Total de {len(imagens)} visualização(ões) encontrada(s).",
            style={'color': COLORS['gray'], 'fontSize': '0.95rem', 'marginBottom': '2rem'}
        ),
        dbc.Row(cards, className="g-4")
    ])

def render_tela_react():
    """Renderiza a tela React em um iframe"""
    build_path = Path("tela_build")
    if build_path.exists() and (build_path / "index.html").exists():
        return html.Div([
            html.Iframe(
                src="/tela-react/",
                style={
                    'width': '100%',
                    'height': 'calc(100vh - 200px)',
                    'border': 'none',
                    'borderRadius': '12px'
                }
            )
        ])
    else:
        return dbc.Alert([
            html.H5("⚠️ Build do React não encontrado"),
            html.P("Execute o comando: cd tela && npm run build", className="mb-0")
        ], color="warning")

# ============================================
# ROTAS PARA SERVIR ARQUIVOS ESTÁTICOS DO REACT (mantidas as originais)
# ============================================
@server.route('/tela-react/')
@server.route('/tela-react/<path:path>')
def serve_react_app(path='index.html'):
    """Serve os arquivos estáticos do build do React"""
    build_dir = Path("tela_build")
    
    if not build_dir.exists():
        return "Build do React não encontrado. Execute: cd tela && npm run build", 404
    
    if path == '' or path == '/':
        path = 'index.html'
    
    file_path = build_dir / path
    
    if file_path.exists() and file_path.is_file():
        return send_file(str(file_path))
    elif path == 'index.html':
        # Se não encontrar index.html, tenta servir o que existe
        index_file = build_dir / 'index.html'
        if index_file.exists():
            return send_file(str(index_file))
        return "index.html não encontrado", 404
    else:
        # Para SPA, sempre retorna index.html para rotas não encontradas
        index_file = build_dir / 'index.html'
        if index_file.exists():
            return send_file(str(index_file))
        return "Arquivo não encontrado", 404

# ============================================
# FUNÇÃO PARA EXTRAIR IMAGENS DO NOTEBOOK (SIMPLIFICADA)
# ============================================

def extrair_imagens_notebook():
    """Extrai todas as imagens PNG dos outputs do notebook"""
    notebook_path = Path("notebook/Verdefica_Unificado_12nov2025.ipynb")
    imagens = []
    imagens_vistas = set()  # Para detectar duplicatas
    
    if not notebook_path.exists():
        return imagens
    
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        cells = nb.get('cells', [])
        
        for cell_idx, cell in enumerate(cells):
            if cell.get('cell_type') == 'code':
                outputs = cell.get('outputs', [])
                
                # Analisa o código da célula
                source_code = cell.get('source', [])
                if isinstance(source_code, list):
                    codigo_completo = ''.join(source_code).lower()
                else:
                    codigo_completo = str(source_code).lower()
                
                for output_idx, output in enumerate(outputs):
                    if output.get('output_type') == 'display_data':
                        data = output.get('data', {})
                        if 'image/png' in data:
                            img_data = data['image/png']
                            
                            # Verifica se a imagem já foi adicionada (remove duplicatas)
                            img_hash = hashlib.md5(img_data.encode('utf-8') if isinstance(img_data, str) else img_data).hexdigest()
                            if img_hash in imagens_vistas:
                                continue
                            imagens_vistas.add(img_hash)
                            
                            # Detecta número de eixos
                            titulo = None
                            num_axes = 1
                            if 'text/plain' in data:
                                text_plain = data['text/plain']
                                if isinstance(text_plain, list) and len(text_plain) > 0:
                                    titulo = text_plain[0]
                                    match = re.search(r'with (\d+) Axes?', titulo)
                                    if match:
                                        num_axes = int(match.group(1))
                            
                            # Gera ID único para o gráfico (baseado no índice sequencial)
                            grafico_id = f"GRAFICO_{len(imagens) + 1:03d}"
                            
                            imagens.append({
                                'imagem': img_data,
                                'id': grafico_id,
                                'codigo': codigo_completo,
                                'num_axes': num_axes,
                                'hash': img_hash,
                                'cell_idx': cell_idx,
                                'output_idx': output_idx
                            })
        
        # Identifica posições relativas para scatter plots específicos
        scatter_altura_dap = []
        scatter_altura_copa = []
        
        for i, img in enumerate(imagens):
            codigo = img['codigo']
            num_axes = img['num_axes']
            
            # Identifica scatter plots altura × DAP
            if (num_axes == 1 and 
                ('scatter' in codigo or 'scatterplot' in codigo) and
                'altura' in codigo and 'dap' in codigo):
                scatter_altura_dap.append(i)
            
            # Identifica scatter plots altura × Copa (sem DAP)
            if (num_axes == 1 and 
                ('scatter' in codigo or 'scatterplot' in codigo) and
                'altura' in codigo and 'copa' in codigo and
                'dap' not in codigo):
                scatter_altura_copa.append(i)
        
        # Marca posições relativas
        if len(scatter_altura_dap) > 0:
            ultimo_idx = scatter_altura_dap[-1]
            imagens[ultimo_idx]['posicao_relativa'] = 'ultimo'
        
        if len(scatter_altura_copa) >= 2:
            penultimo_idx = scatter_altura_copa[-2]
            imagens[penultimo_idx]['posicao_relativa'] = 'penultimo'
            # Remove outros scatter plots altura × copa exceto o penúltimo
            for i in reversed(scatter_altura_copa):
                if i != penultimo_idx:
                    imagens.pop(i)
        elif len(scatter_altura_copa) == 1:
            imagens[scatter_altura_copa[0]]['posicao_relativa'] = 'penultimo'
        
        # Filtros para remover gráficos específicos
        imagens_filtradas = []
        contador_rpa = 0
        contador_correlacao = 0
        
        for img in imagens:
            deve_remover = False
            codigo = img['codigo']
            num_axes = img['num_axes']
            
            # Remove gráfico com 3 eixos sobre distribuição do tamanho das copas
            if num_axes == 3 and 'distribuição do tamanho das copas' in codigo:
                deve_remover = True
            
            # Remove gráfico com 1 eixo sobre "relação entre duas variáveis"
            if num_axes == 1 and 'relação entre duas variáveis das árvores' in codigo:
                deve_remover = True
            
            # Remove dois gráficos sobre quantidade de árvores por RPA
            if 'quantidade de árvores por rpa no recife' in codigo:
                contador_rpa += 1
                if contador_rpa <= 2:
                    deve_remover = True
            
            # Remove gráfico sobre proporção de árvores por RPA
            if 'proporção de árvores por rpa no recife' in codigo:
                deve_remover = True
            
            # Remove uma das duplicatas do gráfico de correlação
            if (num_axes == 2 and 'correlação' in codigo and 'altura' in codigo and 
                'copa' in codigo and 'dap' in codigo):
                contador_correlacao += 1
                if contador_correlacao <= 1:
                    deve_remover = True
            
            if not deve_remover:
                imagens_filtradas.append(img)
        
        # Remove gráficos específicos por ID (mantém IDs estáticos - não renumerar)
        ids_para_remover = ['GRAFICO_004', 'GRAFICO_009', 'GRAFICO_010', 'GRAFICO_011', 
                           'GRAFICO_013', 'GRAFICO_016', 'GRAFICO_017', 'GRAFICO_018']
        imagens_filtradas = [img for img in imagens_filtradas if img['id'] not in ids_para_remover]
        
        # Ordena os gráficos por ID para manter a ordem correta (GRAFICO_001, GRAFICO_002, etc.)
        # Isso garante que os textos apareçam na ordem esperada, mesmo que alguns gráficos tenham sido removidos
        imagens_filtradas.sort(key=lambda x: x['id'])
        
        # IDs são estáticos - NÃO renumerar após filtragem
        # Os IDs originais (atribuídos na primeira passada) são mantidos
        # para preservar a associação correta com os textos de análise
        
        return imagens_filtradas
        
    except Exception as e:
        print(f"⚠️ Erro ao ler notebook: {e}")
        return []

# ============================================
# FUNÇÃO DE RENDERIZAÇÃO DO NOTEBOOK
# ============================================

if __name__ == '__main__':
    import os
    # Usa variável de ambiente PORT (fornecida pelo Render) ou porta padrão 8050
    port = int(os.environ.get('PORT', 8050))
    # Debug apenas em desenvolvimento local
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
    import os
    # Usa variável de ambiente PORT (fornecida pelo Render) ou porta padrão 8050
    port = int(os.environ.get('PORT', 8050))
    # Debug apenas em desenvolvimento local
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)