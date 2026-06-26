"""
Módulo TODOS OS INDICADORES
Processamento consolidado de múltiplos indicadores
Chama os módulos individuais com suas funções reais de processamento.
"""
from __future__ import annotations

import io
import zipfile
from io import BytesIO

import pandas as pd
import streamlit as st
from datetime import datetime

# ── Importações dos módulos individuais ──────────────────────────────────────
from modulos.cvli import ProcessadorCVLI
from modulos.cvp_sportal import (
    interface_cvp_sportal as _interface_cvp_sportal_original,
)
from modulos.cvp_sip import processar_cvp_sip
from modulos.perturbacao_sossego import processar_perturbacao_sossego
from modulos.deslocamento_forcado import processar_deslocamento_forcado
from modulos.roubo_veiculo_sportal import processar_roubo_veiculo_sportal
from modulos.roubo_veiculo_sip import processar_roubo_veiculo_sip
from modulos.acidente_transito import processar_acidente_transito
from modulos.furto_veiculo_sportal import processar_furto_veiculo_sportal
from modulos.furto_veiculo_sip import processar_furto_veiculo_sip
from modulos.utils import nome_arquivo_padrao, gerar_arquivo_excel


# ── Configuração dos indicadores ─────────────────────────────────────────────

INDICADORES_CONFIG = {
    "CVLI": {
        "label": "CVLI - Crimes Violentos Letais Intencionais",
        "key": "cvli",
        "nome_arquivo": f"1-CVLI-{datetime.now().year}-QGP.xlsx",
        "geocodifica": False,
    },
    "CVP (SPORTAL)": {
        "label": "CVP (SPORTAL) - Crimes Violentos contra o Patrimônio",
        "key": "cvp_sportal",
        "nome_arquivo": nome_arquivo_padrao(2, "CVP-SPORTAL"),
        "geocodifica": False,
    },
    "CVP (SIP)": {
        "label": "CVP (SIP) - Crimes Violentos contra o Patrimônio",
        "key": "cvp_sip",
        "nome_arquivo": nome_arquivo_padrao(3, "CVP-SIP-ENDERECO"),
        "geocodifica": True,
    },
    "PERTURBACAO DO SOSSEGO": {
        "label": "Perturbação ao Sossego Alheio",
        "key": "perturbacao_sossego",
        "nome_arquivo": nome_arquivo_padrao(3, "PERTURBACAO-SOSSEGO-ALHEIO"),
        "geocodifica": False,
    },
    "DESLOCAMENTO FORCADO": {
        "label": "Deslocamento Forçado",
        "key": "deslocamento_forcado",
        "nome_arquivo": nome_arquivo_padrao(5, "DESLOCAMENTO-FORCADO"),
        "geocodifica": False,
    },
    "ROUBO DE VEICULO (SPORTAL)": {
        "label": "Roubo de Veículo (SPORTAL)",
        "key": "roubo_sportal",
        "nome_arquivo": nome_arquivo_padrao(6, "ROUBO-DE-VEICULO-SPORTAL-LAT-LONG"),
        "geocodifica": False,
    },
    "ROUBO DE VEICULO (SIP)": {
        "label": "Roubo de Veículo (SIP)",
        "key": "roubo_sip",
        "nome_arquivo": nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
        "geocodifica": True,
    },
    "ACIDENTE DE TRANSITO": {
        "label": "Acidente de Trânsito",
        "key": "acidente_transito",
        "nome_arquivo": nome_arquivo_padrao(8, "ACIDENTE-DE-TRANSITO-SPORTAL-QGP"),
        "geocodifica": False,
    },
    "FURTO DE VEICULO (SPORTAL)": {
        "label": "Furto de Veículo (SPORTAL)",
        "key": "furto_sportal",
        "nome_arquivo": nome_arquivo_padrao(9, "FURTO-DE-VEICULO-SPORTAL-QGP"),
        "geocodifica": False,
    },
    "FURTO DE VEICULO (SIP)": {
        "label": "Furto de Veículo (SIP)",
        "key": "furto_sip",
        "nome_arquivo": nome_arquivo_padrao(7, "FURTO-DE-VEICULO-SIP-ENDERECO"),
        "geocodifica": True,
    },
}


# ── Funções auxiliares ────────────────────────────────────────────────────────

def _gerar_excel_em_memoria(df: pd.DataFrame, sheet_name: str = "Dados") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer.getvalue()


