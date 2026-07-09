"""
Módulo de orquestração de todos os indicadores do QGP Online.

Objetivo:
- Centralizar a execução dos módulos de processamento.
- Permitir execução individual e execução em lote.
- Manter compatibilidade com módulos que usem nomes diferentes
  para suas funções principais de processamento.
"""

from __future__ import annotations

from importlib import import_module
from io import BytesIO
from typing import Any, Callable, Dict, Optional

import pandas as pd
import streamlit as st

from modulos.utils import nome_arquivo_padrao


def _importar_funcao(modulo_path: str, candidatos: list[str]) -> Callable:
    """
    Importa dinamicamente a primeira função existente entre os nomes candidatos.

    Parameters
    ----------
    modulo_path : str
        Caminho do módulo Python.
    candidatos : list[str]
        Lista ordenada de nomes possíveis da função.

    Returns
    -------
    Callable
        Função encontrada no módulo.

    Raises
    ------
    ImportError
        Caso nenhuma função compatível seja localizada.
    """
    modulo = import_module(modulo_path)

    for nome in candidatos:
        func = getattr(modulo, nome, None)
        if callable(func):
            return func

    raise ImportError(
        f"Nenhuma função compatível encontrada em '{modulo_path}'. "
        f"Candidatos testados: {', '.join(candidatos)}"
    )


def _importar_classe_opcional(modulo_path: str, nome_classe: str):
    """
    Importa uma classe opcional. Se não existir, retorna None.
    """
    modulo = import_module(modulo_path)
    return getattr(modulo, nome_classe, None)


FurtoVeiculoSipConfig = _importar_classe_opcional(
    "modulos.furto_veiculo_sip",
    "FurtoVeiculoSipConfig",
)
RouboVeiculoSipConfig = _importar_classe_opcional(
    "modulos.roubo_veiculo_sip",
    "RouboVeiculoSipConfig",
)

processar_cvp_sip = _importar_funcao(
    "modulos.cvp_sip",
    [
        "processar_cvp_sip",
        "processar",
        "executar",
    ],
)

processar_cvp_sportal = _importar_funcao(
    "modulos.cvp_sportal",
    [
        "processar_cvp_sportal",
        "processar_cvp_portal",
        "processar_sportal",
        "processar",
        "executar",
    ],
)

processar_cvli = _importar_funcao(
    "modulos.cvli",
    [
        "processar_cvli",
        "processar",
        "executar",
    ],
)

processar_deslocamento_forcado = _importar_funcao(
    "modulos.deslocamento_forcado",
    [
        "processar_deslocamento_forcado",
        "processar",
        "executar",
    ],
)

processar_acidente_transito = _importar_funcao(
    "modulos.acidente_transito",
    [
        "processar_acidente_transito",
        "processar",
        "executar",
    ],
)

processar_perturbacao_sossego = _importar_funcao(
    "modulos.perturbacao_sossego",
    [
        "processar_perturbacao_sossego",
        "processar",
        "executar",
    ],
)

processar_furto_veiculo_sip = _importar_funcao(
    "modulos.furto_veiculo_sip",
    [
        "processar_furto_veiculo_sip",
        "processar",
        "executar",
    ],
)

processar_roubo_veiculo_sip = _importar_funcao(
    "modulos.roubo_veiculo_sip",
    [
        "processar_roubo_veiculo_sip",
        "processar",
        "executar",
    ],
)

processar_furto_veiculo_sportal = _importar_funcao(
    "modulos.furto_veiculo_sportal",
    [
        "processar_furto_veiculo_sportal",
        "processar_furto_veiculo_portal",
        "processar",
        "executar",
    ],
)

processar_roubo_veiculo_sportal = _importar_funcao(
    "modulos.roubo_veiculo_sportal",
    [
        "processar_roubo_veiculo_sportal",
        "processar_roubo_veiculo_portal",
        "processar",
        "executar",
    ],
)


def _bytesio_from_session(key: str) -> Optional[BytesIO]:
    conteudo = st.session_state.get(key)
    if conteudo is None:
        return None
    buffer = BytesIO(conteudo)
    buffer.seek(0)
    return buffer


def _registrar_resumo_global(chave: str, resumo: Dict[str, Any]) -> None:
    if "resumos_indicadores" not in st.session_state:
        st.session_state["resumos_indicadores"] = {}
    st.session_state["resumos_indicadores"][chave] = resumo


def _gerar_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="BASE_ATUALIZADA")
    buffer.seek(0)
    return buffer.getvalue()


