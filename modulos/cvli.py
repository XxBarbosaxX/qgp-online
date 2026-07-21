"""
Módulo CVLI - Crimes Violentos Letais Intencionais
Processamento e atualização de dados CVLI para QGP Online
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modulos.utils import (
    alinhar_colunas_com_base,
    converter_coluna_data,
    encontrar_coluna_data,
    gerar_arquivo_excel,
    nome_arquivo_padrao,
    normalizar_colunas,
    obter_meses_anos,
    selecionar_aba_atualizacao,
)


class ProcessadorCVLI:
    """Classe para processar dados de CVLI."""

    def __init__(self) -> None:
        self.nome_arquivo_final = nome_arquivo_padrao(1, "CVLI")

    @staticmethod
    def _selecionar_aba_arquivo_02(sheet_names: list[str]) -> str:
        """Seleciona a aba correta do Arquivo 01 complementar conforme chaveamento oficial."""
        return selecionar_aba_atualizacao(sheet_names, "cvli")

    @staticmethod
    def renomear_colunas_equivalentes(
        df_base: pd.DataFrame,
        df_novo: pd.DataFrame,
    ) -> pd.DataFrame:
        """Renomeia colunas equivalentes do arquivo novo para coincidir com a base."""
        mapa_equivalencias = {
            "AIS": ["AIS Nova", "AIS_Nova", "AISNOVA", "ais nova", "ais_nova"],
        }

        colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
        colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}

        renomeacoes: dict[str, str] = {}

        for coluna_base_oficial, aliases in mapa_equivalencias.items():
            chave_base = coluna_base_oficial.strip().lower()
            if chave_base not in colunas_base_map:
                continue

            nome_real_base = colunas_base_map[chave_base]
            if nome_real_base in df_novo.columns:
                continue

            for alias in aliases:
                chave_alias = alias.strip().lower()
                if chave_alias in colunas_novo_map:
                    nome_real_novo = colunas_novo_map[chave_alias]
                    renomeacoes[nome_real_novo] = nome_real_base
                    break

        if renomeacoes:
            df_novo = df_novo.rename(columns=renomeacoes)

        return df_novo

    def atualizar_base(
        self,
        df_base: pd.DataFrame,
        df_novo: pd.DataFrame,
        coluna_data: str,
    ) -> tuple[pd.DataFrame, int, int, int, bool]:
        """Atualiza a base removendo dados antigos e adicionando novos."""
        total_inicial = len(df_base)

        df_novo = self.renomear_colunas_equivalentes(df_base, df_novo)
        df_novo = alinhar_colunas_com_base(df_base, df_novo)

        meses_anos_novo = obter_meses_anos(df_novo, coluna_data)

        if not meses_anos_novo:
            raise ValueError("O Arquivo 01 não possui datas válidas na coluna de data.")

        mask_remover = df_base[coluna_data].notna() & df_base[coluna_data].apply(
            lambda x: (x.year, x.month) in meses_anos_novo
        )

        houve_substituicao = bool(mask_remover.any())

        if houve_substituicao:
            df_base_atualizada = df_base.loc[~mask_remover].copy()
        else:
            df_base_atualizada = df_base.copy()

        total_antes_add = len(df_base_atualizada)

        df_final = pd.concat([df_base_atualizada, df_novo], ignore_index=True)
        df_final = df_final.sort_values(
            by=coluna_data,
            ascending=True,
            na_position="last",
        ).reset_index(drop=True)

        adicionados = len(df_final) - total_antes_add
        total_final = len(df_final)

        return df_final, adicionados, total_final, total_inicial, houve_substituicao

    def processar(self, arquivo01, arquivo02) -> dict:
        """Processa os arquivos CVLI com ordem invertida: arquivo01=complementar, arquivo02=base."""
        try:
            arquivo01.seek(0)
            arquivo02.seek(0)

            # Inversão da ordem esperada:
            # arquivo01 = complementar/atualização
            # arquivo02 = base consolidada atual
            xls_novo = pd.ExcelFile(arquivo01)
            xls_base = pd.ExcelFile(arquivo02)

            aba_novo = self._selecionar_aba_arquivo_02(xls_novo.sheet_names)
            aba_base = xls_base.sheet_names[0]

            df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)
            df_base = pd.read_excel(xls_base, sheet_name=aba_base)

            df_base = normalizar_colunas(df_base)
            df_novo = normalizar_colunas(df_novo)

            coluna_data_base = encontrar_coluna_data(df_base)
            coluna_data_novo = encontrar_coluna_data(df_novo)

            df_base = converter_coluna_data(df_base, coluna_data_base)
            df_novo = converter_coluna_data(df_novo, coluna_data_novo)

            if coluna_data_base != coluna_data_novo:
                df_novo = df_novo.rename(columns={coluna_data_novo: coluna_data_base})

            coluna_data = coluna_data_base

            (
                df_final,
                adicionados,
                total_final,
                total_inicial,
                houve_substituicao,
            ) = self.atualizar_base(df_base, df_novo, coluna_data)

            return {
                "sucesso": True,
                "df_final": df_final,
                "adicionados": adicionados,
                "total_final": total_final,
                "total_inicial": total_inicial,
                "houve_substituicao": houve_substituicao,
                "nome_arquivo": self.nome_arquivo_final,
                "aba_arquivo_01": aba_novo,
                "aba_arquivo_02": aba_base,
            }

        except Exception as e:
            return {
                "sucesso": False,
                "erro": str(e),
            }


def processar_cvli(arquivo_01, arquivo_02):
    """
    Função pública do módulo para integração com o agregador
    todos_indicadores.
    """
    processador = ProcessadorCVLI()
    resultado = processador.processar(arquivo_01, arquivo_02)

    if not resultado["sucesso"]:
        raise ValueError(resultado["erro"])

    resumo = {
        "adicionados": resultado["adicionados"],
        "total_final": resultado["total_final"],
        "total_inicial": resultado["total_inicial"],
        "houve_substituicao": resultado["houve_substituicao"],
        "nome_arquivo": resultado["nome_arquivo"],
        "aba_arquivo_01": resultado["aba_arquivo_01"],
        "aba_arquivo_02": resultado["aba_arquivo_02"],
    }

    return resultado["df_final"], resumo


def _render_resumo_cvli(resultado: dict) -> None:
    """Renderiza o resumo do processamento com componentes nativos do Streamlit."""
    acao = (
        "Atualização com substituição de período"
        if resultado["houve_substituicao"]
        else "Complementação sem substituição"
    )

    st.markdown(
        """
        <div class="cvli-card">
            <div class="cvli-card-header">Resultado do processamento</div>
            <div class="cvli-card-desc">
                O processamento foi concluído com sucesso. Abaixo estão os principais indicadores da execução.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.success("Processo finalizado com sucesso.")
    st.caption(acao)

    col1, col2, col3 = st.columns(3)
    col4, col5 = st.columns(2)

    with col1:
        st.metric("Registros adicionados", resultado["adicionados"])

    with col2:
        st.metric("Total final", resultado["total_final"])

    with col3:
        st.metric("Total inicial", resultado["total_inicial"])

    with col4:
        st.info(f"**Aba arquivo 01:** {resultado['aba_arquivo_01']}")

    with col5:
        st.info(f"**Aba arquivo 02:** {resultado['aba_arquivo_02']}")


