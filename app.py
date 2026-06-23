import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# =============================================================================
# CONFIGURACAO DA PAGINA
# =============================================================================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="\U0001f6e1",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# ESTILOS CUSTOMIZADOS - PALETA VERDE ESCURO + LARANJA
# =============================================================================
st.markdown("""
    <style>
    /* Fundo geral da pagina */
    .stApp {
        background-color: #0d2318;
    }
    /* Cabecalho principal */
    .main-header {
        background: linear-gradient(135deg, #0b3d2a, #1a5c3a);
        padding: 24px 30px;
        border-radius: 12px;
        margin-bottom: 24px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        border: 1px solid #2a7a4a;
    }
    .main-header h1 {
        font-size: 2.4rem;
        font-weight: 800;
        margin: 0 0 6px 0;
        letter-spacing: 1px;
        color: #ffffff;
    }
    .main-header p {
        font-size: 1.05rem;
        margin: 4px 0;
        opacity: 0.9;
        color: #d4f0e0;
    }
    .main-header small {
        font-size: 0.85rem;
        opacity: 0.75;
        color: #f59e0b;
    }
    /* Cards de upload */
    .upload-card {
        background: #122b1c;
        border: 1px solid #2a6640;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 10px;
    }
    /* Botao primario - laranja */
    .stButton > button[kind="primary"] {
        background-color: #f59e0b !important;
        color: #0d2318 !important;
        border: none !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #d97706 !important;
        color: #0d2318 !important;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0b2d1c !important;
        border-right: 1px solid #1e5c32 !important;
    }
    [data-testid="stSidebar"] .stMarkdown, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {
        color: #c8e6c9 !important;
    }
    /* Toggle / selectbox destaque laranja */
    [data-testid="stSidebar"] .stSelectbox label {
        color: #f59e0b !important;
        font-weight: 600 !important;
    }
    /* Rodape */
    .footer {
        text-align: center;
        color: #4a7a5a;
        margin-top: 50px;
        padding-top: 16px;
        border-top: 1px solid #1e4a2e;
        font-size: 12px;
    }
    /* Sidebar info */
    .sidebar-info {
        background: #122b1c;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 13px;
        color: #88b898;
    }
    /* Titulos das secoes */
    h2, h3 {
        color: #f59e0b !important;
    }
    /* Divider */
    hr {
        border-color: #1e5c32 !important;
    }
    /* Metricas */
    [data-testid="stMetric"] {
        background-color: #122b1c;
        border-radius: 8px;
        padding: 10px;
        border: 1px solid #2a6640;
    }
    [data-testid="stMetricLabel"] {
        color: #88b898 !important;
    }
    [data-testid="stMetricValue"] {
        color: #f59e0b !important;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# CABECALHO
# =============================================================================
st.markdown("""
<div class="main-header">
    <h1>&#x1F6E1; QGP Online</h1>
    <p>Atualizador de Indicadores de Seguran&#231;a P&#250;blica</p>
    <small>SUPESP &mdash; Cear&#225;</small>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 10px 0 6px 0;">
        <span style="font-size:2.5rem;">&#x1F6E1;</span><br>
        <span style="font-size:0.8rem; color:#f59e0b; font-weight:600; letter-spacing:2px;">SUPESP / CE</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Painel de Controle")
    st.divider()

    INDICADORES = [
        "Selecione um indicador...",
        "CVLI - Crimes Violentos Letais Intencionais",
        "CVP (SPORTAL) - Crimes Violentos ao Patrim\u00f4nio",
        "CVP (SIP) - Crimes Violentos ao Patrim\u00f4nio",
        "Perturba\u00e7\u00e3o do Sossego Alheio",
        "Outros Indicadores",
        "TODOS OS INDICADORES",
    ]
    indicador_selecionado = st.selectbox(
        "Selecione o Indicador",
        INDICADORES,
        help="Escolha qual indicador deseja processar"
    )
    st.divider()
    salvar_drive = st.toggle(
        "\U0001f4c2 Salvar no Google Drive",
        value=False,
        help="Envia o arquivo gerado automaticamente para uma pasta do Google Drive"
    )
    st.divider()
    agora = datetime.now()
    st.markdown(f"""
    <div class="sidebar-info">
        &#x1F4CC; <b>Vers&#227;o:</b> 1.0.0<br>
        &#x1F4C5; <b>Data:</b> {agora.strftime('%d/%m/%Y')}<br>
        &#x23F0; <b>Hora:</b> {agora.strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# AREA PRINCIPAL - UPLOADS
# =============================================================================
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("\U0001f4c4 Arquivo 02")
    st.caption("Arquivo principal com as metas e refer\u00eancias")
    arquivo_02 = st.file_uploader(
        "Envie o Arquivo 02",
        type=["xlsx", "xls"],
        key="arquivo_02",
        help="Selecione o Arquivo 02 no formato Excel (.xlsx ou .xls)"
    )
    if arquivo_02:
        st.success(f"\u2705 Carregado: {arquivo_02.name}")
        st.caption(f"Tamanho: {arquivo_02.size / 1024:.1f} KB")

with col2:
    st.subheader("\U0001f4c1 Arquivos 01")
    st.caption("Arquivos de entrada com os dados brutos")
    arquivos_01 = st.file_uploader(
        "Envie os Arquivos 01",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="arquivos_01",
        help="Selecione um ou mais Arquivos 01 no formato Excel"
    )
    if arquivos_01:
        for arq in arquivos_01:
            st.success(f"\u2705 {arq.name}")
        st.caption(f"Total: {len(arquivos_01)} arquivo(s) carregado(s)")

st.divider()

# =============================================================================
# PAINEL DE STATUS PRE-PROCESSAMENTO
# =============================================================================
if indicador_selecionado != "Selecione um indicador...":
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        status_02 = "\u2705 Pronto" if arquivo_02 else "\u274c Pendente"
        st.metric("Arquivo 02", status_02)
    with col_s2:
        status_01 = f"\u2705 {len(arquivos_01)} arquivo(s)" if arquivos_01 else "\u274c Pendente"
        st.metric("Arquivos 01", status_01)
    with col_s3:
        st.metric("Indicador", indicador_selecionado.split(" - ")[0] if " - " in indicador_selecionado else indicador_selecionado)
    st.divider()

# =============================================================================
# BOTAO DE PROCESSAMENTO
# =============================================================================
col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])
with col_btn2:
    btn_disabled = (
        indicador_selecionado == "Selecione um indicador..."
        or not arquivo_02
        or not arquivos_01
    )
    processar = st.button(
        "\u25b6\ufe0f Processar",
        type="primary",
        use_container_width=True,
        disabled=btn_disabled
    )

if btn_disabled and indicador_selecionado != "Selecione um indicador...":
    if not arquivo_02 and not arquivos_01:
        st.warning("\u26a0\ufe0f Envie o Arquivo 02 e os Arquivos 01 para habilitar o processamento.")
    elif not arquivo_02:
        st.warning("\u26a0\ufe0f Envie o Arquivo 02 para habilitar o processamento.")
    elif not arquivos_01:
        st.warning("\u26a0\ufe0f Envie pelo menos um Arquivo 01 para habilitar o processamento.")

# =============================================================================
# LOGICA DE PROCESSAMENTO
# =============================================================================
if processar:
    st.divider()
    st.subheader("\U0001f4cb Log de Processamento")
    log_area = st.empty()
    progress_bar = st.progress(0, text="Iniciando...")
    logs = []

    def log(mensagem: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entrada = f"[{timestamp}] {mensagem}"
        logs.append(entrada)
        log_area.code("\n".join(logs), language="bash")

    log(f"Indicador selecionado: {indicador_selecionado}")
    progress_bar.progress(10, text="Verificando arquivos...")
    log(f"Arquivo 02: {arquivo_02.name} ({arquivo_02.size / 1024:.1f} KB)")
    progress_bar.progress(30, text="Lendo Arquivo 02...")
    log(f"{len(arquivos_01)} Arquivo(s) 01 recebido(s):")
    for arq in arquivos_01:
        log(f"  -> {arq.name} ({arq.size / 1024:.1f} KB)")
    progress_bar.progress(60, text="Processando...")
    log("Modulo de processamento sera integrado na proxima versao.")
    progress_bar.progress(90, text="Finalizando...")
    log("Processamento concluido com sucesso.")
    progress_bar.progress(100, text="Concluido!")
    st.success("\u2705 Processamento finalizado com sucesso!")
    if salvar_drive:
        st.info("\U0001f4c2 Integracao com Google Drive sera ativada na proxima versao.")

# =============================================================================
# RODAPE
# =============================================================================
st.markdown("""
<div class="footer">
    QGP Online v1.0 &mdash; SUPESP/CE &mdash; Desenvolvido em Python + Streamlit
</div>
""", unsafe_allow_html=True)
