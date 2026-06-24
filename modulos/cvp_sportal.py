"""
Modulo CVP (SPORTAL) - Crimes Violentos contra o Patrimonio
Processamento e atualizacao de dados CVP do sistema SPORTAL para QGP Online
"""

import io
import pandas as pd
import streamlit as st
from datetime import datetime
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
    gerar_arquivo_excel,
    nome_arquivo_padrao,
)

NOME_ARQUIVO_FINAL = nome_arquivo_padrao(2, "CVP-SPORTAL")


def interface_cvp_sportal():
    """Interface Streamlit para CVP SPORTAL."""
    st.markdown("## Atualizar CVP (SPORTAL)")
    st.info("""
    **Instrucoes:**
    - **Arquivo 01:** Base CVP existente (dados historicos)
    - **Arquivo 02:** Complemento SPORTAL (novos registros)

    O sistema ira:
    - Verificar coordenadas validas
    - Converter coordenadas UTM (SIRGAS2000) para WGS84
    - Adicionar apenas registros posteriores a ultima DataHora da base
    - Gerar arquivo final consolidado para download
    """)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Arquivo 01 - Base CVP")
        arquivo_base = st.file_uploader(
            "Selecione o arquivo base",
            type=["xlsx", "xls"],
            key="cvp_sportal_base"
        )

    with col2:
        st.markdown("#### Arquivo 02 - Complemento SPORTAL")
        arquivo_novo = st.file_uploader(
            "Selecione o arquivo complemento",
            type=["xlsx", "xls"],
            key="cvp_sportal_novo"
        )

    if not arquivo_base or not arquivo_novo:
        st.warning("Por favor, faca upload dos dois arquivos para continuar.")
        return

    if st.button("Processar Arquivos", type="primary", use_container_width=True):
        try:
            with st.spinner("Processando arquivos..."):

                # Leitura
                df_base = pd.read_excel(arquivo_base)
                df_novo = pd.read_excel(arquivo_novo)

                # Normalizacao de colunas
                df_base = normalizar_colunas(df_base)
                df_novo = normalizar_colunas(df_novo)

                # Localizar colunas de data e hora
                col_data_base = encontrar_coluna_data(df_base)
                col_data_novo = encontrar_coluna_data(df_novo)
                col_hora_base = encontrar_coluna_hora(df_base)
                col_hora_novo = encontrar_coluna_hora(df_novo)

                # Padronizar nomes das colunas de data/hora
                if col_data_base != col_data_novo:
                    df_novo = df_novo.rename(columns={col_data_novo: col_data_base})
                if col_hora_base != col_hora_novo:
                    df_novo = df_novo.rename(columns={col_hora_novo: col_hora_base})

                col_data = col_data_base
                col_hora = col_hora_base

                # Localizar colunas de coordenadas
                col_lat_base = encontrar_coluna_por_nomes(df_base, ["lat", "latitude"])
                col_lon_base = encontrar_coluna_por_nomes(df_base, ["long", "longitude", "lon"])
                col_lat_novo = encontrar_coluna_por_nomes(df_novo, ["latitude"])
                col_lon_novo = encontrar_coluna_por_nomes(df_novo, ["longitude"])

                # Renomear equivalencias
                df_novo = renomear_colunas_equivalentes(df_base, df_novo)

                total_lido_arquivo_02 = len(df_novo)

                # Remover coordenadas invalidas
                df_novo = excluir_coordenadas_invalidas(df_novo, col_lat_novo, col_lon_novo)
                removidos_invalidos = total_lido_arquivo_02 - len(df_novo)

                if df_novo.empty:
                    st.error("Apos excluir coordenadas invalidas, o Arquivo 02 ficou sem registros validos.")
                    return

                # Criar coluna DataHora
                df_base = criar_coluna_datahora(df_base, col_data, col_hora)
                df_novo = criar_coluna_datahora(df_novo, col_data, col_hora)

                ultima_datahora_base = obter_ultima_datahora(df_base, "datahora")

                # Filtrar por DataHora
                total_antes_filtro_tempo = len(df_novo)
                df_novo_filtrado = filtrar_apenas_registros_posteriores(
                    df_novo, "datahora", ultima_datahora_base
                )
                removidos_por_datahora = total_antes_filtro_tempo - len(df_novo_filtrado)

                # Preparar base sem coluna auxiliar
                base_sem_aux = df_base.drop(columns=["datahora"])

                if ultima_datahora_base is None:
                    df_novo_util = df_novo.copy()
                    situacao = "Base anterior sem DataHora valida - Arquivo 02 incluido integralmente."
                elif df_novo_filtrado.empty:
                    df_novo_util = df_novo_filtrado.copy()
                    situacao = "Nenhum registro novo encontrado apos a ultima DataHora da base."
                else:
                    df_novo_util = df_novo_filtrado.copy()
                    situacao = "Somente registros posteriores a ultima DataHora foram adicionados."

                adicionados = len(df_novo_util)

                # Reprojetar coordenadas UTM -> WGS84
                if not df_novo_util.empty:
                    df_novo_util = converter_coordenadas_para_wgs84_auto(
                        df_novo_util,
                        col_y_or_lat=col_lat_novo,
                        col_x_or_lon=col_lon_novo,
                        col_lat_destino=col_lat_base,
                        col_lon_destino=col_lon_base
                    )
                    df_novo_util = alinhar_colunas_com_base(base_sem_aux, df_novo_util)
                    df_final = pd.concat([base_sem_aux, df_novo_util], ignore_index=True)
                else:
                    df_final = base_sem_aux.copy()

                # Ordenar por DataHora
                df_final = criar_coluna_datahora(df_final, col_data, col_hora)
                df_final = df_final.sort_values(
                    by="datahora", ascending=True, na_position="last"
                ).reset_index(drop=True)
                df_final = df_final.drop(columns=["datahora"])

                total_final = len(df_final)

            # Exibir resultados
            st.success("Processamento Finalizado com Sucesso!")
            st.markdown("### Resumo")

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Registros Adicionados", adicionados)
            with col_b:
                st.metric("Total Final", total_final)
            with col_c:
                ultima_ref = (
                    ultima_datahora_base.strftime("%d/%m/%Y %H:%M:%S")
                    if ultima_datahora_base is not None
                    else "N/A"
                )
                st.metric("Ultima DataHora Base", ultima_ref)

            st.info(f"**Situacao:** {situacao}")

            if removidos_invalidos > 0:
                st.warning(f"Registros excluidos por coordenadas invalidas: {removidos_invalidos}")
            if removidos_por_datahora > 0:
                st.warning(f"Registros excluidos por serem anteriores/iguais a ultima DataHora: {removidos_por_datahora}")

            # Download
            excel_data = gerar_arquivo_excel(df_final, sheet_name="CVP-SPORTAL")
            st.download_button(
                label="Baixar Arquivo Final",
                data=excel_data,
                file_name=NOME_ARQUIVO_FINAL,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Erro durante o processamento: {str(e)}")
            import traceback
            with st.expander("Detalhes do erro"):
                st.code(traceback.format_exc())
