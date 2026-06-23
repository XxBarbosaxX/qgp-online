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
# ESTILOS CUSTOMIZADOS
# =============================================================================
st.markdown("""
    <style>
        /* Cabecalho principal */
        .main-header {
            background: linear-gradient(90deg, #1a3a5c, #2e6da4);
            padding: 24px 30px;
            border-radius: 12px;
            margin-bottom: 24px;
            color: white;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .main-header h1 {
            font-size: 2.4rem;
            font-weight: 800;
            margin: 0 0 6px 0;
            letter-spacing: 1px;
        }
        .main-header p {
            font-size: 1.05rem;
            margin: 4px 0;
            opacity: 0.9;
        }
        .main-header small {
            font-size: 0.85rem;
            opacity: 0.75;
        }
        /* Cards de upload */
        .upload-card {
            background: #1e2530;
            border: 1px solid #2e4060;
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 10px;
        }
        /* Rodape */
        .footer {
            text-align: center;
            color: #666;
            margin-top: 50px;
            padding-top: 16px;
            border-top: 1px solid #2e2e2e;
            font-size: 12px;
        }
        /* Sidebar info */
        .sidebar-info {
            background: #1e2530;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 13px;
            color: #aaa;
        }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# CABECALHO
# =============================================================================
st.markdown("""
    <div class="main-header">
        <h1>\U0001f6e1 QGP Online</h1>
        <p>Atualizador de Indicadores de Seguran\u00e7a P\u00fablica</p>
        <small>SUPESP &mdash; Cear\u00e1</small>
    </div>
""", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    # Brasao usando markdown com emoji como substituto visual
    st.markdown("""
        <div style="text-align:center; padding: 10px 0 5px 0;">
            <span style="font-size: 3rem;">\U0001f6e1</span><br>
            <span style="font-size: 0.75rem; color: #aaa; letter-spacing: 1px;">SUPESP / CE</span>
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

    # Data e hora dinamica (atualizada a cada execucao)
    agora = datetime.now()
    st.markdown(f"""
        <div class="sidebar-info">
            \U0001f4cc <b>Vers\u00e3o:</b> 1.0.0<br>
            \U0001f4c5 <b>Data:</b> {agora.strftime('%d/%m/%Y')}<br>
            \u23f0 <b>Hora:</b> {agora.strftime('%H:%M:%S')}
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
