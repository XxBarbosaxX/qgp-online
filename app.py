from __future__ import annotations

import os
import sys
import hmac
import hashlib
import importlib
from datetime import datetime

import streamlit as st


# ── Configuração inicial ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="QGP Online - SUPESP/CE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = os.path.dirname(__file__)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

MODULOS_DIR = os.path.join(BASE_DIR, "modulos")
if MODULOS_DIR not in sys.path:
    sys.path.insert(0, MODULOS_DIR)


# ── Usuários autorizados ─────────────────────────────────────────────────────

def gerar_hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


USUARIOS = {
    "admin": {
        "nome": "Administrador",
        "senha_hash": gerar_hash_senha("123456"),
        "perfil": "admin",
    },
    "clebio": {
        "nome": "Clébio Barbosa",
        "senha_hash": gerar_hash_senha("senha_segura_2026"),
        "perfil": "admin",
    },
}


# ── Mapeamento dos módulos ───────────────────────────────────────────────────

MAPEAMENTO = {
    "CVLI": ("cvli", "interface_cvli"),
    "CVP (SPORTAL)": ("cvp_sportal", "interface_cvp_sportal"),
    "CVP (SIP)": ("cvp_sip", "interface_cvp_sip"),
    "PERTURBAÇÃO AO SOSSEGO ALHEIO": ("perturbacao_sossego", "interface_perturbacao_sossego"),
    "DESLOCAMENTO FORÇADO": ("deslocamento_forcado", "interface_deslocamento_forcado"),
    "ROUBO DE VEÍCULO (SPORTAL)": ("roubo_veiculo_sportal", "interface_roubo_veiculo_sportal"),
    "ROUBO DE VEÍCULO (SIP)": ("roubo_veiculo_sip", "interface_roubo_veiculo_sip"),
    "ACIDENTE DE TRÂNSITO": ("acidente_transito", "interface_acidente_transito"),
    "FURTO DE VEÍCULO (SPORTAL)": ("furto_veiculo_sportal", "interface_furto_veiculo_sportal"),
    "FURTO DE VEÍCULO (SIP)": ("furto_veiculo_sip", "interface_furto_veiculo_sip"),
    "TODOS OS INDICADORES": ("todos_indicadores", "interface_todos_indicadores"),
}

INDICADORES_HOME = [
    "CVLI",
    "CVP (SPORTAL)",
    "CVP (SIP)",
    "PERTURBAÇÃO AO SOSSEGO ALHEIO",
    "DESLOCAMENTO FORÇADO",
    "ROUBO DE VEÍCULO (SPORTAL)",
    "ROUBO DE VEÍCULO (SIP)",
    "ACIDENTE DE TRÂNSITO",
    "FURTO DE VEÍCULO (SPORTAL)",
    "FURTO DE VEÍCULO (SIP)",
    "TODOS OS INDICADORES",
]


# ── Estado da aplicação ──────────────────────────────────────────────────────

