import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# =============================================================================
# CONFIGURACAO DA PAGINA
# =============================================================================
st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="shield",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# ESTILOS CUSTOMIZADOS
# =============================================================================
st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(90deg, #1a3a5c, #2e6da4);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            color: white;
            text-align: center;
        }
        .status-box {
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
        }
        .footer {
            text-align: center;
            color: #888;
            margin-top: 40px;
            font-size: 12px;
        }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# CABECALHO
# =============================================================================
st.markdown("""
    <div class="main-header">
        <h1>QGP Online</h1>
        <p>Atualizador de Indicadores de Seguranca Publica</p>
        <p><small>SUPESP / Ceara</small></p>
    </div>
""", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Bras%C3%A3o_do_Cear%C3%A1.svg/120px-Bras%C3%A3o_do_Cear%C3%A1.svg.png", width=80)
    st.title("Painel de Controle")
    st.divider()

    INDICADORES = [
        "Selecione um indicador...",
        "CVLI - Crimes Violentos Letais Intencionais",
        "CVP (SPORTAL) - Crimes Violentos ao Patrimonio",
        "CVP (SIP) - Crimes Violentos ao Patrimonio",
        "Perturbacao do Sossego Alheio",
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
        "Salvar resultado no Google Drive",
        value=False,
        help="Envia o arquivo gerado automaticamente para o Google Drive"
    )

    st.divider()
    st.caption(f"Versao: 1.0.0")
    st.caption(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# =============================================================================
# AREA PRINCIPAL
# =============================================================================
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("Arquivo 02")
    st.caption("Arquivo principal com as metas e referencias")
    arquivo_02 = st.file_uploader(
        "Envie o Arquivo 02",
        type=["xlsx", "xls"],
        key="arquivo_02",
        help="Selecione o Arquivo 02 no formato Excel"
    )
    if arquivo_02:
        st.success(f"Carregado: {arquivo_02.name}")

with col2:
    st.subheader("Arquivos 01")
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
            st.success(f"Carregado: {arq.name}")

st.divider()

# =============================================================================
# BOTAO DE PROCESSAMENTO
# =============================================================================
col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 2])

with col_btn2:
    processar = st.button(
        "Processar",
        type="primary",
        use_container_width=True,
        disabled=(indicador_selecionado == "Selecione um indicador...")
    )

# =============================================================================
# LOGICA DE PROCESSAMENTO
# =============================================================================
if processar:
    if not arquivo_02:
        st.error("Envie o Arquivo 02 antes de processar.")
    elif not arquivos_01:
        st.error("Envie ao menos um Arquivo 01 antes de processar.")
    else:
        st.divider()
        st.subheader("Log de Processamento")

        log_area = st.empty()
        progress_bar = st.progress(0)
        logs = []

        def log(mensagem: str, tipo: str = "info"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            entrada = f"[{timestamp}] {mensagem}"
            logs.append(entrada)
            log_area.code("\n".join(logs), language="bash")

        log(f"Iniciando processamento do indicador: {indicador_selecionado}")
        progress_bar.progress(10)

        log(f"Arquivo 02 recebido: {arquivo_02.name}")
        progress_bar.progress(30)

        log(f"{len(arquivos_01)} Arquivo(s) 01 recebido(s):")
        for arq in arquivos_01:
            log(f"  -> {arq.name}")
        progress_bar.progress(60)

        # Placeholder de processamento real
        log("Processamento em desenvolvimento. Modulo sera integrado em breve.")
        progress_bar.progress(90)

        log("Processamento concluido.")
        progress_bar.progress(100)

        st.success("Processamento finalizado com sucesso!")

        if salvar_drive:
            st.info("Integracao com Google Drive sera ativada na proxima versao.")

# =============================================================================
# RODAPE
# =============================================================================
st.markdown("""
    <div class="footer">
        QGP Online v1.0 &mdash; SUPESP/CE &mdash; Desenvolvido em Python + Streamlit
    </div>
""", unsafe_allow_html=True)