def _executar_modulo_padrao(
    *,
    chave_modulo: str,
    chave_arquivo_01: str,
    chave_arquivo_02: str,
    func_processamento: Callable,
    chave_resultado_df: str,
    chave_resultado_excel: str,
    mensagem_spinner: str,
    mensagem_warning: str,
    config: Any = None,
) -> None:
    arq_01 = _bytesio_from_session(chave_arquivo_01)
    arq_02 = _bytesio_from_session(chave_arquivo_02)

    if not arq_01 or not arq_02:
        st.warning(mensagem_warning)
        return

    with st.spinner(mensagem_spinner):
        if config is None:
            df_final, resumo = func_processamento(arq_01, arq_02)
        else:
            df_final, resumo = func_processamento(arq_01, arq_02, config)

    st.session_state[chave_resultado_df] = df_final
    st.session_state[chave_resultado_excel] = _gerar_excel_bytes(df_final)
    _registrar_resumo_global(chave_modulo, resumo)


def executar_cvp_sip() -> None:
    _executar_modulo_padrao(
        chave_modulo="cvp_sip",
        chave_arquivo_01="cvp_sip_arquivo_01_bytes",
        chave_arquivo_02="cvp_sip_arquivo_02_bytes",
        func_processamento=processar_cvp_sip,
        chave_resultado_df="cvp_sip_resultado_df",
        chave_resultado_excel="cvp_sip_resultado_excel",
        mensagem_spinner="Processando CVP (SIP)...",
        mensagem_warning="Arquivos do módulo CVP SIP não encontrados na sessão.",
    )


def executar_cvp_sportal() -> None:
    _executar_modulo_padrao(
        chave_modulo="cvp_sportal",
        chave_arquivo_01="cvp_sportal_arquivo_01_bytes",
        chave_arquivo_02="cvp_sportal_arquivo_02_bytes",
        func_processamento=processar_cvp_sportal,
        chave_resultado_df="cvp_sportal_resultado_df",
        chave_resultado_excel="cvp_sportal_resultado_excel",
        mensagem_spinner="Processando CVP (Portal)...",
        mensagem_warning="Arquivos do módulo CVP Portal não encontrados na sessão.",
    )


def executar_cvli() -> None:
    _executar_modulo_padrao(
        chave_modulo="cvli",
        chave_arquivo_01="cvli_arquivo_01_bytes",
        chave_arquivo_02="cvli_arquivo_02_bytes",
        func_processamento=processar_cvli,
        chave_resultado_df="cvli_resultado_df",
        chave_resultado_excel="cvli_resultado_excel",
        mensagem_spinner="Processando CVLI...",
        mensagem_warning="Arquivos do módulo CVLI não encontrados na sessão.",
    )


def executar_furto_veiculo_sip(
    config: Optional[Any] = None,
) -> None:
    _executar_modulo_padrao(
        chave_modulo="furto_veiculo_sip",
        chave_arquivo_01="furto_veiculo_sip_arquivo_01_bytes",
        chave_arquivo_02="furto_veiculo_sip_arquivo_02_bytes",
        func_processamento=processar_furto_veiculo_sip,
        chave_resultado_df="furto_veiculo_sip_resultado_df",
        chave_resultado_excel="furto_veiculo_sip_resultado_excel",
        mensagem_spinner="Processando Furto de Veículo (SIP)...",
        mensagem_warning="Arquivos de Furto de Veículo (SIP) não encontrados na sessão.",
        config=config,
    )


def executar_roubo_veiculo_sip(
    config: Optional[Any] = None,
) -> None:
    _executar_modulo_padrao(
        chave_modulo="roubo_veiculo_sip",
        chave_arquivo_01="roubo_veiculo_sip_arquivo_01_bytes",
        chave_arquivo_02="roubo_veiculo_sip_arquivo_02_bytes",
        func_processamento=processar_roubo_veiculo_sip,
        chave_resultado_df="roubo_veiculo_sip_resultado_df",
        chave_resultado_excel="roubo_veiculo_sip_resultado_excel",
        mensagem_spinner="Processando Roubo de Veículo (SIP)...",
        mensagem_warning="Arquivos de Roubo de Veículo (SIP) não encontrados na sessão.",
        config=config,
    )


