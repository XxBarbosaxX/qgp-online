from __future__ import annotations

import importlib
import logging
from typing import Callable, Optional

import streamlit as st


logger = logging.getLogger(__name__)


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
            logger.error(
                "Função '%s' não encontrada no módulo '%s'.",
                nome_funcao,
                nome_modulo,
            )
            st.error(
                "Não foi possível carregar o módulo solicitado. "
                "Verifique a configuração da aplicação."
            )
            return None

        return func

    except Exception:
        logger.exception("Erro ao carregar módulo '%s'.", nome_modulo)
        st.error(
            "Ocorreu um erro interno ao carregar o módulo solicitado. "
            "Tente novamente ou contate o administrador do sistema."
        )
        return None


def executar_interface_segura(func: Callable, nome_indicador: str) -> None:
    """Executa interface dentro de container e captura erros sem expor detalhes internos."""
    area_execucao = st.container()

    try:
        with area_execucao:
            func()

    except Exception:
        logger.exception("Erro ao executar o módulo '%s'.", nome_indicador)
        st.error(
            "Ocorreu um erro interno ao executar este módulo. "
            "Tente novamente ou contate o administrador do sistema."
        )
