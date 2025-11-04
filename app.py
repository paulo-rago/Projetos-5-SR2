import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import numpy as np

# Configuracao da pagina
st.set_page_config(
    page_title="Censo Arboreo de Recife",
    page_icon=":deciduous_tree:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cache do dataset
@st.cache_data
def load_data():
    """Carrega o dataset limpo"""
    arquivo = Path("censo_arboreo_final.csv")
    df = pd.read_csv(arquivo, low_memory=False)
    
    # Converter datas se necessario
    if 'data_plantio' in df.columns:
        df['data_plantio'] = pd.to_datetime(df['data_plantio'], errors='coerce')
    if 'data_monitoramento' in df.columns:
        df['data_monitoramento'] = pd.to_datetime(df['data_monitoramento'], errors='coerce')
    
    return df

# Sidebar - Filtros
st.sidebar.header("Filtros")
df = load_data()

# Filtros principais
rpa_options = ['Todos'] + sorted(df['rpa'].dropna().unique().tolist())
rpa_selected = st.sidebar.selectbox("RPA", rpa_options)

if rpa_selected != 'Todos':
    df = df[df['rpa'] == rpa_selected]

# Filtro por bairro
if 'bairro_nome' in df.columns:
    bairro_options = ['Todos'] + sorted(df['bairro_nome'].dropna().unique().tolist())
    bairro_selected = st.sidebar.selectbox("Bairro", bairro_options)
    
    if bairro_selected != 'Todos':
        df = df[df['bairro_nome'] == bairro_selected]

# Filtro por estado fitossanitario
if 'fitossanid_grupo' in df.columns:
    fitossanid_options = ['Todos'] + sorted(df['fitossanid_grupo'].dropna().unique().tolist())
    fitossanid_selected = st.sidebar.selectbox("Estado Fitossanitario", fitossanid_options)
    
    if fitossanid_selected != 'Todos':
        df = df[df['fitossanid_grupo'] == fitossanid_selected]

# Filtro por especie
if 'nome_popular_padrao' in df.columns:
    especie_options = ['Todos'] + sorted(df['nome_popular_padrao'].dropna().unique().tolist())
    especie_selected = st.sidebar.selectbox("Especie", especie_options)
    
    if especie_selected != 'Todos':
        df = df[df['nome_popular_padrao'] == especie_selected]

# Titulo principal
st.title("Dashboard - Censo Arboreo de Recife")
st.markdown("---")

# Metricas principais
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de Arvores", f"{len(df):,}")
    
with col2:
    if 'rpa' in df.columns:
        st.metric("RPAs Unicos", df['rpa'].nunique())
    
with col3:
    if 'bairro_nome' in df.columns:
        st.metric("Bairros Unicos", df['bairro_nome'].nunique())
    
with col4:
    if 'nome_popular_padrao' in df.columns:
        st.metric("Especies Unicas", df['nome_popular_padrao'].nunique())

st.markdown("---")

# Tabs para diferentes visualizacoes
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Visao Geral",
    "Mapa Interativo",
    "Analises Estatisticas",
    "Especies",
    "Analise Temporal"
])

