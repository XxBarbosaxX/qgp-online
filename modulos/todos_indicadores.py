"""<br>Módulo TODOS OS INDICADORES<br><br>Processamento consolidado de múltiplos indicadores.<br><br>Chama os módulos individuais com suas lógicas reais (incluindo geocodificação).<br><br>"""
from __future__ import annotations

import re
import unicodedata
import zipfile
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from modulos.acidente_transito import processar_acidente_transito
from modulos.cvli import ProcessadorCVLI
from modulos.cvp_sip import processar_cvp_sip
from modulos.deslocamento_forcado import processar_deslocamento_forcado
from modulos.furto_veiculo_sip import processar_furto_veiculo_sip
from modulos.furto_veiculo_sportal import processar_furto_veiculo_sportal
from modulos.perturbacao_sossego import processar_perturbacao_sossego
from modulos.roubo_veiculo_sip import processar_roubo_veiculo_sip
from modulos.roubo_veiculo_sportal import processar_roubo_veiculo_sportal
from modulos.utils import (
    alinhar_colunas_com_base,
    converter_coordenadas_para_wgs84_auto,
    criar_coluna_datahora,
    encontrar_coluna_data,
    encontrar_coluna_hora,
    encontrar_coluna_por_nomes,
    excluir_coordenadas_invalidas,
    filtrar_apenas_registros_posteriores,
    nome_arquivo_padrao,
    normalizar_colunas,
    obter_ultima_datahora,
    renomear_colunas_equivalentes,
)

INDICADORES_CONFIG = {
    "CVLI": {
        "ordem": 1,
        "label": "CVLI",
        "key": "cvli",
        "nome_arquivo": f"1-CVLI-{datetime.now().year}-QGP.xlsx",
        "geocodifica": False,
    },
    "CVP (SPORTAL)": {
        "ordem": 2,
        "label": "CVP (SPORTAL)",
        "key": "cvp_sportal",
        "nome_arquivo": nome_arquivo_padrao(2, "CVP-SPORTAL"),
        "geocodifica": False,
    },
    "CVP (SIP)": {
        "ordem": 3,
        "label": "CVP (SIP)",
        "key": "cvp_sip",
        "nome_arquivo": nome_arquivo_padrao(3, "CVP-SIP-ENDERECO"),
        "geocodifica": True,
    },
    "PERTURBAÇÃO AO SOSSEGO ALHEIO": {
        "ordem": 4,
        "label": "PERTURBAÇÃO AO SOSSEGO ALHEIO",
        "key": "perturbacao_sossego",
        "nome_arquivo": nome_arquivo_padrao(4, "PERTURBACAO-AO-SOSSEGO-ALHEIO"),
        "geocodifica": False,
    },
    "DESLOCAMENTO FORÇADO": {
        "ordem": 5,
        "label": "DESLOCAMENTO FORÇADO",
        "key": "deslocamento_forcado",
        "nome_arquivo": nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO"),
        "geocodifica": False,
    },
    "ROUBO DE VEÍCULO (SPORTAL)": {
        "ordem": 6,
        "label": "ROUBO DE VEÍCULO (SPORTAL)",
        "key": "roubo_sportal",
        "nome_arquivo": nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG"),
        "geocodifica": False,
    },
    "ROUBO DE VEÍCULO (SIP)": {
        "ordem": 7,
        "label": "ROUBO DE VEÍCULO (SIP)",
        "key": "roubo_sip",
        "nome_arquivo": nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
        "geocodifica": True,
    },
    "ACIDENTE DE TRÂNSITO": {
        "ordem": 8,
        "label": "ACIDENTE DE TRÂNSITO",
        "key": "acidente_transito",
        "nome_arquivo": nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL-QGP"),
        "geocodifica": False,
    },
    "FURTO DE VEÍCULO (SPORTAL)": {
        "ordem": 9,
        "label": "FURTO DE VEÍCULO (SPORTAL)",
        "key": "furto_sportal",
        "nome_arquivo": nome_arquivo_padrao(9, "FURTO-DE-VEICULO-SPORTAL-QGP"),
        "geocodifica": False,
    },
    "FURTO DE VEÍCULO (SIP)": {
        "ordem": 10,
        "label": "FURTO DE VEÍCULO (SIP)",
        "key": "furto_sip",
        "nome_arquivo": nome_arquivo_padrao(10, "FURTO-DE-VEICULO-SIP-ENDERECO"),
        "geocodifica": True,
    },
}

INDICADORES_ORDEM = [
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
]


