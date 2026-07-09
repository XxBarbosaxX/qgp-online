"""
Módulo de orquestração de todos os indicadores do QGP Online.

Responsável por:
- Expor a interface unificada de processamento dos principais módulos.
- Coordenar a leitura de Arquivo 01 (base histórica) e Arquivo 02 (complemento SIP/Portal).
- Disparar os processamentos específicos (CVP SIP, CVP Portal, Furto/Roubo de Veículo SIP/Portal, etc.).
- Manter uma camada de resumo consolidado dos resultados.

Este módulo NÃO contém regras de negócio específicas de cada indicador.
Cada família de indicador fica encapsulada em seu próprio módulo especializado.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import streamlit as st

from modulos.acidente_transito import processar_acidente_transito
from modulos.cvp_sip import processar_cvp_sip
from modulos.cvp_sportal import processar_cvp_sportal
from modulos.cvli import processar_cvli
from modulos.deslocamento_forcado import processar_deslocamento_forcado
from modulos.furto_veiculo_sip import (
    FurtoVeiculoSipConfig,
    processar_furto_veiculo_sip,
)
from modulos.furto_veiculo_sportal import processar_furto_veiculo_sportal
from modulos.perturbacao_sossego import processar_perturbacao_sossego
from modulos.roubo_veiculo_sip import (
    RouboVeiculoSipConfig,
    processar_roubo_veiculo_sip,
)
from modulos.roubo_veiculo_sportal import processar_roubo_veiculo_sportal
from modulos.utils import nome_arquivo_padrao


def _bytesio_from_session(key: str) -> Optional[BytesIO]:
    """
    Constrói um BytesIO a partir de um conteúdo armazenado na sessão.

    Parameters
    ----------
    key : str
        Chave em st.session_state com bytes de arquivo.

    Returns
    -------
    Optional[BytesIO]
        Buffer pronto para uso em módulos de processamento.
    """
    conteudo = st.session_state.get(key)
    if conteudo is None:
        return None
    buffer = BytesIO(conteudo)
    buffer.seek(0)
    return buffer


def _registrar_resumo_global(chave: str, resumo: Dict[str, Any]) -> None:
    """
    Armazena, em uma estrutura consolidada de sessão, o resumo de um indicador.

    Parameters
    ----------
    chave : str
        Identificador do módulo de indicador (ex.: 'cvp_sip', 'roubo_veiculo_sip').
    resumo : Dict[str, Any]
        Dicionário de resumo retornado pelo módulo específico.
    """
    if "resumos_indicadores" not in st.session_state:
        st.session_state["resumos_indicadores"] = {}

    st.session_state["resumos_indicadores"][chave] = resumo


def executar_cvp_sip() -> None:
    """
    Executa o processamento do módulo CVP SIP
    usando os arquivos já carregados na sessão.
    """
    arq_01 = _bytesio_from_session("cvp_sip_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("cvp_sip_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos do módulo CVP SIP não encontrados na sessão.")
        return

    with st.spinner("Processando CVP (SIP)..."):
        df_final, resumo = processar_cvp_sip(arq_01, arq_02)

    st.session_state.cvp_sip_resultado_df = df_final
    st.session_state.cvp_sip_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(1, "CVP-SIP"),
    )
    _registrar_resumo_global("cvp_sip", resumo)


def executar_cvp_sportal() -> None:
    """
    Executa o processamento do módulo CVP Portal
    usando os arquivos já carregados na sessão.
    """
    arq_01 = _bytesio_from_session("cvp_sportal_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("cvp_sportal_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos do módulo CVP Portal não encontrados na sessão.")
        return

    with st.spinner("Processando CVP (Portal)..."):
        df_final, resumo = processar_cvp_sportal(arq_01, arq_02)

    st.session_state.cvp_sportal_resultado_df = df_final
    st.session_state.cvp_sportal_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(2, "CVP-PORTAL"),
    )
    _registrar_resumo_global("cvp_sportal", resumo)


def executar_cvli() -> None:
    """
    Executa o processamento do módulo CVLI.
    """
    arq_01 = _bytesio_from_session("cvli_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("cvli_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos do módulo CVLI não encontrados na sessão.")
        return

    with st.spinner("Processando CVLI..."):
        df_final, resumo = processar_cvli(arq_01, arq_02)

    st.session_state.cvli_resultado_df = df_final
    st.session_state.cvli_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(3, "CVLI"),
    )
    _registrar_resumo_global("cvli", resumo)


def executar_furto_veiculo_sip(
    config: Optional[FurtoVeiculoSipConfig] = None,
) -> None:
    """
    Executa o processamento de Furto de Veículo (SIP)
    usando os módulos especializados e suas configurações.

    A função de processamento já:
    - Normaliza config quando None.
    - Descobre abas automaticamente.
    - Aplica filtro interno robusto por natureza.
    - Faz geocodificação por endereço com base enxuta + ArcGIS.
    """
    arq_01 = _bytesio_from_session("furto_veiculo_sip_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("furto_veiculo_sip_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Furto de Veículo (SIP) não encontrados na sessão.")
        return

    with st.spinner("Processando Furto de Veículo (SIP)..."):
        df_final, resumo = processar_furto_veiculo_sip(arq_01, arq_02, config)

    st.session_state.furto_veiculo_sip_resultado_df = df_final
    st.session_state.furto_veiculo_sip_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(6, "FURTO-DE-VEICULO-SIP-ENDERECO"),
    )
    _registrar_resumo_global("furto_veiculo_sip", resumo)


def executar_roubo_veiculo_sip(
    config: Optional[RouboVeiculoSipConfig] = None,
) -> None:
    """
    Executa o processamento de Roubo de Veículo (SIP)
    com a nova assinatura do módulo especializado.

    Não cria mais SimpleNamespace nem exige valor_filtro_natureza externo.
    Toda a lógica de filtro por natureza está encapsulada
    em processar_roubo_veiculo_sip.
    """
    arq_01 = _bytesio_from_session("roubo_veiculo_sip_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("roubo_veiculo_sip_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Roubo de Veículo (SIP) não encontrados na sessão.")
        return

    with st.spinner("Processando Roubo de Veículo (SIP)..."):
        df_final, resumo = processar_roubo_veiculo_sip(arq_01, arq_02, config)

    st.session_state.roubo_veiculo_sip_resultado_df = df_final
    st.session_state.roubo_veiculo_sip_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(7, "ROUBO-DE-VEICULO-SIP-ENDERECO"),
    )
    _registrar_resumo_global("roubo_veiculo_sip", resumo)


def executar_furto_veiculo_sportal() -> None:
    """
    Executa o processamento de Furto de Veículo (Portal).
    """
    arq_01 = _bytesio_from_session("furto_veiculo_sportal_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("furto_veiculo_sportal_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Furto de Veículo (Portal) não encontrados na sessão.")
        return

    with st.spinner("Processando Furto de Veículo (Portal)..."):
        df_final, resumo = processar_furto_veiculo_sportal(arq_01, arq_02)

    st.session_state.furto_veiculo_sportal_resultado_df = df_final
    st.session_state.furto_veiculo_sportal_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(8, "FURTO-DE-VEICULO-PORTAL"),
    )
    _registrar_resumo_global("furto_veiculo_sportal", resumo)


def executar_roubo_veiculo_sportal() -> None:
    """
    Executa o processamento de Roubo de Veículo (Portal).
    """
    arq_01 = _bytesio_from_session("roubo_veiculo_sportal_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("roubo_veiculo_sportal_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Roubo de Veículo (Portal) não encontrados na sessão.")
        return

    with st.spinner("Processando Roubo de Veículo (Portal)..."):
        df_final, resumo = processar_roubo_veiculo_sportal(arq_01, arq_02)

    st.session_state.roubo_veiculo_sportal_resultado_df = df_final
    st.session_state.roubo_veiculo_sportal_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(9, "ROUBO-DE-VEICULO-PORTAL"),
    )
    _registrar_resumo_global("roubo_veiculo_sportal", resumo)


def executar_acidente_transito() -> None:
    """
    Executa o processamento de Acidente de Trânsito.
    """
    arq_01 = _bytesio_from_session("acidente_transito_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("acidente_transito_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Acidente de Trânsito não encontrados na sessão.")
        return

    with st.spinner("Processando Acidente de Trânsito..."):
        df_final, resumo = processar_acidente_transito(arq_01, arq_02)

    st.session_state.acidente_transito_resultado_df = df_final
    st.session_state.acidente_transito_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(10, "ACIDENTE-TRANSITO"),
    )
    _registrar_resumo_global("acidente_transito", resumo)


def executar_deslocamento_forcado() -> None:
    """
    Executa o processamento de Deslocamento Forçado.
    """
    arq_01 = _bytesio_from_session("deslocamento_forcado_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("deslocamento_forcado_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Deslocamento Forçado não encontrados na sessão.")
        return

    with st.spinner("Processando Deslocamento Forçado..."):
        df_final, resumo = processar_deslocamento_forcado(arq_01, arq_02)

    st.session_state.deslocamento_forcado_resultado_df = df_final
    st.session_state.deslocamento_forcado_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(11, "DESLOCAMENTO-FORCADO"),
    )
    _registrar_resumo_global("deslocamento_forcado", resumo)


def executar_perturbacao_sossego() -> None:
    """
    Executa o processamento de Perturbação do Sossego.
    """
    arq_01 = _bytesio_from_session("perturbacao_sossego_arquivo_01_bytes")
    arq_02 = _bytesio_from_session("perturbacao_sossego_arquivo_02_bytes")

    if not arq_01 or not arq_02:
        st.warning("Arquivos de Perturbação do Sossego não encontrados na sessão.")
        return

    with st.spinner("Processando Perturbação do Sossego..."):
        df_final, resumo = processar_perturbacao_sossego(arq_01, arq_02)

    st.session_state.perturbacao_sossego_resultado_df = df_final
    st.session_state.perturbacao_sossego_resultado_excel = _gerar_excel_bytes(
        df_final,
        nome_arquivo_padrao(12, "PERTURBACAO-SOSSEGO"),
    )
    _registrar_resumo_global("perturbacao_sossego", resumo)


def _gerar_excel_bytes(df, nome_arquivo: str) -> bytes:
    """
    Gera um Excel em memória para ser usado em botões de download.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame de saída do módulo de indicador.
    nome_arquivo : str
        Nome sugerido para o arquivo final (usado apenas como referência externa).

    Returns
    -------
    bytes
        Conteúdo binário do Excel.
    """
    from io import BytesIO

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:  # type: ignore[name-defined]
        df.to_excel(writer, index=False, sheet_name="BASE_ATUALIZADA")
    buffer.seek(0)
    return buffer.getvalue()


def executar_todos_indicadores() -> None:
    """
    Função de conveniência para executar, em sequência,
    todos os módulos de indicadores que possuam arquivos
    carregados na sessão.

    Cada módulo é independente; falha em um não interrompe os demais.
    """
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