with tab1:
    st.header("Distribuicao por RPA")
    
    if 'rpa' in df.columns:
        rpa_counts = df['rpa'].value_counts().sort_index()
        fig_rpa = px.bar(
            x=rpa_counts.index,
            y=rpa_counts.values,
            labels={'x': 'RPA', 'y': 'Quantidade de Arvores'},
            title="Distribuicao de Arvores por RPA"
        )
        st.plotly_chart(fig_rpa, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top 10 Bairros")
        if 'bairro_nome' in df.columns:
            top_bairros = df['bairro_nome'].value_counts().head(10)
            fig_bairros = px.bar(
                x=top_bairros.values,
                y=top_bairros.index,
                orientation='h',
                labels={'x': 'Quantidade', 'y': 'Bairro'},
                title="Top 10 Bairros com Mais Arvores"
            )
            st.plotly_chart(fig_bairros, use_container_width=True)
    
    with col2:
        st.subheader("Estado Fitossanitario")
        if 'fitossanid_grupo' in df.columns:
            fitossanid_counts = df['fitossanid_grupo'].value_counts()
            fig_fito = px.pie(
                values=fitossanid_counts.values,
                names=fitossanid_counts.index,
                title="Distribuicao por Estado Fitossanitario"
            )
            st.plotly_chart(fig_fito, use_container_width=True)
    
    # Grafico de injuria
    if 'injuria_grupo' in df.columns:
        st.subheader("Tipo de Injuria")
        injuria_counts = df['injuria_grupo'].value_counts()
        fig_injuria = px.bar(
            x=injuria_counts.index,
            y=injuria_counts.values,
            labels={'x': 'Tipo de Injuria', 'y': 'Quantidade'},
            title="Distribuicao por Tipo de Injuria"
        )
        st.plotly_chart(fig_injuria, use_container_width=True)

with tab2:
    st.header("Mapa Interativo das Arvores")
    
    # Sub-tabs para diferentes tipos de mapa
    sub_tab1, sub_tab2 = st.tabs(["Mapa Plotly", "Mapa Folium"])
    
    with sub_tab1:
        if 'longitude' in df.columns and 'latitude' in df.columns:
            # Filtrar coordenadas validas
            df_map = df[df['longitude'].notna() & df['latitude'].notna()].copy()
            
            if len(df_map) > 0:
                # Limitar a 10.000 pontos para performance
                if len(df_map) > 10000:
                    st.warning(f"Mostrando 10.000 pontos aleatorios de {len(df_map):,} total")
                    df_map = df_map.sample(n=10000, random_state=42)
                
                # Opcoes de coloracao
                color_option = st.selectbox(
                    "Colorir por:",
                    ['RPA', 'Estado Fitossanitario', 'Tipo de Injuria', 'Especie'],
                    key='map_color'
                )
                
                color_col = None
                if color_option == 'RPA' and 'rpa' in df_map.columns:
                    color_col = 'rpa'
                elif color_option == 'Estado Fitossanitario' and 'fitossanid_grupo' in df_map.columns:
                    color_col = 'fitossanid_grupo'
                elif color_option == 'Tipo de Injuria' and 'injuria_grupo' in df_map.columns:
                    color_col = 'injuria_grupo'
                elif color_option == 'Especie' and 'nome_popular_padrao' in df_map.columns:
                    color_col = 'nome_popular_padrao'
                
                # Usar go.Scattermapbox com estilo que nao precisa de token
                fig_map = go.Figure()
                
                if color_col:
                    # Agrupar por cor se houver coloracao
                    for grupo in df_map[color_col].dropna().unique():
                        df_grupo = df_map[df_map[color_col] == grupo]
                        fig_map.add_trace(go.Scattermapbox(
                            lat=df_grupo['latitude'],
                            lon=df_grupo['longitude'],
                            mode='markers',
                            marker=dict(size=5, opacity=0.6),
                            name=str(grupo),
                            text=df_grupo.get('bairro_nome', ''),
                            hovertemplate='<b>%{text}</b><br>' +
                                         'Lat: %{lat:.4f}<br>' +
                                         'Lon: %{lon:.4f}<extra></extra>'
                        ))
                else:
                    # Sem coloracao, todos os pontos juntos
                    fig_map.add_trace(go.Scattermapbox(
                        lat=df_map['latitude'],
                        lon=df_map['longitude'],
                        mode='markers',
                        marker=dict(size=5, opacity=0.6),
                        text=df_map.get('bairro_nome', ''),
                        hovertemplate='<b>%{text}</b><br>' +
                                     'Lat: %{lat:.4f}<br>' +
                                     'Lon: %{lon:.4f}<extra></extra>'
                    ))
                
                # Configurar layout do mapa
                fig_map.update_layout(
                    mapbox=dict(
                        style="open-street-map",
                        center=dict(
                            lat=df_map['latitude'].mean(),
                            lon=df_map['longitude'].mean()
                        ),
                        zoom=11
                    ),
                    height=600,
                    title="Distribuicao Geografica das Arvores",
                    showlegend=True if color_col else False
                )
                
                st.plotly_chart(fig_map, use_container_width=True)
                
                # Estatisticas do mapa
                st.subheader("Estatisticas do Mapa")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"Total de pontos no mapa: {len(df_map):,}")
                with col2:
                    if color_col:
                        st.write(f"Coloracao por: {color_option}")
            else:
                st.warning("Nao ha coordenadas validas para exibir no mapa.")
        else:
            st.warning("Colunas de coordenadas nao encontradas no dataset.")
    
    with sub_tab2:
        st.subheader("Mapa Folium Interativo de Recife")
        
        try:
            from pyproj import Transformer
            import folium
            from folium.plugins import FastMarkerCluster
            from streamlit_folium import st_folium
            
            # Filtrar RPAs validas e coordenadas existentes
            if 'rpa' in df.columns and 'x' in df.columns and 'y' in df.columns:
                df_mapa = df[df['rpa'].between(1, 6)].copy()
                df_mapa = df_mapa[df_mapa['x'].notna() & df_mapa['y'].notna()]
                
                if len(df_mapa) > 0:
                    # Limitar a 50.000 pontos para performance
                    if len(df_mapa) > 50000:
                        st.warning(f"Mostrando 50.000 pontos aleatorios de {len(df_mapa):,} total para melhor performance")
                        df_mapa = df_mapa.sample(n=50000, random_state=42)
                    
                    # Converter de UTM 25S para WGS84 (lon/lat)
                    transformer = Transformer.from_crs("EPSG:31985", "EPSG:4326", always_xy=True)
                    
                    lon, lat = transformer.transform(df_mapa['x'].values, df_mapa['y'].values)
                    df_mapa['lon'] = lon
                    df_mapa['lat'] = lat
                    
                    # Criar mapa interativo em Recife
                    center = [df_mapa['lat'].mean(), df_mapa['lon'].mean()]
                    m = folium.Map(location=center, zoom_start=12, tiles="CartoDB positron")
                    
                    locs = df_mapa[['lat','lon']].values.tolist()
                    FastMarkerCluster(locs).add_to(m)
                    
                    # Exibir mapa no Streamlit
                    st_folium(m, width=1200, height=600, returned_objects=[])
                    
                    # Estatisticas
                    st.subheader("Estatisticas do Mapa Folium")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total de Arvores no Mapa", f"{len(df_mapa):,}")
                    with col2:
                        st.metric("RPAs Unicas", df_mapa['rpa'].nunique())
                    with col3:
                        if 'bairro_nome' in df_mapa.columns:
                            st.metric("Bairros Unicos", df_mapa['bairro_nome'].nunique())
                else:
                    st.warning("Nao ha coordenadas UTM validas para exibir no mapa.")
            else:
                st.warning("Colunas necessarias (rpa, x, y) nao encontradas no dataset.")
                
        except ImportError as e:
            st.error(f"Bibliotecas pyproj ou folium nao instaladas. Instale com: pip install pyproj folium streamlit-folium")
            st.code("pip install pyproj folium streamlit-folium")
        except Exception as e:
            st.error(f"Erro ao gerar mapa Folium: {e}")
            st.exception(e)

