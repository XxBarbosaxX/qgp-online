"""
Módulo agregador para processamento de todos os indicadores do QGP Online.
"""

from __future__ import annotations

import importlib
from io import BytesIO
from typing import Any, Callable

import pandas as pd
import streamlit as st

from modulos.utils import gerar_arquivo_excel


MODULOS_CONFIG = [
    {
        "id": "cvli",
        "label": "CVLI",
        "modulo": "modulos.cvli",
        "funcao": "processar_cvli",
        "arquivo_01_key": "cvli_arquivo_01_bytes",
        "arquivo_02_key": "cvli_arquivo_02_bytes",
    },
    {
        "id": "cvp_sip",
        "label": "CVP SIP",
        "modulo": "modulos.cvp_sip",
        "funcao": "processar_cvp_sip",
        "arquivo_01_key": "cvp_sip_arquivo_01_bytes",
        "arquivo_02_key": "cvp_sip_arquivo_02_bytes",
    },
    {
        "id": "cvp_sportal",
        "label": "CVP SPORTAL",
        "modulo": "modulos.cvp_sportal",
        "funcao": "processar_cvp_sportal",
        "arquivo_01_key": "cvp_sportal_arquivo_01_bytes",
        "arquivo_02_key": "cvp_sportal_arquivo_02_bytes",
    },
    {
        "id": "acidente_transito",
        "label": "Acidente de Trânsito",
        "modulo": "modulos.acidente_transito",
        "funcao": "processar_acidente_transito",
        "arquivo_01_key": "acidente_transito_arquivo_01_bytes",
        "arquivo_02_key": "acidente_transito_arquivo_02_bytes",
    },
    {
        "id": "perturbacao_sossego",
        "label": "Perturbação do Sossego",
        "modulo": "modulos.perturbacao_sossego",
        "funcao": "processar_perturbacao_sossego",
        "arquivo_01_key": "perturbacao_sossego_arquivo_01_bytes",
        "arquivo_02_key": "perturbacao_sossego_arquivo_02_bytes",
    },
    {
        "id": "deslocamento_forcado",
        "label": "Deslocamento Forçado",
        "modulo": "modulos.deslocamento_forcado",
        "funcao": "processar_deslocamento_forcado",
        "arquivo_01_key": "deslocamento_forcado_arquivo_01_bytes",
        "arquivo_02_key": "deslocamento_forcado_arquivo_02_bytes",
    },
    {
        "id": "furto_veiculo_sip",
        "label": "Furto de Veículo SIP",
        "modulo": "modulos.furto_veiculo_sip",
        "funcao": "processar_furto_veiculo_sip",
        "arquivo_01_key": "furto_veiculo_sip_arquivo_01_bytes",
        "arquivo_02_key": "furto_veiculo_sip_arquivo_02_bytes",
    },
    {
        "id": "furto_veiculo_sportal",
        "label": "Furto de Veículo SPORTAL",
        "modulo": "modulos.furto_veiculo_sportal",
        "funcao": "processar_furto_veiculo_sportal",
        "arquivo_01_key": "furto_veiculo_sportal_arquivo_01_bytes",
        "arquivo_02_key": "furto_veiculo_sportal_arquivo_02_bytes",
    },
    {
        "id": "roubo_veiculo_sip",
        "label": "Roubo de Veículo SIP",
        "modulo": "modulos.roubo_veiculo_sip",
        "funcao": "processar_roubo_veiculo_sip",
        "arquivo_01_key": "roubo_veiculo_sip_arquivo_01_bytes",
        "arquivo_02_key": "roubo_veiculo_sip_arquivo_02_bytes",
    },
    {
        "id": "roubo_veiculo_sportal",
        "label": "Roubo de Veículo SPORTAL",
        "modulo": "modulos.roubo_veiculo_sportal",
        "funcao": "processar_roubo_veiculo_sportal",
        "arquivo_01_key": "roubo_veiculo_sportal_arquivo_01_bytes",
        "arquivo_02_key": "roubo_veiculo_sportal_arquivo_02_bytes",
    },
]


