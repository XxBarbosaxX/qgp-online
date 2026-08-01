from __future__ import annotations

import importlib
import logging
from typing import Callable, Optional

import streamlit as st

from services.modules_registry import (
    INDICADORES_ATUALIZACAO,
    MAPEAMENTO,
    MODULOS_CONSOLIDACAO,
    MODULOS_GEO,
)


logger = logging.getLogger(__name__)


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
            return None

        return func

    except Exception:
        logger.exception("Erro ao carregar módulo '%s'.", nome_modulo)
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