def init_state():
    defaults = {
        "autenticado": False,
        "usuario_logado": None,
        "nome_usuario_logado": None,
        "perfil_usuario_logado": None,
        "indicador_selecionado": "Selecione um indicador...",
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


# ── Estilo visual ────────────────────────────────────────────────────────────

def load_custom_css():
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #032822 0%, #011714 100%);
            color: #f3f4ef;
        }

        section[data-testid="stSidebar"] {
            display: none !important;
        }

        .block-container {
            padding-top: 2.0rem !important;
            padding-bottom: 2rem;
            max-width: 1280px;
        }

        .topbar-wrap {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            margin-bottom: 1.4rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid rgba(243, 154, 31, 0.18);
        }

        .topbar-title {
            font-size: 2.15rem;
            font-weight: 900;
            color: #ffffff;
            line-height: 1.1;
            margin: 0;
        }

        .topbar-subtitle {
            font-size: 0.96rem;
            font-weight: 800;
            color: #f39a1f;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-top: 0.35rem;
        }

        .card-box {
            background: rgba(255, 255, 255, 0.035);
            border: 1px solid rgba(243, 154, 31, 0.16);
            border-radius: 18px;
            padding: 1.4rem;
            margin-bottom: 1rem;
        }

        .login-box {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(243, 154, 31, 0.20);
            border-radius: 18px;
            padding: 1.6rem;
            margin-top: 2rem;
        }

        .card-title {
            font-size: 1.35rem;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 0.35rem;
        }

        .card-subtitle {
            color: #d0d8d3;
            font-size: 0.98rem;
            line-height: 1.5;
            margin-bottom: 0.25rem;
        }

        .chip {
            display: inline-block;
            background: rgba(243, 154, 31, 0.12);
            color: #ffd089;
            border: 1px solid rgba(243, 154, 31, 0.22);
            border-radius: 999px;
            padding: 0.35rem 0.8rem;
            font-size: 0.84rem;
            font-weight: 700;
            margin-right: 0.45rem;
            margin-bottom: 0.45rem;
        }

        .footer-note {
            color: #b8c3bd;
            font-size: 0.90rem;
            margin-top: 1.4rem;
            text-align: center;
        }

        .login-help {
            color: #c7d2cc;
            font-size: 0.92rem;
            margin-top: 0.5rem;
            line-height: 1.5;
        }

        div[data-testid="stForm"] {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
        }

        .stButton > button,
        div[data-testid="stFormSubmitButton"] > button {
            background: #f39a1f !important;
            color: #16211d !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 900 !important;
            font-size: 0.98rem !important;
            min-height: 3rem !important;
            width: 100% !important;
        }

        .stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover {
            background: #ffae34 !important;
            color: #101816 !important;
        }

        .secondary-button .stButton > button {
            background: transparent !important;
            color: #f3f4ef !important;
            border: 1px solid rgba(243, 154, 31, 0.28) !important;
            font-weight: 800 !important;
        }

        .secondary-button .stButton > button:hover {
            background: rgba(243, 154, 31, 0.08) !important;
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Autenticação ─────────────────────────────────────────────────────────────

def verificar_senha(senha_digitada: str, senha_hash_armazenada: str) -> bool:
    senha_hash_digitada = gerar_hash_senha(senha_digitada)
    return hmac.compare_digest(senha_hash_digitada, senha_hash_armazenada)


def autenticar_usuario(usuario: str, senha: str) -> bool:
    usuario = usuario.strip().lower()

    if usuario not in USUARIOS:
        return False

    cadastro = USUARIOS[usuario]
    if not verificar_senha(senha, cadastro["senha_hash"]):
        return False

    st.session_state.autenticado = True
    st.session_state.usuario_logado = usuario
    st.session_state.nome_usuario_logado = cadastro["nome"]
    st.session_state.perfil_usuario_logado = cadastro["perfil"]
    return True


def logout():
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None
    st.session_state.nome_usuario_logado = None
    st.session_state.perfil_usuario_logado = None
    st.session_state.indicador_selecionado = "Selecione um indicador..."
    st.rerun()


# ── Layout principal ─────────────────────────────────────────────────────────

def render_topbar():
    col1, col2 = st.columns([8, 2])

    with col1:
        st.markdown(
            """
            <div class="topbar-wrap">
                <div>
                    <div class="topbar-title">QGP Online</div>
                    <div class="topbar-subtitle">SUPESP / CE · Atualizador de Indicadores</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        if st.session_state.autenticado:
            st.markdown(
                f"**Usuário:** {st.session_state.nome_usuario_logado}<br>"
                f"**Perfil:** {st.session_state.perfil_usuario_logado}",
                unsafe_allow_html=True,
            )
            st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
            if st.button("Sair", key="btn_logout", use_container_width=True):
                logout()
            st.markdown("</div>", unsafe_allow_html=True)


def render_login():
    st.markdown(
        """
        <div class="login-box">
            <div class="card-title">Acesso ao Sistema</div>
            <div class="card-subtitle">Informe seu usuário e senha para acessar o QGP Online.</div>
            <div class="login-help">O acesso é validado antes da liberação dos módulos de processamento.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            entrar = st.form_submit_button("Entrar", use_container_width=True)

        if entrar:
            if autenticar_usuario(usuario, senha):
                st.success("Login realizado com sucesso.")
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")


def selecionar_indicador(nome: str):
    st.session_state.indicador_selecionado = nome


def voltar_inicio():
    st.session_state.indicador_selecionado = "Selecione um indicador..."
    st.rerun()


def render_home():
    st.markdown(
        """
        <div class="card-box">
            <div class="card-title">Bem-vindo ao QGP Online</div>
            <div class="card-subtitle">Sistema de atualização de indicadores de Segurança Pública da SUPESP/CE.</div>
            <div class="card-subtitle">Selecione o indicador desejado para iniciar o processamento.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Selecione o indicador abaixo:")

    col1, col2, col3 = st.columns(3)

    blocos = [
        INDICADORES_HOME[0:4],
        INDICADORES_HOME[4:8],
        INDICADORES_HOME[8:11],
    ]

    for coluna, bloco in zip([col1, col2, col3], blocos):
        with coluna:
            for nome in bloco:
                if st.button(nome, key=f"btn_{nome}", use_container_width=True):
                    selecionar_indicador(nome)
                    st.rerun()

    st.markdown(
        f'<div class="chip">Versão 1.0.0</div>'
        f'<div class="chip">Data {datetime.now().strftime("%d/%m/%Y")}</div>'
        f'<div class="chip">Hora {datetime.now().strftime("%H:%M:%S")}</div>',
        unsafe_allow_html=True,
    )


# ── Carregamento dinâmico dos módulos ────────────────────────────────────────

def carregar_modulo(nome_modulo: str, nome_funcao: str):
    try:
        modulo = importlib.import_module(f"modulos.{nome_modulo}")
        return getattr(modulo, nome_funcao, None)
    except Exception as exc:
        st.error(f"Erro ao carregar módulo '{nome_modulo}': {exc}")
        return None


def render_modulo():
    indicador = st.session_state.indicador_selecionado

    if indicador == "Selecione um indicador...":
        render_home()
        return

    if indicador not in MAPEAMENTO:
        st.warning(f"O indicador {indicador} estará disponível em breve.")
        return

    col_topo_1, col_topo_2 = st.columns([10, 2])

    with col_topo_2:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("← Voltar", use_container_width=True):
            voltar_inicio()
        st.markdown("</div>", unsafe_allow_html=True)

    nome_modulo, nome_funcao = MAPEAMENTO[indicador]
    funcao = carregar_modulo(nome_modulo, nome_funcao)

    if funcao:
        funcao()


# ── Execução principal ───────────────────────────────────────────────────────

init_state()
load_custom_css()
render_topbar()

if not st.session_state.autenticado:
    render_login()
else:
    render_modulo()

st.markdown(
    '<p class="footer-note">QGP Online — Atualizador de Indicadores de Segurança Pública — SUPESP/CE</p>',
    unsafe_allow_html=True,
)
