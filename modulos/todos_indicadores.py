"""
Módulo agregador para processamento de todos os indicadores do QGP Online.
Fluxo:
- Arquivo 01: base consolidada contendo os 10 indicadores.
- Arquivo 02: arquivo complementar com múltiplas abas, uma para cada indicador.
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
        "aba_arquivo_02": "CVLI",
    },
    {
        "id": "cvp_sip",
        "label": "CVP SIP",
        "modulo": "modulos.cvp_sip",
        "funcao": "processar_cvp_sip",
        "aba_arquivo_02": "CVP SIP",
    },
    {
        "id": "cvp_sportal",
        "label": "CVP SPORTAL",
        "modulo": "modulos.cvp_sportal",
        "funcao": "processar_cvp_sportal",
        "aba_arquivo_02": "CVP SPORTAL",
    },
    {
        "id": "acidente_transito",
        "label": "Acidente de Trânsito",
        "modulo": "modulos.acidente_transito",
        "funcao": "processar_acidente_transito",
        "aba_arquivo_02": "ACIDENTE TRANSITO",
    },
    {
        "id": "perturbacao_sossego",
        "label": "Perturbação do Sossego",
        "modulo": "modulos.perturbacao_sossego",
        "funcao": "processar_perturbacao_sossego",
        "aba_arquivo_02": "PERTURBACAO SOSSEGO",
    },
    {
        "id": "deslocamento_forcado",
        "label": "Deslocamento Forçado",
        "modulo": "modulos.deslocamento_forcado",
        "funcao": "processar_deslocamento_forcado",
        "aba_arquivo_02": "DESLOCAMENTO FORCADO",
    },
    {
        "id": "furto_veiculo_sip",
        "label": "Furto de Veículo SIP",
        "modulo": "modulos.furto_veiculo_sip",
        "funcao": "processar_furto_veiculo_sip",
        "aba_arquivo_02": "FURTO VEICULO SIP",
    },
    {
        "id": "furto_veiculo_sportal",
        "label": "Furto de Veículo SPORTAL",
        "modulo": "modulos.furto_veiculo_sportal",
        "funcao": "processar_furto_veiculo_sportal",
        "aba_arquivo_02": "FURTO VEICULO SPORTAL",
    },
    {
        "id": "roubo_veiculo_sip",
        "label": "Roubo de Veículo SIP",
        "modulo": "modulos.roubo_veiculo_sip",
        "funcao": "processar_roubo_veiculo_sip",
        "aba_arquivo_02": "ROUBO VEICULO SIP",
    },
    {
        "id": "roubo_veiculo_sportal",
        "label": "Roubo de Veículo SPORTAL",
        "modulo": "modulos.roubo_veiculo_sportal",
        "funcao": "processar_roubo_veiculo_sportal",
        "aba_arquivo_02": "ROUBO VEICULO SPORTAL",
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
                background: linear-gradient(135deg, rgba(17, 24, 39, 0.96) 0%, rgba(31, 41, 55, 0.96) 100%);
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

            @media (max-width: 900px) {
                .todos-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _normalizar_nome_aba(nome: str) -> str:
    """Normaliza o nome de aba para comparação flexível."""
    return (
        str(nome)
        .strip()
        .upper()
        .replace("_", " ")
        .replace("-", " ")
        .replace("Á", "A")
        .replace("À", "A")
        .replace("Ã", "A")
        .replace("Â", "A")
        .replace("É", "E")
        .replace("Ê", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ô", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
        .replace("Ç", "C")
    )


def _obter_funcao_processamento(nome_modulo: str, nome_funcao: str) -> Callable:
    """Importa dinamicamente a função pública de processamento do módulo."""
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


def _carregar_abas_arquivo_02(arquivo_02_bytes: bytes) -> dict[str, pd.DataFrame]:
    """Lê todas as abas do Arquivo 02 e retorna um dicionário normalizado."""
    workbook = pd.read_excel(BytesIO(arquivo_02_bytes), sheet_name=None)
    return {_normalizar_nome_aba(nome): df for nome, df in workbook.items()}


def _extrair_base_indicador_arquivo_01(
    arquivo_01_bytes: bytes,
    nome_indicador: str,
) -> BytesIO:
    """
    Extrai a base do indicador a partir do Arquivo 01.

    Estratégia:
    - tenta encontrar uma aba com o nome do indicador;
    - se não encontrar, assume a primeira aba como fallback.
    """
    workbook = pd.read_excel(BytesIO(arquivo_01_bytes), sheet_name=None)

    if not workbook:
        raise ValueError("O Arquivo 01 não possui abas válidas.")

    abas_normalizadas = {
        _normalizar_nome_aba(nome): (nome, df)
        for nome, df in workbook.items()
    }

    chave = _normalizar_nome_aba(nome_indicador)
    if chave in abas_normalizadas:
        _, df_base = abas_normalizadas[chave]
    else:
        _, df_base = next(iter(workbook.items()))

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_base.to_excel(writer, index=False, sheet_name="Base")
    output.seek(0)
    return output


def _extrair_complemento_indicador_arquivo_02(
    abas_arquivo_02: dict[str, pd.DataFrame],
    nome_aba_esperada: str,
) -> BytesIO:
    """Extrai do Arquivo 02 a aba correspondente ao indicador."""
    chave_esperada = _normalizar_nome_aba(nome_aba_esperada)

    if chave_esperada not in abas_arquivo_02:
        raise ValueError(
            f"A aba '{nome_aba_esperada}' não foi encontrada no Arquivo 02."
        )

    df = abas_arquivo_02[chave_esperada]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Complemento")
    output.seek(0)
    return output


def _executar_modulo(
    config: dict[str, Any],
    arquivo_01_bytes: bytes,
    abas_arquivo_02: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    """Executa um módulo individual usando a base do Arquivo 01 e a aba correspondente do Arquivo 02."""
    try:
        func_processamento = _obter_funcao_processamento(
            config["modulo"],
            config["funcao"],
        )

        arquivo_01 = _extrair_base_indicador_arquivo_01(
            arquivo_01_bytes,
            config["label"],
        )
        arquivo_02 = _extrair_complemento_indicador_arquivo_02(
            abas_arquivo_02,
            config["aba_arquivo_02"],
        )

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


def _executar_todos_indicadores(
    arquivo_01_bytes: bytes,
    arquivo_02_bytes: bytes,
) -> dict[str, dict[str, Any]]:
    """Executa todos os módulos configurados."""
    abas_arquivo_02 = _carregar_abas_arquivo_02(arquivo_02_bytes)
    resultados: dict[str, dict[str, Any]] = {}

    for config in MODULOS_CONFIG:
        resultados[config["id"]] = _executar_modulo(
            config=config,
            arquivo_01_bytes=arquivo_01_bytes,
            abas_arquivo_02=abas_arquivo_02,
        )

    return resultados


def _render_resultados(resultados: dict[str, dict[str, Any]]) -> None:
    """Renderiza os resultados do processamento consolidado."""
    st.markdown(
        """
        <div class="todos-card">
            <div class="todos-card-title">Status dos indicadores processados</div>
            <div class="todos-card-desc">
                Resultado consolidado do processamento a partir do Arquivo 01 e das abas do Arquivo 02.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cards_html = ['<div class="todos-grid">']

    for config in MODULOS_CONFIG:
        resultado = resultados.get(config["id"], {})

        if resultado.get("sucesso"):
            resumo = resultado.get("resumo", {})
            badge = '<div class="todos-badge ok">Processado com sucesso</div>'
            detalhe = (
                f"<div style='color: rgba(255,255,255,0.72); font-size: 0.88rem;'>"
                f"Adicionados: {resumo.get('adicionados', 'N/A')}<br>"
                f"Total final: {resumo.get('total_final', 'N/A')}"
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
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{config['id']}",
                    use_container_width=True,
                )