with tab3:
    st.header("Analises Estatisticas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribuicao de Altura")
        if 'altura' in df.columns:
            df_altura = df[df['altura'].notna() & (df['altura'] > 0)]
            if len(df_altura) > 0:
                fig_altura = px.histogram(
                    df_altura,
                    x='altura',
                    nbins=50,
                    labels={'altura': 'Altura (m)', 'count': 'Frequencia'},
                    title="Distribuicao de Altura das Arvores"
                )
                st.plotly_chart(fig_altura, use_container_width=True)
                
                col_met1, col_met2 = st.columns(2)
                with col_met1:
                    st.metric("Altura Media", f"{df_altura['altura'].mean():.2f} m")
                with col_met2:
                    st.metric("Altura Maxima", f"{df_altura['altura'].max():.2f} m")
    
    with col2:
        st.subheader("Distribuicao de DAP")
        if 'dap' in df.columns:
            df_dap = df[df['dap'].notna() & (df['dap'] > 0)]
            if len(df_dap) > 0:
                fig_dap = px.histogram(
                    df_dap,
                    x='dap',
                    nbins=50,
                    labels={'dap': 'DAP (cm)', 'count': 'Frequencia'},
                    title="Distribuicao de DAP das Arvores"
                )
                st.plotly_chart(fig_dap, use_container_width=True)
                
                col_met3, col_met4 = st.columns(2)
                with col_met3:
                    st.metric("DAP Medio", f"{df_dap['dap'].mean():.2f} cm")
                with col_met4:
                    st.metric("DAP Maximo", f"{df_dap['dap'].max():.2f} cm")
    
    # Relacao entre variaveis
    st.subheader("Relacao entre Variaveis")
    col3, col4 = st.columns(2)
    
    with col3:
        if 'altura' in df.columns and 'dap' in df.columns:
            df_rel = df[(df['altura'].notna() & df['altura'] > 0) & 
                       (df['dap'].notna() & df['dap'] > 0)]
            if len(df_rel) > 0:
                fig_scatter = px.scatter(
                    df_rel,
                    x='dap',
                    y='altura',
                    labels={'dap': 'DAP (cm)', 'altura': 'Altura (m)'},
                    title="Relacao entre DAP e Altura",
                    trendline="ols"
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
    
    with col4:
        if 'copa' in df.columns:
            df_copa = df[df['copa'].notna() & (df['copa'] > 0)]
            if len(df_copa) > 0:
                fig_copa = px.histogram(
                    df_copa,
                    x='copa',
                    nbins=50,
                    labels={'copa': 'Copa (m)', 'count': 'Frequencia'},
                    title="Distribuicao de Copa"
                )
                st.plotly_chart(fig_copa, use_container_width=True)
                st.metric("Copa Media", f"{df_copa['copa'].mean():.2f} m")

with tab4:
    st.header("Analise por Especies")
    
    if 'nome_popular_padrao' in df.columns:
        st.subheader("Top 20 Especies Mais Comuns")
        top_especies = df['nome_popular_padrao'].value_counts().head(20)
        
        fig_especies = px.bar(
            x=top_especies.values,
            y=top_especies.index,
            orientation='h',
            labels={'x': 'Quantidade', 'y': 'Especie'},
            title="Top 20 Especies Mais Comuns"
        )
        st.plotly_chart(fig_especies, use_container_width=True)
        
        # Analise detalhada por especie
        st.subheader("Analise Detalhada por Especie")
        especie_selected_detail = st.selectbox(
            "Selecione uma especie para ver detalhes:",
            ['Todas'] + sorted(df['nome_popular_padrao'].dropna().unique().tolist()),
            key='especie_detail'
        )
        
        if especie_selected_detail != 'Todas':
            df_especie = df[df['nome_popular_padrao'] == especie_selected_detail]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total", len(df_especie))
            with col2:
                if 'altura' in df_especie.columns:
                    altura_media = df_especie['altura'].mean() if df_especie['altura'].notna().any() else 0
                    st.metric("Altura Media", f"{altura_media:.2f} m")
            with col3:
                if 'dap' in df_especie.columns:
                    dap_medio = df_especie['dap'].mean() if df_especie['dap'].notna().any() else 0
                    st.metric("DAP Medio", f"{dap_medio:.2f} cm")
            
            # Distribuicao geografica da especie
            if 'rpa' in df_especie.columns:
                st.subheader(f"Distribuicao por RPA - {especie_selected_detail}")
                especie_rpa = df_especie['rpa'].value_counts().sort_index()
                fig_especie_rpa = px.bar(
                    x=especie_rpa.index,
                    y=especie_rpa.values,
                    labels={'x': 'RPA', 'y': 'Quantidade'},
                    title=f"Distribuicao por RPA"
                )
                st.plotly_chart(fig_especie_rpa, use_container_width=True)
            
            # Tabela com dados
            st.subheader("Dados da Especie Selecionada")
            st.dataframe(df_especie.head(100), use_container_width=True)

with tab5:
    st.header("Analise Temporal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'data_plantio' in df.columns:
            st.subheader("Plantio ao Longo do Tempo")
            df_plantio = df[df['data_plantio'].notna()].copy()
            
            if len(df_plantio) > 0:
                df_plantio['ano'] = df_plantio['data_plantio'].dt.year
                plantio_ano = df_plantio['ano'].value_counts().sort_index()
                
                fig_temporal = px.line(
                    x=plantio_ano.index,
                    y=plantio_ano.values,
                    labels={'x': 'Ano', 'y': 'Quantidade de Plantios'},
                    title="Plantios por Ano"
                )
                st.plotly_chart(fig_temporal, use_container_width=True)
                
                st.metric("Total de Plantios Registrados", len(df_plantio))
                st.metric("Ano com Mais Plantios", 
                         df_plantio['ano'].value_counts().idxmax() if len(df_plantio) > 0 else "N/A")
    
    with col2:
        if 'data_monitoramento' in df.columns:
            st.subheader("Monitoramento ao Longo do Tempo")
            df_monitor = df[df['data_monitoramento'].notna()].copy()
            
            if len(df_monitor) > 0:
                df_monitor['ano'] = df_monitor['data_monitoramento'].dt.year
                monitor_ano = df_monitor['ano'].value_counts().sort_index()
                
                fig_monitor = px.bar(
                    x=monitor_ano.index,
                    y=monitor_ano.values,
                    labels={'x': 'Ano', 'y': 'Quantidade de Monitoramentos'},
                    title="Monitoramentos por Ano"
                )
                st.plotly_chart(fig_monitor, use_container_width=True)
                
                st.metric("Total de Monitoramentos", len(df_monitor))
    
    # Distribuicao mensal
    if 'data_plantio' in df.columns:
        st.subheader("Distribuicao Mensal de Plantios")
        df_plantio_mes = df[df['data_plantio'].notna()].copy()
        
        if len(df_plantio_mes) > 0:
            df_plantio_mes['mes'] = df_plantio_mes['data_plantio'].dt.month
            df_plantio_mes['mes_nome'] = df_plantio_mes['data_plantio'].dt.strftime('%B')
            plantio_mes = df_plantio_mes['mes'].value_counts().sort_index()
            
            meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                          'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
            plantio_mes.index = [meses_nomes[int(i)-1] if i > 0 and i <= 12 else str(i) for i in plantio_mes.index]
            
            fig_mes = px.bar(
                x=plantio_mes.index,
                y=plantio_mes.values,
                labels={'x': 'Mes', 'y': 'Quantidade'},
                title="Plantios por Mes"
            )
            st.plotly_chart(fig_mes, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("**Fonte:** Prefeitura do Recife - Portal de Dados Abertos")