def executar_furto_veiculo_sportal() -> None:
    _executar_modulo_padrao(
        chave_modulo="furto_veiculo_sportal",
        chave_arquivo_01="furto_veiculo_sportal_arquivo_01_bytes",
        chave_arquivo_02="furto_veiculo_sportal_arquivo_02_bytes",
        func_processamento=processar_furto_veiculo_sportal,
        chave_resultado_df="furto_veiculo_sportal_resultado_df",
        chave_resultado_excel="furto_veiculo_sportal_resultado_excel",
        mensagem_spinner="Processando Furto de Veículo (Portal)...",
        mensagem_warning="Arquivos de Furto de Veículo (Portal) não encontrados na sessão.",
    )


def executar_roubo_veiculo_sportal() -> None:
    _executar_modulo_padrao(
        chave_modulo="roubo_veiculo_sportal",
        chave_arquivo_01="roubo_veiculo_sportal_arquivo_01_bytes",
        chave_arquivo_02="roubo_veiculo_sportal_arquivo_02_bytes",
        func_processamento=processar_roubo_veiculo_sportal,
        chave_resultado_df="roubo_veiculo_sportal_resultado_df",
        chave_resultado_excel="roubo_veiculo_sportal_resultado_excel",
        mensagem_spinner="Processando Roubo de Veículo (Portal)...",
        mensagem_warning="Arquivos de Roubo de Veículo (Portal) não encontrados na sessão.",
    )


def executar_acidente_transito() -> None:
    _executar_modulo_padrao(
        chave_modulo="acidente_transito",
        chave_arquivo_01="acidente_transito_arquivo_01_bytes",
        chave_arquivo_02="acidente_transito_arquivo_02_bytes",
        func_processamento=processar_acidente_transito,
        chave_resultado_df="acidente_transito_resultado_df",
        chave_resultado_excel="acidente_transito_resultado_excel",
        mensagem_spinner="Processando Acidente de Trânsito...",
        mensagem_warning="Arquivos de Acidente de Trânsito não encontrados na sessão.",
    )


def executar_deslocamento_forcado() -> None:
    _executar_modulo_padrao(
        chave_modulo="deslocamento_forcado",
        chave_arquivo_01="deslocamento_forcado_arquivo_01_bytes",
        chave_arquivo_02="deslocamento_forcado_arquivo_02_bytes",
        func_processamento=processar_deslocamento_forcado,
        chave_resultado_df="deslocamento_forcado_resultado_df",
        chave_resultado_excel="deslocamento_forcado_resultado_excel",
        mensagem_spinner="Processando Deslocamento Forçado...",
        mensagem_warning="Arquivos de Deslocamento Forçado não encontrados na sessão.",
    )


def executar_perturbacao_sossego() -> None:
    _executar_modulo_padrao(
        chave_modulo="perturbacao_sossego",
        chave_arquivo_01="perturbacao_sossego_arquivo_01_bytes",
        chave_arquivo_02="perturbacao_sossego_arquivo_02_bytes",
        func_processamento=processar_perturbacao_sossego,
        chave_resultado_df="perturbacao_sossego_resultado_df",
        chave_resultado_excel="perturbacao_sossego_resultado_excel",
        mensagem_spinner="Processando Perturbação do Sossego...",
        mensagem_warning="Arquivos de Perturbação do Sossego não encontrados na sessão.",
    )


def executar_todos_indicadores() -> None:
    funcoes = [
        ("cvp_sip", executar_cvp_sip),
        ("cvp_sportal", executar_cvp_sportal),
        ("cvli", executar_cvli),
        ("furto_veiculo_sip", executar_furto_veiculo_sip),
        ("roubo_veiculo_sip", executar_roubo_veiculo_sip),
        ("furto_veiculo_sportal", executar_furto_veiculo_sportal),
        ("roubo_veiculo_sportal", executar_roubo_veiculo_sportal),
        ("acidente_transito", executar_acidente_transito),
        ("deslocamento_forcado", executar_deslocamento_forcado),
        ("perturbacao_sossego", executar_perturbacao_sossego),
    ]

    for nome, func in funcoes:
        try:
            func()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falha ao processar módulo '{nome}': {exc}")


__all__ = [
    "executar_cvp_sip",
    "executar_cvp_sportal",
    "executar_cvli",
    "executar_furto_veiculo_sip",
    "executar_roubo_veiculo_sip",
    "executar_furto_veiculo_sportal",
    "executar_roubo_veiculo_sportal",
    "executar_acidente_transito",
    "executar_deslocamento_forcado",
    "executar_perturbacao_sossego",
    "executar_todos_indicadores",
]
