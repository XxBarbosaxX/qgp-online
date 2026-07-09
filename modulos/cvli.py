"""
Módulo CVLI - Crimes Violentos Letais Intencionais
Processamento e atualização de dados CVLI para QGP Online
"""

from __future__ import annotations

import io

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
        """Seleciona a aba correta do Arquivo 02 conforme chaveamento oficial."""
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
            raise ValueError("O Arquivo 02 não possui datas válidas na coluna de data.")

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
        """Processa os arquivos CVLI."""
        try:
            arquivo01.seek(0)
            arquivo02.seek(0)

            xls_base = pd.ExcelFile(arquivo01)
            xls_novo = pd.ExcelFile(arquivo02)

            aba_base = xls_base.sheet_names[0]
            aba_novo = self._selecionar_aba_arquivo_02(xls_novo.sheet_names)

            df_base = pd.read_excel(xls_base, sheet_name=aba_base)
            df_novo = pd.read_excel(xls_novo, sheet_name=aba_novo)

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
                "aba_arquivo_01": aba_base,
                "aba_arquivo_02": aba_novo,
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


def interface_cvli() -> None:
    """Interface Streamlit para processamento CVLI."""
    st.markdown("### Processamento CVLI")
    st.markdown("Atualize a base de Crimes Violentos Letais Intencionais")

    col1, col2 = st.columns(2)

    with col1:
        arquivo01 = st.file_uploader(
            "📁 Arquivo 01 - Base de dados CVLI",
            type=["xlsx", "xls"],
            key="cvli_arquivo01",
        )

    with col2:
        arquivo02 = st.file_uploader(
            "📁 Arquivo 02 - Dados complementares",
            type=["xlsx", "xls"],
            key="cvli_arquivo02",
        )

    salvar_drive = st.checkbox("💾 Salvar no Google Drive", key="cvli_drive")

    if st.button("▶️ Processar CVLI", key="processar_cvli"):
        if not arquivo01:
            st.error("⚠️ Envie o Arquivo 01 (Base de dados)")
            return

        if not arquivo02:
            st.error("⚠️ Envie o Arquivo 02 (Dados complementares)")
            return

        with st.spinner("Processando dados CVLI..."):
            processador = ProcessadorCVLI()
            resultado = processador.processar(arquivo01, arquivo02)

        if resultado["sucesso"]:
            acao = "atualizado" if resultado["houve_substituicao"] else "complementado"

            st.success("✅ Processo Finalizado!")
            st.info(f"📊 **{resultado['adicionados']}** CVLIs novos adicionados")
            st.info(f"📈 Total de **{resultado['total_final']}** CVLIs na base")
            st.info(f"🔄 Arquivo {acao} com sucesso")
            st.info(
                f"📑 Aba usada no Arquivo 01: {resultado['aba_arquivo_01']} | "
                f"Aba usada no Arquivo 02: {resultado['aba_arquivo_02']}"
            )

            output = gerar_arquivo_excel(resultado["df_final"], sheet_name="CVLI")

            st.download_button(
                label="💾 Download do arquivo processado",
                data=output,
                file_name=resultado["nome_arquivo"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_cvli",
            )

            if salvar_drive:
                st.warning("🔄 Integração com Google Drive em desenvolvimento")
        else:
            st.error(f"❌ Erro no processamento: {resultado['erro']}")
