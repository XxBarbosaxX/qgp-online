from __future__ import annotations

import importlib
import traceback
from typing import Callable, Optional

import streamlit as st


MAPEAMENTO: dict[str, tuple[str, str]] = {
    "TODOS OS INDICADORES": ("todos_indicadores", "interface_todos_indicadores"),
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
    "GEOCODIFICAÇÃO": ("geocodificar", "interface_geocodificar"),
    "CONVERSÃO": ("conversor_coordenadas", "interface_conversor_coordenadas"),
    "CONSOLIDAR INDICADORES": (
        "consolidar_indicadores_criminais",
        "interface_consolidar_indicadores_criminais",
    ),
}


INDICADORES_ATUALIZACAO: list[str] = [
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

MODULOS_GEO: list[str] = [
    "GEOCODIFICAÇÃO",
    "CONVERSÃO",
]

MODULOS_CONSOLIDACAO: list[str] = ["CONSOLIDAR INDICADORES"]


def carregar_modulo(nome_modulo: str, nome_funcao: str) -> Optional[Callable]:
    """Importa módulo sob demanda e retorna a função alvo."""
    try:
        modulo = importlib.import_module(f"modulos.{nome_modulo}")
        func = getattr(modulo, nome_funcao, None)

        if func is None:
            st.error(f"Função '{nome_funcao}' não encontrada no módulo '{nome_modulo}'.")
            return None

        return func
    except Exception as exc:  # noqa: BLE001
        st.error(f"Erro ao carregar módulo '{nome_modulo}': {exc}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
        return None


def executar_interface_segura(func: Callable, nome_indicador: str) -> None:
    """Executa interface dentro de container e captura erros com detalhes."""
    area_execucao = st.container()

    try:
        with area_execucao:
            func()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Erro ao executar o módulo '{nome_indicador}': {exc}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())