def _aplicar_estilo_todos_indicadores() -> None:
    """Aplica estilo visual da interface agregadora."""
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
                background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(31, 41, 55, 0.95) 100%);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 20px;
                padding: 1.5rem;
                margin-bottom: 1rem;
            }

            .todos-kicker {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.14em;
                font-weight: 800;
                color: #60a5fa;
                margin-bottom: 0.55rem;
            }

            .todos-title {
                font-size: 2rem;
                line-height: 1.1;
                font-weight: 900;
                color: #f9fafb;
                margin-bottom: 0.55rem;
            }

            .todos-description {
                color: rgba(255, 255, 255, 0.78);
                font-size: 0.98rem;
                line-height: 1.6;
                margin: 0;
            }

            .todos-card {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 1rem;
                margin: 0.8rem 0;
            }

            .todos-card-title {
                font-size: 1.05rem;
                font-weight: 800;
                color: #f8fafc;
                margin-bottom: 0.3rem;
            }

            .todos-card-desc {
                font-size: 0.92rem;
                color: rgba(255, 255, 255, 0.70);
                line-height: 1.5;
            }

            .todos-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.9rem;
                margin-top: 1rem;
            }

            .todos-item {
                background: rgba(255, 255, 255, 0.025);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 0.95rem 1rem;
            }

            .todos-item-title {
                font-size: 0.95rem;
                font-weight: 800;
                color: #ffffff;
                margin-bottom: 0.35rem;
            }

            .todos-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.4rem 0.68rem;
                border-radius: 999px;
                font-size: 0.8rem;
                font-weight: 700;
                margin-top: 0.35rem;
            }

            .todos-badge.ok {
                background: rgba(34, 197, 94, 0.12);
                color: #bbf7d0;
                border: 1px solid rgba(34, 197, 94, 0.22);
            }

            .todos-badge.warn {
                background: rgba(245, 158, 11, 0.12);
                color: #fde68a;
                border: 1px solid rgba(245, 158, 11, 0.22);
            }

            .todos-badge.err {
                background: rgba(239, 68, 68, 0.12);
                color: #fecaca;
                border: 1px solid rgba(239, 68, 68, 0.22);
            }

            .todos-upload-label {
                font-size: 0.86rem;
                font-weight: 700;
                color: rgba(249, 250, 251, 0.92);
                margin-bottom: 0.15rem;
            }

            @media (max-width: 900px) {
                .todos-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _obter_funcao_processamento(nome_modulo: str, nome_funcao: str) -> Callable:
    """
    Importa dinamicamente uma função pública de processamento.
    """
    modulo = importlib.import_module(nome_modulo)

    if hasattr(modulo, nome_funcao):
        return getattr(modulo, nome_funcao)

    candidatos = ["processar", "executar"]
    for candidato in candidatos:
        if hasattr(modulo, candidato):
            return getattr(modulo, candidato)

    raise AttributeError(
        f"Nenhuma função compatível encontrada em '{nome_modulo}'. "
        f"Candidatos testados: {nome_funcao}, processar, executar"
    )


def _carregar_arquivos_da_sessao(config: dict[str, Any]) -> tuple[BytesIO, BytesIO]:
    """
    Recupera arquivos em memória a partir do session_state.
    """
    arquivo_01_bytes = st.session_state.get(config["arquivo_01_key"])
    arquivo_02_bytes = st.session_state.get(config["arquivo_02_key"])

    if not arquivo_01_bytes or not arquivo_02_bytes:
        raise FileNotFoundError(
            f"Arquivos do módulo {config['label']} não encontrados na sessão."
        )

    return BytesIO(arquivo_01_bytes), BytesIO(arquivo_02_bytes)


def _executar_modulo(config: dict[str, Any]) -> dict[str, Any]:
    """
    Executa um módulo individual e retorna o resultado padronizado.
    """
    try:
        func_processamento = _obter_funcao_processamento(
            config["modulo"],
            config["funcao"],
        )
        arquivo_01, arquivo_02 = _carregar_arquivos_da_sessao(config)

        resultado = func_processamento(arquivo_01, arquivo_02)

        if not isinstance(resultado, tuple) or len(resultado) != 2:
            raise ValueError(
                f"O módulo {config['label']} deve retornar (df_final, resumo)."
            )

        df_final, resumo = resultado

        excel_bytes = gerar_arquivo_excel(df_final, sheet_name=config["label"][:31])

        return {
            "sucesso": True,
            "df_final": df_final,
            "resumo": resumo,
            "excel_bytes": excel_bytes,
        }

    except Exception as exc:
        return {
            "sucesso": False,
            "erro": str(exc),
        }


def _executar_todos_indicadores() -> dict[str, dict[str, Any]]:
    """
    Executa todos os módulos configurados.
    """
    resultados: dict[str, dict[str, Any]] = {}

    for config in MODULOS_CONFIG:
        resultados[config["id"]] = _executar_modulo(config)

    return resultados


def _render_resultados(resultados: dict[str, dict[str, Any]]) -> None:
    """Renderiza os resultados do processamento consolidado."""
    st.markdown(
        """
        <div class="todos-card">
            <div class="todos-card-title">Status dos módulos processados</div>
            <div class="todos-card-desc">
                Abaixo está o resultado consolidado da execução dos indicadores disponíveis.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cards_html = ['<div class="todos-grid">']

    for config in MODULOS_CONFIG:
        resultado = resultados.get(config["id"], {})
        if resultado.get("sucesso"):
            badge = '<div class="todos-badge ok">Processado com sucesso</div>'
            detalhe = ""
            resumo = resultado.get("resumo", {})
            if resumo:
                adicionados = resumo.get("adicionados", "N/A")
                total_final = resumo.get("total_final", "N/A")
                detalhe = (
                    f"<div style='color: rgba(255,255,255,0.72); font-size: 0.88rem;'>"
                    f"Adicionados: {adicionados}<br>Total final: {total_final}"
                    f"</div>"
                )
        else:
            badge = '<div class="todos-badge err">Falha no processamento</div>'
            detalhe = (
                f"<div style='color: #fecaca; font-size: 0.88rem;'>"
                f"{resultado.get('erro', 'Erro não informado')}"
                f"</div>"
            )

        cards_html.append(
            f"""
            <div class="todos-item">
                <div class="todos-item-title">{config["label"]}</div>
                {badge}
                {detalhe}
            </div>
            """
        )

    cards_html.append("</div>")
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    for config in MODULOS_CONFIG:
        resultado = resultados.get(config["id"], {})
        if resultado.get("sucesso"):
            with st.expander(f"Prévia - {config['label']}", expanded=False):
                st.dataframe(
                    resultado["df_final"].head(200),
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    label=f"💾 Baixar resultado - {config['label']}",
                    data=resultado["excel_bytes"],
                    file_name=f"{config['id']}_processado.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    key=f"download_{config['id']}",
                    use_container_width=True,
                )


def _render_uploads_por_modulo() -> None:
    """Renderiza área de upload de Arquivo 01 e 02 para cada módulo."""
    st.markdown(
        """
        <div class="todos-card">
            <div class="todos-card-title">Arquivos por módulo</div>
            <div class="todos-card-desc">
                Carregue os arquivos 01 (base) e 02 (complemento) diretamente por módulo. 
                Esses arquivos serão usados tanto nas interfaces individuais quanto no 
                processamento consolidado.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for config in MODULOS_CONFIG:
        with st.expander(f"Arquivos - {config['label']}", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(
                    '<div class="todos-upload-label">📁 Arquivo 01 - Base</div>',
                    unsafe_allow_html=True,
                )
                arq1 = st.file_uploader(
                    f"Arquivo 01 - {config['label']}",
                    type=["xlsx", "xls"],
                    key=f"{config['id']}_arquivo_01_upload",
                    label_visibility="collapsed",
                )
                if arq1 is not None:
                    st.session_state[config["arquivo_01_key"]] = arq1.getvalue()
                    st.caption("✅ Arquivo 01 carregado na sessão.")

            with col2:
                st.markdown(
                    '<div class="todos-upload-label">📁 Arquivo 02 - Complemento</div>',
                    unsafe_allow_html=True,
                )
                arq2 = st.file_uploader(
                    f"Arquivo 02 - {config['label']}",
                    type=["xlsx", "xls"],
                    key=f"{config['id']}_arquivo_02_upload",
                    label_visibility="collapsed",
                )
                if arq2 is not None:
                    st.session_state[config["arquivo_02_key"]] = arq2.getvalue()
                    st.caption("✅ Arquivo 02 carregado na sessão.")


def interface_todos_indicadores() -> None:
    """
    Interface principal do módulo agregador de todos os indicadores.
    """
    _aplicar_estilo_todos_indicadores()

    st.markdown(
        """
        <div class="todos-shell">
            <div class="todos-hero">
                <div class="todos-kicker">Processamento consolidado</div>
                <div class="todos-title">Todos os Indicadores</div>
                <p class="todos-description">
                    Execute em lote os módulos disponíveis do QGP Online. Você pode carregar os
                    arquivos de cada módulo diretamente aqui ou nas interfaces individuais. O
                    sistema utiliza sempre os arquivos persistidos em memória na sessão atual.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _render_uploads_por_modulo()

    st.markdown(
        """
        <div class="todos-card">
            <div class="todos-card-title">Execução consolidada</div>
            <div class="todos-card-desc">
                Ao iniciar o processamento, cada módulo será executado de forma independente 
                com base nos arquivos atualmente disponíveis em memória. Módulos sem arquivos 
                carregados serão marcados como falha na execução.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    executar = st.button(
        "🚀 Processar todos os indicadores",
        type="primary",
        use_container_width=True,
        key="btn_processar_todos_indicadores",
    )

    if executar:
        with st.spinner("Processando todos os indicadores..."):
            resultados = _executar_todos_indicadores()
            st.session_state["todos_indicadores_resultados"] = resultados

    resultados = st.session_state.get("todos_indicadores_resultados")

    if resultados:
        _render_resultados(resultados)