def _chamar_processador(nome_indicador: str, buf_01: BytesIO, buf_02: BytesIO):
    """
    Chama a função de processamento correta para cada indicador.
    Retorna (df_final, resumo_dict) ou levanta exceção.
    """
    buf_01.seek(0)
    buf_02.seek(0)

    if nome_indicador == "CVLI":
        processador = ProcessadorCVLI()
        resultado = processador.processar(buf_01, buf_02)
        if not resultado["sucesso"]:
            raise ValueError(resultado["erro"])
        df = resultado["df_final"]
        resumo = {
            "adicionados": resultado.get("adicionados", 0),
            "total_final": resultado.get("total_final", len(df)),
            "geocodificados": 0,
            "situacao": "Atualizado" if resultado.get("houve_substituicao") else "Complementado",
        }
        return df, resumo

    elif nome_indicador == "CVP (SPORTAL)":
        # CVP SPORTAL: lógica embutida na interface — extraímos via utils diretamente
        from modulos.utils import (
            normalizar_colunas,
            encontrar_coluna_data,
            encontrar_coluna_hora,
            encontrar_coluna_por_nomes,
            renomear_colunas_equivalentes,
            alinhar_colunas_com_base,
            criar_coluna_datahora,
            excluir_coordenadas_invalidas,
            converter_coordenadas_para_wgs84_auto,
            obter_ultima_datahora,
            filtrar_apenas_registros_posteriores,
        )
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

        col_data = col_data_base
        col_hora = col_hora_base

        col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude", "lat"], obrigatoria=False)
        col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude", "long", "lon"], obrigatoria=False)

        if col_lat_novo and col_lon_novo:
            df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
            df_novo = converter_coordenadas_para_wgs84_auto(df_novo, col_lat_novo, col_lon_novo)

        df_novo = renomear_colunas_equivalentes(df_base, df_novo)

        df_base = criar_coluna_datahora(df_base, col_data, col_hora, "__datahora__")
        df_novo = criar_coluna_datahora(df_novo, col_data, col_hora, "__datahora__")

        ultima_dh = obter_ultima_datahora(df_base, "__datahora__")
        df_novo_filtrado = filtrar_apenas_registros_posteriores(df_novo, "__datahora__", ultima_dh)

        base_sem_aux = df_base.drop(columns=["__datahora__"], errors="ignore").copy()
        df_novo_util = df_novo_filtrado.drop(columns=["__datahora__"], errors="ignore").copy()
        df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)

        df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
        df_final = criar_coluna_datahora(df_final, col_data, col_hora, "__datahora__")
        df_final = df_final.sort_values("__datahora__", ascending=True, na_position="last").reset_index(drop=True)
        df_final = df_final.drop(columns=["__datahora__"], errors="ignore")

        resumo = {
            "adicionados": len(df_novo_util),
            "total_final": len(df_final),
            "geocodificados": 0,
            "situacao": "Base atualizada com registros posteriores.",
        }
        return df_final, resumo

    elif nome_indicador == "CVP (SIP)":
        return processar_cvp_sip(buf_01, buf_02)

    elif nome_indicador == "PERTURBACAO DO SOSSEGO":
        return processar_perturbacao_sossego(buf_01, buf_02)

    elif nome_indicador == "DESLOCAMENTO FORCADO":
        return processar_deslocamento_forcado(buf_01, buf_02)

    elif nome_indicador == "ROUBO DE VEICULO (SPORTAL)":
        return processar_roubo_veiculo_sportal(buf_01, buf_02)

    elif nome_indicador == "ROUBO DE VEICULO (SIP)":
        return processar_roubo_veiculo_sip(buf_01, buf_02)

    elif nome_indicador == "ACIDENTE DE TRANSITO":
        return processar_acidente_transito(buf_01, buf_02)

    elif nome_indicador == "FURTO DE VEICULO (SPORTAL)":
        return processar_furto_veiculo_sportal(buf_01, buf_02)

    elif nome_indicador == "FURTO DE VEICULO (SIP)":
        return processar_furto_veiculo_sip(buf_01, buf_02)

    else:
        raise ValueError(f"Indicador desconhecido: {nome_indicador}")


# ── Interface principal ───────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "todos_ind_arquivos_01": {},   # {chave_indicador: bytes}
        "todos_ind_arquivos_01_nomes": {},
        "todos_ind_arquivo_02_bytes": None,
        "todos_ind_arquivo_02_nome": None,
        "todos_ind_resultados": {},    # {nome_indicador: bytes_excel}
        "todos_ind_resumos": {},       # {nome_indicador: dict_resumo}
        "todos_ind_erros": {},         # {nome_indicador: str_erro}
        "todos_ind_processando": False,
        "todos_ind_parar": False,
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor


def interface_todos_indicadores():
    """Interface principal do módulo TODOS OS INDICADORES"""
    _init_state()

    st.title("📋 Processamento Consolidado")
    st.markdown("### 🔍 TODOS OS INDICADORES")
    st.info(
        "Este módulo processa múltiplos indicadores sequencialmente, "
        "chamando cada módulo individual com sua lógica completa (incluindo geocodificação onde aplicável)."
    )
    st.divider()

    # ── Upload Arquivo 02 (único para todos) ──────────────────────────────────
    st.subheader("📁 Arquivo 02 — Complemento Único (compartilhado por todos)")
    st.caption(
        "O Arquivo 02 contém as abas de cada indicador. "
        "Cada módulo seleciona automaticamente a aba correspondente."
    )
    arquivo_02_upload = st.file_uploader(
        "📂 Arquivo 02 (Excel com múltiplas abas)",
        type=["xlsx", "xls"],
        key="todos_ind_upload_02",
    )
    if arquivo_02_upload is not None:
        arquivo_02_upload.seek(0)
        st.session_state.todos_ind_arquivo_02_bytes = arquivo_02_upload.read()
        st.session_state.todos_ind_arquivo_02_nome = arquivo_02_upload.name

    if st.session_state.todos_ind_arquivo_02_nome:
        st.success(f"✅ Arquivo 02 carregado: **{st.session_state.todos_ind_arquivo_02_nome}**")

    st.divider()

    # ── Upload Arquivos 01 por indicador ──────────────────────────────────────
    st.subheader("📁 Arquivos 01 — Base Histórica (um por indicador)")

    # Organizar em abas
    tab_violento, tab_patrimonio, tab_outros = st.tabs(
        ["🔴 Crime Violento", "🟠 Patrimônio", "🔵 Outros"]
    )

    grupos = {
        "🔴 Crime Violento": 