def interface_cvli() -> None:
    """Interface Streamlit para processamento CVLI."""
    st.markdown(
        """
        <style>
        .cvli-card {
            border-radius: 0.85rem;
            padding: 1rem 1.1rem;
            margin-bottom: 0.75rem;
            border: 1px solid rgba(148, 163, 184, 0.30);
            background: #020617;
            background: linear-gradient(180deg, rgba(2, 44, 34, 0.95), rgba(2, 26, 23, 0.95));
        }
        .cvli-card-header {
            font-weight: 700;
            font-size: 0.98rem;
            margin-bottom: 0.35rem;
            font-size: 1rem;
            margin-bottom: 0.45rem;
            color: rgba(248, 250, 252, 0.98);
        }
        .cvli-card-desc {
            font-size: 0.84rem;
            color: rgba(226, 232, 240, 0.82);
            margin-bottom: 0.2rem;
            color: rgba(226, 232, 240, 0.86);
            margin-bottom: 0.15rem;
            line-height: 1.6;
        }
        .cvli-list {
            margin: 0.7rem 0 0 0;
            padding-left: 1.2rem;
            color: rgba(226, 232, 240, 0.92);
        }
        .cvli-list li {
            margin-bottom: 0.35rem;
        }
        .cvli-file-card {
            border-radius: 0.75rem;
            padding: 0.75rem 0.85rem;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(148, 163, 184, 0.20);
            margin-top: 0.4rem;
            margin-bottom: 0.45rem;
        }
        .cvli-file-title {
            font-size: 0.8rem;
            font-weight: 700;
            color: rgba(248, 250, 252, 0.98);
            margin-bottom: 0.2rem;
        }
        .cvli-file-desc {
            font-size: 0.78rem;
            color: rgba(148, 163, 184, 0.95);
        }
        .element-container:has(#cvli-download-marker) + div button {
            background: linear-gradient(135deg, #ea580c, #f97316) !important;
            border-color: rgba(248, 250, 252, 0.15) !important;
            color: #fff7ed !important;
            font-weight: 700 !important;
        }
        .element-container:has(#cvli-download-marker) + div button:hover {
            background: linear-gradient(135deg, #c2410c, #ea580c) !important;
        }
        .element-container:has(#cvli-download-marker) + div button p {
            color: #fff7ed !important;
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## CVLI")
    st.caption(
        "Atualização da base de Crimes Violentos Letais Intencionais com padronização visual do QGP Online."
    )

    st.markdown(
        """
        <div class="cvli-card">
            <div class="cvli-card-header">Processamento de CVLI</div>
            <div class="cvli-card-desc">
                Envie primeiro o arquivo complementar de atualização e depois a base histórica consolidada
                para consolidar o indicador CVLI no padrão do QGP Online, com identificação automática da aba
                correta, alinhamento estrutural das colunas e substituição dos períodos já existentes quando necessário.
            </div>
            <ul class="cvli-list">
                <li>Seleção automática da aba correta do arquivo complementar.</li>
                <li>Padronização e alinhamento das colunas com a base histórica.</li>
                <li>Conversão e validação da coluna de data para processamento seguro.</li>
                <li>Substituição automática de meses já existentes na base quando houver sobreposição.</li>
                <li>Geração do arquivo final consolidado para download.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="cvli-card">
            <div class="cvli-card-header">Entrada de arquivos</div>
            <div class="cvli-card-desc">
                Envie o arquivo complementar no Arquivo 01 e a base atual consolidada no Arquivo 02.
                O sistema irá identificar a aba correta, alinhar as colunas e substituir automaticamente
                os meses já existentes quando necessário.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="cvli-file-card">
                <div class="cvli-file-title">Arquivo 01</div>
                <div class="cvli-file-desc">Arquivo complementar para atualização do indicador.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arquivo01 = st.file_uploader(
            "Arquivo 01 - Dados complementares",
            type=["xlsx", "xls"],
            key="cvli_arquivo01",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown(
            """
            <div class="cvli-file-card">
                <div class="cvli-file-title">Arquivo 02</div>
                <div class="cvli-file-desc">Base consolidada atual do CVLI.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        arquivo02 = st.file_uploader(
            "Arquivo 02 - Base de dados CVLI",
            type=["xlsx", "xls"],
            key="cvli_arquivo02",
            label_visibility="collapsed",
        )

    pode_processar = arquivo01 is not None and arquivo02 is not None
    processar = st.button(
        "Processar CVLI",
        key="processar_cvli",
        type="primary",
        use_container_width=True,
        disabled=not pode_processar,
    )

    if not processar:
        return

    if not arquivo01:
        st.error("Envie o Arquivo 01 (Dados complementares).")
        return

    if not arquivo02:
        st.error("Envie o Arquivo 02 (Base de dados).")
        return

    with st.spinner("Processando dados CVLI..."):
        processador = ProcessadorCVLI()
        resultado = processador.processar(arquivo01, arquivo02)

    if not resultado["sucesso"]:
        st.error(f"Erro no processamento: {resultado['erro']}")
        return

    _render_resumo_cvli(resultado)

    output = gerar_arquivo_excel(resultado["df_final"], sheet_name="CVLI")

    st.markdown(
        """
        <div class="cvli-card">
            <div class="cvli-card-header">Download</div>
            <div class="cvli-card-desc">
                Baixe o arquivo final processado no padrão oficial do módulo CVLI.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<span id="cvli-download-marker"></span>', unsafe_allow_html=True)
    st.download_button(
        label="Baixar arquivo processado",
        data=output,
        file_name=resultado["nome_arquivo"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_cvli",
        use_container_width=True,
    )