def interface_todos_indicadores() -> None:
    """Interface principal do módulo agregador."""
    _aplicar_estilo_todos_indicadores()

    st.markdown(
        """
        <div class="todos-shell">
            <div class="todos-hero">
                <div class="todos-kicker">Módulo ativo</div>
                <div class="todos-title">TODOS OS INDICADORES</div>
                <p class="todos-description">
                    Envie o Arquivo 01 com a base dos indicadores e o Arquivo 02 com múltiplas abas.
                    O sistema irá identificar cada aba correspondente e executar o processamento
                    consolidado dos 10 indicadores.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="todos-card">
            <div class="todos-card-title">Arquivos de entrada</div>
            <div class="todos-card-desc">
                Arquivo 01: base consolidada dos indicadores.<br>
                Arquivo 02: planilha complementar com várias abas, uma para cada indicador.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        arquivo_01 = st.file_uploader(
            "📁 Arquivo 01 - Base consolidada",
            type=["xlsx", "xls"],
            key="todos_indicadores_arquivo_01",
        )

    with col2:
        arquivo_02 = st.file_uploader(
            "📁 Arquivo 02 - Arquivo com múltiplas abas",
            type=["xlsx", "xls"],
            key="todos_indicadores_arquivo_02",
        )

    pode_processar = arquivo_01 is not None and arquivo_02 is not None

    if arquivo_02 is not None:
        try:
            abas = pd.ExcelFile(arquivo_02).sheet_names
            arquivo_02.seek(0)
            st.info(f"Abas identificadas no Arquivo 02: {', '.join(abas)}")
        except Exception:
            arquivo_02.seek(0)

    st.markdown(
        """
        <div class="todos-card">
            <div class="todos-card-title">Execução consolidada</div>
            <div class="todos-card-desc">
                O processamento distribui automaticamente os dados do Arquivo 02 para os respectivos
                módulos, conforme a aba correspondente a cada indicador.
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
        disabled=not pode_processar,
    )

    if executar:
        with st.spinner("Processando todos os indicadores..."):
            resultados = _executar_todos_indicadores(
                arquivo_01_bytes=arquivo_01.getvalue(),
                arquivo_02_bytes=arquivo_02.getvalue(),
            )
            st.session_state["todos_indicadores_resultados"] = resultados

    resultados = st.session_state.get("todos_indicadores_resultados")

    if resultados:
        _render_resultados(resultados)