def _aplicar_estilo_todos_indicadores() -> None:
    st.markdown(
        """
        <style>
            .todos-shell {
                display: flex;
                flex-direction: column;
                gap: 1rem;
                margin-bottom: 1rem;
            }

            .todos-hero {
                background: linear-gradient(135deg, rgba(8, 54, 49, 0.92) 0%, rgba(9, 79, 70, 0.92) 100%);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 18px;
                padding: 1.4rem 1.4rem 1.2rem 1.4rem;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
            }

            .todos-kicker {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.14em;
                font-weight: 800;
                color: #f7b267;
                margin-bottom: 0.55rem;
            }

            .todos-title {
                font-size: 2rem;
                line-height: 1.1;
                font-weight: 900;
                color: #f8fafc;
                margin: 0 0 0.5rem 0;
            }

            .todos-description {
                color: rgba(255, 255, 255, 0.82);
                font-size: 0.98rem;
                line-height: 1.6;
                margin: 0;
                max-width: 920px;
            }

            .todos-section-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1.1rem 1.1rem 0.7rem 1.1rem;
                margin: 1rem 0;
            }

            .todos-section-title {
                font-size: 1.15rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.25rem;
            }

            .todos-section-desc {
                font-size: 0.93rem;
                color: rgba(255, 255, 255, 0.70);
                margin-bottom: 0.9rem;
                line-height: 1.5;
            }

            .todos-grid-status {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 1rem 0 0.2rem 0;
            }

            .todos-stat {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .todos-stat-label {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: rgba(255, 255, 255, 0.58);
                margin-bottom: 0.35rem;
                font-weight: 700;
            }

            .todos-stat-value {
                font-size: 1.45rem;
                font-weight: 900;
                color: #ffffff;
                line-height: 1;
            }

            .todos-badge-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 0.55rem;
                margin-bottom: 0.15rem;
            }

            .todos-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.5rem 0.72rem;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 700;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(255, 255, 255, 0.03);
                color: #e5f3ee;
            }

            .todos-badge.ok {
                background: rgba(34, 197, 94, 0.10);
                color: #b7f7c9;
                border-color: rgba(34, 197, 94, 0.22);
            }

            .todos-badge.warn {
                background: rgba(245, 158, 11, 0.10);
                color: #fde4b0;
                border-color: rgba(245, 158, 11, 0.22);
            }

            .todos-badge.err {
                background: rgba(239, 68, 68, 0.10);
                color: #fecaca;
                border-color: rgba(239, 68, 68, 0.22);
            }

            .todos-mini-list {
                margin: 0.6rem 0 0 0;
                padding-left: 1rem;
                color: rgba(255,255,255,0.78);
                font-size: 0.92rem;
            }

            .todos-divider-space {
                height: 0.2rem;
            }

            @media (max-width: 980px) {
                .todos-grid-status {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }

            @media (max-width: 640px) {
                .todos-grid-status {
                    grid-template-columns: 1fr;
                }

                .todos-title {
                    font-size: 1.6rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalizar_texto(texto: str) -> str:
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9]+", "-", texto)
    texto = re.sub(r"-+", "-", texto).strip("-")
    return texto


def _tokens_nome_arquivo(nome_arquivo: str) -> str:
    nome_base = str(nome_arquivo).rsplit(".", 1)[0]
    return _normalizar_texto(nome_base)


def _mapa_tokens_indicadores_nome() -> dict[str, list[str]]:
    return {
        "CVLI": ["CVLI", "1-CVLI"],
        "CVP (SPORTAL)": ["CVP-SPORTAL", "2-CVP-SPORTAL"],
        "CVP (SIP)": ["CVP-SIP", "CVP-SIP-ENDERECO", "3-CVP-SIP-ENDERECO"],
        "PERTURBAÇÃO AO SOSSEGO ALHEIO": [
            "PERTURBACAO-AO-SOSSEGO-ALHEIO",
            "PERTURBACAO-SOSSEGO-ALHEIO",
            "4-PERTURBACAO-AO-SOSSEGO-ALHEIO",
        ],
        "DESLOCAMENTO FORÇADO": ["DESLOCAMENTO-FORCADO", "5-DESLOCAMENTO-FORCADO"],
        "ROUBO DE VEÍCULO (SPORTAL)": [
            "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG",
            "ROUBO-DE-VEICULO-SPORTAL",
            "6-ROUBO-DE-VEICULO-SPORTAL-LAT-LONG",
        ],
        "ROUBO DE VEÍCULO (SIP)": [
            "ROUBO-DE-VEICULO-SIP-ENDERECO",
            "ROUBO-DE-VEICULO-SIP",
            "7-ROUBO-DE-VEICULO-SIP-ENDERECO",
        ],
        "ACIDENTE DE TRÂNSITO": [
            "ACIDENTE-DE-TRANSITO-SPORTAL-QGP",
            "ACIDENTE-DE-TRANSITO",
            "8-ACIDENTE-DE-TRANSITO-SPORTAL-QGP",
        ],
        "FURTO DE VEÍCULO (SPORTAL)": [
            "FURTO-DE-VEICULO-SPORTAL-QGP",
            "FURTO-DE-VEICULO-SPORTAL",
            "9-FURTO-DE-VEICULO-SPORTAL-QGP",
        ],
        "FURTO DE VEÍCULO (SIP)": [
            "FURTO-DE-VEICULO-SIP-ENDERECO",
            "FURTO-DE-VEICULO-SIP",
            "10-FURTO-DE-VEICULO-SIP-ENDERECO",
        ],
    }


def _identificar_por_nome(nome_arquivo: str) -> str | None:
    nome_norm = _tokens_nome_arquivo(nome_arquivo)
    correspondencias = []

    for indicador, tokens in _mapa_tokens_indicadores_nome().items():
        for token in tokens:
            token_norm = _normalizar_texto(token)
            if token_norm and token_norm in nome_norm:
                correspondencias.append((len(token_norm), indicador))

    if not correspondencias:
        return None

    correspondencias.sort(reverse=True)
    return correspondencias[0][1]


def _identificar_por_conteudo(arquivo) -> str | None:
    try:
        arquivo.seek(0)
        df = pd.read_excel(arquivo, nrows=200)
        arquivo.seek(0)
    except Exception:
        return None

    df_norm = normalizar_colunas(df)
    colunas = set(df_norm.columns)

    def tem_algum(*cols):
        return any(c in colunas for c in cols)

    if df_norm.empty:
        return None

    natureza_series = (
        df_norm["natureza"].astype(str).fillna("").unique()
        if "natureza" in df_norm.columns
        else []
    )
    natureza_tokens = {_normalizar_texto(v) for v in natureza_series}

    if tem_algum("natureza", "tipo_crime", "tipo_ocorrencia") and tem_algum("vitima", "nome_vitima"):
        if tem_algum("cvli", "homicidio", "latrocini"):
            return "CVLI"

    if tem_algum("logradouro", "endereco") and tem_algum("bairro", "municipio"):
        if tem_algum("tipo_crime", "natureza") and tem_algum("cvp", "crime_contra_patrimonio"):
            return "CVP (SIP)"

    if tem_algum("latitude", "lat") and tem_algum("longitude", "long", "lon"):
        if tem_algum("cvp", "crime_contra_patrimonio"):
            return "CVP (SPORTAL)"

    if "natureza" in df_norm.columns:
        if any("PERTURBACAO" in v or "SOSSEGO" in v for v in natureza_tokens):
            return "PERTURBAÇÃO AO SOSSEGO ALHEIO"

        if any("DESLOCAMENTO-FORCADO" in v or "DESLOCAMENTO" in v for v in natureza_tokens):
            return "DESLOCAMENTO FORÇADO"

    if tem_algum("placa", "chassi", "modelo", "veiculo", "categoria_veiculo"):
        if tem_algum("logradouro", "endereco", "bairro", "municipio"):
            if "natureza" in df_norm.columns:
                if any("ROUBO" in v for v in natureza_tokens):
                    return "ROUBO DE VEÍCULO (SIP)"
                if any("FURTO" in v for v in natureza_tokens):
                    return "FURTO DE VEÍCULO (SIP)"
        elif tem_algum("latitude", "lat") and tem_algum("longitude", "long", "lon"):
            if "natureza" in df_norm.columns:
                if any("ROUBO" in v for v in natureza_tokens):
                    return "ROUBO DE VEÍCULO (SPORTAL)"
                if any("FURTO" in v for v in natureza_tokens):
                    return "FURTO DE VEÍCULO (SPORTAL)"

    if tem_algum("natureza", "tipo_acidente", "tipo_crime"):
        if "natureza" in df_norm.columns:
            valores_nat = {_normalizar_texto(str(v)) for v in df_norm["natureza"].astype(str).unique()}
        elif "tipo_acidente" in df_norm.columns:
            valores_nat = {_normalizar_texto(str(v)) for v in df_norm["tipo_acidente"].astype(str).unique()}
        else:
            valores_nat = {_normalizar_texto(str(v)) for v in df_norm["tipo_crime"].astype(str).unique()}

        if any("ACIDENTE" in v or "COLISAO" in v or "TRANSITO" in v for v in valores_nat):
            return "ACIDENTE DE TRÂNSITO"

    return None


def _identificar_indicador(arquivo) -> tuple[str | None, str]:
    nome_arq = getattr(arquivo, "name", "arquivo_sem_nome")
    ind_nome = _identificar_por_nome(nome_arq)
    if ind_nome:
        return ind_nome, "Identificado automaticamente pelo nome do arquivo."

    ind_cont = _identificar_por_conteudo(arquivo)
    if ind_cont:
        return ind_cont, "Identificado automaticamente pelo conteúdo da planilha."

    return None, "Não foi possível identificar o indicador pelo nome ou conteúdo."


def _registrar_arquivos_base(arquivos_upload) -> tuple[list[str], list[str]]:
    reconhecidos = []
    nao_reconhecidos = []

    st.session_state.todos_arq01_bytes = {}
    st.session_state.todos_arq01_nomes = {}
    st.session_state.todos_erros_upload = {}
    st.session_state.todos_duplicados_upload = {}

    for arq in arquivos_upload:
        indicador, origem_msg = _identificar_indicador(arq)

        if indicador is None:
            nao_reconhecidos.append(arq.name)
            continue

        if indicador in st.session_state.todos_arq01_bytes:
            st.session_state.todos_duplicados_upload.setdefault(indicador, []).append(arq.name)
            continue

        arq.seek(0)
        st.session_state.todos_arq01_bytes[indicador] = arq.read()
        st.session_state.todos_arq01_nomes[indicador] = f"{arq.name} ({origem_msg})"
        reconhecidos.append(indicador)

    return reconhecidos, nao_reconhecidos


@contextmanager
def _silenciar_streamlit_temporariamente():
    funcoes_silenciadas = [
        "write",
        "dataframe",
        "table",
        "caption",
        "info",
        "success",
        "warning",
        "error",
        "markdown",
        "text",
        "subheader",
        "header",
        "divider",
        "code",
        "toast",
        "balloons",
        "snow",
    ]
    originais = {}

    def _noop(*args, **kwargs):
        return None

    class _DummyContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, *args, **kwargs):
            return None

        def dataframe(self, *args, **kwargs):
            return None

        def table(self, *args, **kwargs):
            return None

        def caption(self, *args, **kwargs):
            return None

        def markdown(self, *args, **kwargs):
            return None

        def code(self, *args, **kwargs):
            return None

        def info(self, *args, **kwargs):
            return None

        def success(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    for nome in funcoes_silenciadas:
        if hasattr(st, nome):
            originais[nome] = getattr(st, nome)
            setattr(st, nome, _noop)

    if hasattr(st, "expander"):
        originais["expander"] = st.expander
        st.expander = lambda *args, **kwargs: _DummyContext()

    if hasattr(st, "empty"):
        originais["empty"] = st.empty
        st.empty = lambda *args, **kwargs: _DummyContext()

    try:
        yield
    finally:
        for nome, func in originais.items():
            setattr(st, nome, func)


def _normalizar_saida_processamento(resultado, nome_indicador: str) -> tuple[pd.DataFrame, dict]:
    if isinstance(resultado, tuple) and len(resultado) == 2:
        df_final, resumo = resultado
    elif isinstance(resultado, dict):
        if not resultado.get("sucesso", True):
            raise ValueError(resultado.get("erro", f"Falha ao processar {nome_indicador}."))
        df_final = resultado.get("df_final")
        if df_final is None:
            raise ValueError(f"O processador de {nome_indicador} não retornou 'df_final'.")
        resumo = {
            "adicionados": resultado.get("adicionados", 0),
            "total_final": resultado.get("total_final", len(df_final)),
            "geocodificados": resultado.get("geocodificados", 0),
            "situacao": resultado.get("situacao", "Processado com sucesso."),
        }
    else:
        raise ValueError(
            f"Retorno inválido do processador de {nome_indicador}: {type(resultado).__name__}"
        )

    if not isinstance(df_final, pd.DataFrame):
        raise ValueError(f"O resultado de {nome_indicador} não é um DataFrame válido.")

    if not isinstance(resumo, dict):
        resumo = {}

    resumo.setdefault("adicionados", 0)
    resumo.setdefault("total_final", len(df_final))
    resumo.setdefault("geocodificados", 0)
    resumo.setdefault("situacao", "Processado com sucesso.")
    return df_final, resumo


def _processar_cvp_sportal(buf_01: BytesIO, buf_02: BytesIO):
    buf_01.seek(0)
    buf_02.seek(0)

    df_base = pd.read_excel(buf_01)
    df_novo = pd.read_excel(buf_02)

    df_base = normalizar_colunas(df_base)
    df_novo = normalizar_colunas(df_novo)

    col_data_base = encontrar_coluna_data(df_base)
    col_data_novo = encontrar_coluna_data(df_novo)
    col_hora_base = encontrar_coluna_hora(df_base)
    col_hora_novo = encontrar_coluna_hora(df_novo)

    if col_data_base and col_data_novo and col_data_base != col_data_novo:
        df_novo = df_novo.rename(columns={col_data_novo: col_data_base})

    if col_hora_base and col_hora_novo and col_hora_base != col_hora_novo:
        df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})

    col_data = col_data_base or col_data_novo
    col_hora = col_hora_base or col_hora_novo

    col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"], obrigatoria=False)
    col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"], obrigatoria=False)

    df_novo = renomear_colunas_equivalentes(df_base, df_novo)

    col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["lat", "latitude"], obrigatoria=False)
    col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["long", "longitude", "lon"], obrigatoria=False)

    total_lido = len(df_novo)
    removidos_invalidos = 0

    if col_lat_novo and col_lon_novo:
        df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
        removidos_invalidos = total_lido - len(df_novo)

    df_base = criar_coluna_datahora(df_base, col_data, col_hora, "datahora")
    df_novo = criar_coluna_datahora(df_novo, col_data, col_hora, "datahora")

    ultima_dh = obter_ultima_datahora(df_base, "datahora")

    total_antes = len(df_novo)
    df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "datahora", ultima_dh)
    removidos_datahora = total_antes - len(df_novo_filtrado)

    base_sem_aux = df_base.drop(columns=["datahora"], errors="ignore").copy()

    if ultima_dh is None:
        df_novo_util = df_novo.drop(columns=["datahora"], errors="ignore").copy()
        situacao = "Base anterior sem Data/Hora válida - Arquivo 02 incluído integralmente."
    elif df_novo_filtrado.empty:
        df_novo_util = df_novo_filtrado.drop(columns=["datahora"], errors="ignore").copy()
        situacao = "Nenhum registro novo encontrado após a última Data/Hora da base."
    else:
        df_novo_util = df_novo_filtrado.drop(columns=["datahora"], errors="ignore").copy()
        situacao = "Somente registros posteriores à última Data/Hora foram adicionados."

    adicionados = len(df_novo_util)

    if not df_novo_util.empty and col_lat_novo and col_lon_novo and col_lat_base and col_lon_base:
        df_novo_util = converter_coordenadas_para_wgs84_auto(
            df_novo_util,
            col_y_or_lat=col_lat_novo,
            col_x_or_lon=col_lon_novo,
            col_lat_destino=col_lat_base,
            col_lon_destino=col_lon_base,
        )

    if not df_novo_util.empty:
        df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
    else:
        df_final = base_sem_aux.copy()

    df_final = criar_coluna_datahora(df_final, col_data, col_hora, "datahora")
    if "datahora" in df_final.columns:
        df_final = df_final.sort_values("datahora", ascending=True, na_position="last").reset_index(drop=True)
    df_final = df_final.drop(columns=["datahora"], errors="ignore")

    resumo = {
        "adicionados": adicionados,
        "total_final": len(df_final),
        "geocodificados": 0,
        "removidos_invalidos": removidos_invalidos,
        "removidos_datahora": removidos_datahora,
        "ultima_datahora_base": ultima_dh.strftime("%d/%m/%Y %H:%M:%S") if ultima_dh else "N/A",
        "situacao": situacao,
    }

    return df_final, resumo


def _criar_config_padrao_sip() -> SimpleNamespace:
    return SimpleNamespace(
        origem="todos_indicadores",
        modo_silencioso=True,
        usar_cache=True,
        valor_filtro_natureza="",
        caminho_base_enxuta=None,
    )


def _chamar_processador(nome_indicador: str, buf_01: BytesIO, buf_02: BytesIO):
    buf_01.seek(0)
    buf_02.seek(0)

    with _silenciar_streamlit_temporariamente():
        if nome_indicador == "CVLI":
            proc = ProcessadorCVLI()
            res = proc.processar(buf_01, buf_02)
            return _normalizar_saida_processamento(res, nome_indicador)

        if nome_indicador == "CVP (SPORTAL)":
            return _normalizar_saida_processamento(
                _processar_cvp_sportal(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "CVP (SIP)":
            return _normalizar_saida_processamento(
                processar_cvp_sip(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "PERTURBAÇÃO AO SOSSEGO ALHEIO":
            return _normalizar_saida_processamento(
                processar_perturbacao_sossego(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "DESLOCAMENTO FORÇADO":
            return _normalizar_saida_processamento(
                processar_deslocamento_forcado(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "ROUBO DE VEÍCULO (SPORTAL)":
            return _normalizar_saida_processamento(
                processar_roubo_veiculo_sportal(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "ROUBO DE VEÍCULO (SIP)":
            config_padrao = _criar_config_padrao_sip()
            return _normalizar_saida_processamento(
                processar_roubo_veiculo_sip(buf_01, buf_02, config=config_padrao),
                nome_indicador,
            )

        if nome_indicador == "ACIDENTE DE TRÂNSITO":
            return _normalizar_saida_processamento(
                processar_acidente_transito(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "FURTO DE VEÍCULO (SPORTAL)":
            return _normalizar_saida_processamento(
                processar_furto_veiculo_sportal(buf_01, buf_02),
                nome_indicador,
            )

        if nome_indicador == "FURTO DE VEÍCULO (SIP)":
            config_padrao = _criar_config_padrao_sip()
            return _normalizar_saida_processamento(
                processar_furto_veiculo_sip(buf_01, buf_02, config=config_padrao),
                nome_indicador,
            )

        raise ValueError(f"Indicador desconhecido: {nome_indicador}")


def _df_para_excel(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    buf.seek(0)
    return buf.getvalue()


def _init_state():
    defaults = {
        "todos_arq01_bytes": {},
        "todos_arq01_nomes": {},
        "todos_arq02_bytes": None,
        "todos_arq02_nome": None,
        "todos_resultados_excel": {},
        "todos_resumos": {},
        "todos_erros": {},
        "todos_processando": False,
        "todos_parar": False,
        "todos_erros_upload": {},
        "todos_duplicados_upload": {},
        "todos_df_resultados": None,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def _render_hero():
    st.markdown(
        """
        <div class="todos-shell">
            <div class="todos-hero">
                <div class="todos-kicker">Processamento consolidado</div>
                <div class="todos-title">Todos os Indicadores</div>
                <p class="todos-description">
                    Centralize o processamento dos indicadores em uma única operação. O módulo identifica
                    automaticamente os arquivos-base, utiliza o Arquivo 02 compartilhado e executa, de forma
                    sequencial, as regras específicas de cada indicador — inclusive geocodificação quando aplicável.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_status_cards(indicadores_prontos: list[str], indicadores_faltantes: list[str], tem_arq02: bool) -> None:
    total_indicadores = len(INDICADORES_ORDEM)
    total_prontos = len(indicadores_prontos)
    total_geocodificaveis = sum(
        1 for nome in indicadores_prontos if INDICADORES_CONFIG[nome]["geocodifica"]
    )
    total_faltantes = len(indicadores_faltantes)
    arq02_status = "Sim" if tem_arq02 else "Não"

    st.markdown(
        f"""
        <div class="todos-grid-status">
            <div class="todos-stat">
                <div class="todos-stat-label">Indicadores carregados</div>
                <div class="todos-stat-value">{total_prontos}/{total_indicadores}</div>
            </div>
            <div class="todos-stat">
                <div class="todos-stat-label">Arquivo 02</div>
                <div class="todos-stat-value">{arq02_status}</div>
            </div>
            <div class="todos-stat">
                <div class="todos-stat-label">Com geocodificação</div>
                <div class="todos-stat-value">{total_geocodificaveis}</div>
            </div>
            <div class="todos-stat">
                <div class="todos-stat-label">Pendentes</div>
                <div class="todos-stat-value">{total_faltantes}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_lista_indicadores(titulo: str, indicadores: list[str], tipo: str) -> None:
    if not indicadores:
        return

    badges = []
    for nome in indicadores:
        cfg = INDICADORES_CONFIG[nome]
        badges.append(
            f'<span class="todos-badge {tipo}">{cfg["ordem"]}. {cfg["label"]}</span>'
        )

    st.markdown(
        f"""
        <div class="todos-section-card">
            <div class="todos-section-title">{titulo}</div>
            <div class="todos-badge-wrap">
                {''.join(badges)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def interface_todos_indicadores():
    _init_state()
    _aplicar_estilo_todos_indicadores()
    _render_hero()

    st.markdown(
        """
        <div class="todos-section-card">
            <div class="todos-section-title">Arquivo 02 · Complemento único</div>
            <div class="todos-section-desc">
                Envie o arquivo consolidado em Excel com múltiplas abas. Cada processador seleciona
                automaticamente a aba correspondente ao indicador.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    arquivo_02_upload = st.file_uploader(
        "Arquivo 02 (Excel com múltiplas abas)",
        type=["xlsx", "xls"],
        key="todos_upload_02",
    )

    if arquivo_02_upload is not None:
        arquivo_02_upload.seek(0)
        st.session_state.todos_arq02_bytes = arquivo_02_upload.read()
        st.session_state.todos_arq02_nome = arquivo_02_upload.name
    else:
        st.session_state.todos_arq02_bytes = None
        st.session_state.todos_arq02_nome = None

    if st.session_state.todos_arq02_nome:
        st.success(f"Arquivo 02 carregado com sucesso: {st.session_state.todos_arq02_nome}")

    st.markdown(
        """
        <div class="todos-section-card">
            <div class="todos-section-title">Arquivos 01 · Base histórica</div>
            <div class="todos-section-desc">
                Selecione em lote os arquivos históricos. O sistema tenta identificar automaticamente
                cada indicador pelo nome do arquivo e, quando necessário, pelo conteúdo da planilha.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    arquivos_base_upload = st.file_uploader(
        "Arquivos 01 (seleção múltipla)",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="todos_upload_01_lote",
    )

    if arquivos_base_upload:
        reconhecidos, nao_reconhecidos = _registrar_arquivos_base(arquivos_base_upload)

        if reconhecidos:
            reconhecidos_ordenados = sorted(
                reconhecidos,
                key=lambda nome: INDICADORES_CONFIG[nome]["ordem"],
            )
            st.success(
                f"{len(reconhecidos_ordenados)} arquivo(s) de base reconhecido(s): "
                + ", ".join(
                    f"{INDICADORES_CONFIG[nome]['ordem']} - {INDICADORES_CONFIG[nome]['label']}"
                    for nome in reconhecidos_ordenados
                )
            )

        if nao_reconhecidos:
            st.warning(
                "Arquivo(s) não reconhecido(s) pelo nome ou conteúdo: "
                + ", ".join(nao_reconhecidos)
            )

        if st.session_state.todos_duplicados_upload:
            for nome_ind, arquivos_dup in st.session_state.todos_duplicados_upload.items():
                cfg = INDICADORES_CONFIG[nome_ind]
                st.warning(
                    f"Duplicidade para {cfg['ordem']} - {cfg['label']}: "
                    + ", ".join(arquivos_dup)
                    + ". Apenas o primeiro arquivo reconhecido foi considerado."
                )
    else:
        st.session_state.todos_arq01_bytes = {}
        st.session_state.todos_arq01_nomes = {}
        st.session_state.todos_erros_upload = {}
        st.session_state.todos_duplicados_upload = {}

    indicadores_prontos = [
        nome_ind for nome_ind in INDICADORES_ORDEM
        if nome_ind in st.session_state.todos_arq01_bytes
    ]
    indicadores_faltantes = [
        nome_ind for nome_ind in INDICADORES_ORDEM
        if nome_ind not in st.session_state.todos_arq01_bytes
    ]
    tem_arq02 = st.session_state.todos_arq02_bytes is not None

    _render_status_cards(indicadores_prontos, indicadores_faltantes, tem_arq02)

    if st.session_state.todos_arq01_nomes:
        with st.expander("Ver arquivos base identificados", expanded=False):
            for nome_ind in INDICADORES_ORDEM:
                if nome_ind in st.session_state.todos_arq01_nomes:
                    cfg = INDICADORES_CONFIG[nome_ind]
                    st.caption(
                        f"{cfg['ordem']} - {cfg['label']}: "
                        f"{st.session_state.todos_arq01_nomes[nome_ind]}"
                    )

    _render_lista_indicadores("Indicadores prontos para processamento", indicadores_prontos, "ok")
    _render_lista_indicadores("Indicadores ainda pendentes", indicadores_faltantes, "warn")

    if not tem_arq02:
        st.warning("O Arquivo 02 ainda não foi carregado.")

    pode_processar = len(indicadores_prontos) > 0 and tem_arq02

    st.markdown(
        """
        <div class="todos-section-card">
            <div class="todos-section-title">Execução do processamento</div>
            <div class="todos-section-desc">
                Inicie o processamento consolidado após validar os arquivos carregados. O fluxo executa
                os indicadores em sequência e preserva o resultado individual para download.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        iniciar = st.button(
            "Processar Todos os Indicadores",
            type="primary",
            use_container_width=True,
            disabled=not pode_processar or st.session_state.todos_processando,
        )

    with col_btn2:
        if st.button(
            "Parar Processo",
            type="secondary",
            use_container_width=True,
            disabled=not st.session_state.todos_processando,
        ):
            st.session_state.todos_parar = True
            st.warning("Sinalização de parada enviada ao processamento.")

    if iniciar:
        st.session_state.todos_resultados_excel = {}
        st.session_state.todos_resumos = {}
        st.session_state.todos_erros = {}
        st.session_state.todos_df_resultados = None
        st.session_state.todos_processando = True
        st.session_state.todos_parar = False

        total = len(indicadores_prontos)
        progresso = st.progress(0)
        status = st.empty()
        resultados_linha = []
        interrompido = False

        for idx, nome_ind in enumerate(indicadores_prontos):
            if st.session_state.todos_parar:
                interrompido = True
                status.warning("Processo interrompido pelo usuário.")
                break

            cfg = INDICADORES_CONFIG[nome_ind]
            status.info(
                f"[{idx + 1}/{total}] Processando {cfg['label']}"
                + (" · executando geocodificação" if cfg["geocodifica"] else "")
            )

            try:
                buf_01 = BytesIO(st.session_state.todos_arq01_bytes[nome_ind])
                buf_02 = BytesIO(st.session_state.todos_arq02_bytes)

                df_final, resumo = _chamar_processador(nome_ind, buf_01, buf_02)
                excel_bytes = _df_para_excel(df_final, sheet_name=nome_ind[:31])

                st.session_state.todos_resultados_excel[nome_ind] = (
                    excel_bytes,
                    cfg["nome_arquivo"],
                )
                st.session_state.todos_resumos[nome_ind] = resumo

                resultados_linha.append({
                    "Ordem": cfg["ordem"],
                    "Indicador": cfg["label"],
                    "Status": "Sucesso",
                    "Adicionados": resumo.get("adicionados", 0),
                    "Total Final": resumo.get("total_final", 0),
                    "Geocodificados": resumo.get("geocodificados", 0),
                    "Situação": resumo.get("situacao", ""),
                })
            except Exception as exc:
                st.session_state.todos_erros[nome_ind] = str(exc)
                resultados_linha.append({
                    "Ordem": cfg["ordem"],
                    "Indicador": cfg["label"],
                    "Status": "Erro",
                    "Adicionados": 0,
                    "Total Final": 0,
                    "Geocodificados": 0,
                    "Situação": str(exc),
                })

            progresso.progress((idx + 1) / total)

        st.session_state.todos_processando = False

        if interrompido:
            status.warning("Processamento interrompido antes da conclusão.")
        else:
            status.success("Processamento concluído com sucesso.")

        if resultados_linha:
            st.session_state.todos_df_resultados = (
                pd.DataFrame(resultados_linha)
                .sort_values("Ordem")
                .reset_index(drop=True)
            )

    if st.session_state.todos_df_resultados is not None:
        st.markdown(
            """
            <div class="todos-section-card">
                <div class="todos-section-title">Painel de resultados</div>
                <div class="todos-section-desc">
                    Acompanhe o desempenho por indicador, valide quantidades adicionadas e confira
                    a situação final de cada processamento.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        df_resultados = st.session_state.todos_df_resultados
        total_ok = int((df_resultados["Status"] == "Sucesso").sum())
        total_erro = int((df_resultados["Status"] == "Erro").sum())
        total_adicionados = int(df_resultados["Adicionados"].fillna(0).sum())
        total_geo = int(df_resultados["Geocodificados"].fillna(0).sum())

        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        col_r1.metric("Processados com sucesso", total_ok)
        col_r2.metric("Com erro", total_erro)
        col_r3.metric("Registros adicionados", f"{total_adicionados:,}".replace(",", "."))
        col_r4.metric("Geocodificados", f"{total_geo:,}".replace(",", "."))

        st.dataframe(df_resultados, use_container_width=True, hide_index=True)

    if st.session_state.todos_resultados_excel:
        st.markdown(
            """
            <div class="todos-section-card">
                <div class="todos-section-title">Downloads individuais</div>
                <div class="todos-section-desc">
                    Baixe os arquivos gerados por indicador ou exporte tudo em um único pacote ZIP.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for nome_ind in INDICADORES_ORDEM:
            if nome_ind not in st.session_state.todos_resultados_excel:
                continue

            excel_bytes, nome_arq = st.session_state.todos_resultados_excel[nome_ind]
            resumo = st.session_state.todos_resumos.get(nome_ind, {})
            cfg = INDICADORES_CONFIG[nome_ind]

            with st.expander(
                f"{cfg['ordem']} - {cfg['label']} · "
                f"Adicionados: {resumo.get('adicionados', 0)} · "
                f"Total final: {resumo.get('total_final', 0)}",
                expanded=False,
            ):
                st.caption(resumo.get("situacao", ""))
                if resumo.get("geocodificados", 0):
                    st.caption(f"Geocodificados: {resumo.get('geocodificados', 0)}")

                st.download_button(
                    label=f"Baixar {nome_arq}",
                    data=excel_bytes,
                    file_name=nome_arq,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"todos_dl_{cfg['key']}",
                    use_container_width=True,
                )

        zip_buf = BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome_ind in INDICADORES_ORDEM:
                if nome_ind not in st.session_state.todos_resultados_excel:
                    continue
                excel_bytes, nome_arq = st.session_state.todos_resultados_excel[nome_ind]
                zf.writestr(nome_arq, excel_bytes)

        zip_buf.seek(0)

        st.download_button(
            label=(
                f"Baixar ZIP com todos os indicadores "
                f"({len(st.session_state.todos_resultados_excel)} arquivos)"
            ),
            data=zip_buf.getvalue(),
            file_name=f"QGP-TODOS-INDICADORES-{datetime.now().year}.zip",
            mime="application/zip",
            use_container_width=True,
            key="todos_dl_zip",
        )

    if st.session_state.todos_erros:
        st.markdown(
            """
            <div class="todos-section-card">
                <div class="todos-section-title">Erros identificados</div>
                <div class="todos-section-desc">
                    Os indicadores abaixo apresentaram falha durante o processamento e devem ser revisados.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for nome_ind in INDICADORES_ORDEM:
            if nome_ind not in st.session_state.todos_erros:
                continue
            erro = st.session_state.todos_erros[nome_ind]
            cfg = INDICADORES_CONFIG[nome_ind]
            st.error(f"{cfg['ordem']} - {cfg['label']}: {erro}")


ProcessadorTodosIndicadores = interface_todos_indicadores
