"""
Módulo Perturbação do Sossego Alheio
Processamento e atualização de dados de perturbação do sossego para QGP Online
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import io


class ProcessadorPerturbacaoSossego:
    """Classe para processar dados de Perturbação do Sossego"""
    
    def __init__(self):
        self.nome_arquivo_final = f"4-PERTURBACAO-SOSSEGO-{datetime.now().year}-QGP.xlsx"
    
    @staticmethod
    def normalizar_colunas(df):
        """Normaliza os nomes das colunas removendo espaços"""
        df.columns = [str(c).strip() for c in df.columns]
        return df
    
    @staticmethod
    def encontrar_coluna_data(df):
        """Encontra a coluna de data no DataFrame"""
        exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
        if exatos:
            return exatos[0]
        
        aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
        if aproximados:
            return aproximados[0]
        
        raise ValueError("Não foi encontrada a coluna 'Data'. Verifique se existe uma coluna chamada Data.")
    
    @staticmethod
    def converter_coluna_data(df, coluna_data):
        """Converte a coluna de data para datetime"""
        df[coluna_data] = pd.to_datetime(df[coluna_data], errors='coerce', dayfirst=True)
        return df
    
    @staticmethod
    def renomear_colunas_equivalentes(df_base, df_novo):
        """Renomeia colunas equivalentes do arquivo novo para coincidir com a base"""
        mapa_equivalencias = {
            "AIS": ["AIS Nova", "AIS_Nova", "AISNOVA", "ais nova", "ais_nova"]
        }
        
        colunas_base_map = {str(c).strip().lower(): c for c in df_base.columns}
        colunas_novo_map = {str(c).strip().lower(): c for c in df_novo.columns}
        
        renomeacoes = {}
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
    
    @staticmethod
    def filtrar_colunas_do_arquivo01(df_base, df_novo):
        """Filtra e adiciona colunas faltantes no arquivo novo"""
        colunas_base = list(df_base.columns)
        faltantes = [col for col in colunas_base if col not in df_novo.columns]
        
        for col in faltantes:
            df_novo[col] = pd.NA
        
        df_novo = df_novo[colunas_base]
        return df_novo
    
    @staticmethod
    def obter_meses_anos(df, coluna_data):
        """Obtém pares de (ano, mês) presentes no DataFrame"""
        base_valida = df[df[coluna_data].notna()].copy()
        pares = set(zip(base_valida[coluna_data].dt.year, base_valida[coluna_data].dt.month))
        return pares
    
    def atualizar_base(self, df_base, df_novo, coluna_data):
        """Atualiza a base removendo dados antigos e adicionando novos"""
        total_inicial = len(df_base)
        
        df_novo = self.renomear_colunas_equivalentes(df_base, df_novo)
        df_novo = self.filtrar_colunas_do_arquivo01(df_base, df_novo)
        
        meses_anos_novo = self.obter_meses_anos(df_novo, coluna_data)
        
        if not meses_anos_novo:
            raise ValueError("O Arquivo 02 não possui datas válidas na coluna de data.")
        
        mask_remover = df_base[coluna_data].notna() & df_base[coluna_data].apply(
            lambda x: (x.year, x.month) in meses_anos_novo
        )
        
        houve_substituicao = mask_remover.any()
        
        if houve_substituicao:
            df_base_atualizada = df_base.loc[~mask_remover].copy()
        else:
            df_base_atualizada = df_base.copy()
        
        total_antes_add = len(df_base_atualizada)
        df_final = pd.concat([df_base_atualizada, df_novo], ignore_index=True)
        df_final = df_final.sort_values(by=coluna_data, ascending=True, na_position='last').reset_index(drop=True)
        
        adicionados = len(df_final) - total_antes_add
        total_final = len(df_final)
        
        return df_final, adicionados, total_final, total_inicial, houve_substituicao
    
    def processar(self, arquivo01, arquivo02):
        """Processa os arquivos de Perturbação do Sossego"""
        try:
            df_base = pd.read_excel(arquivo01)
            df_novo = pd.read_excel(arquivo02)
            
            df_base = self.normalizar_colunas(df_base)
            df_novo = self.normalizar_colunas(df_novo)
            
            coluna_data_base = self.encontrar_coluna_data(df_base)
            coluna_data_novo = self.encontrar_coluna_data(df_novo)
            
            df_base = self.converter_coluna_data(df_base, coluna_data_base)
            df_novo = self.converter_coluna_data(df_novo, coluna_data_novo)
            
            if coluna_data_base != coluna_data_novo:
                df_novo = df_novo.rename(columns={coluna_data_novo: coluna_data_base})
            
            coluna_data = coluna_data_base
            
            df_final, adicionados, total_final, total_inicial, houve_substituicao = self.atualizar_base(
                df_base, df_novo, coluna_data
            )
            
            return {
                'sucesso': True,
                'df_final': df_final,
                'adicionados': adicionados,
                'total_final': total_final,
                'total_inicial': total_inicial,
                'houve_substituicao': houve_substituicao,
                'nome_arquivo': self.nome_arquivo_final
            }
            
        except Exception as e:
            return {
                'sucesso': False,
                'erro': str(e)
            }


def interface_perturbacao_sossego():
    """Interface Streamlit para processamento de Perturbação do Sossego"""
    st.markdown("### Processamento Perturbação do Sossego")
    st.markdown("Atualize a base de Perturbação do Sossego Alheio")
    
    col1, col2 = st.columns(2)
    
    with col1:
        arquivo01 = st.file_uploader(
            "📁 Arquivo 01 - Base de dados",
            type=["xlsx", "xls"],
            key="perturbacao_arquivo01"
        )
    
    with col2:
        arquivo02 = st.file_uploader(
            "📁 Arquivo 02 - Dados complementares",
            type=["xlsx", "xls"],
            key="perturbacao_arquivo02"
        )
    
    salvar_drive = st.checkbox("💾 Salvar no Google Drive", key="perturbacao_drive")
    
    if st.button("▶️ Processar Perturbação do Sossego", key="processar_perturbacao"):
        if not arquivo01:
            st.error("⚠️ Envie o Arquivo 01 (Base de dados)")
            return
        
        if not arquivo02:
            st.error("⚠️ Envie o Arquivo 02 (Dados complementares)")
            return
        
        with st.spinner("Processando dados de Perturbação do Sossego..."):
            processador = ProcessadorPerturbacaoSossego()
            resultado = processador.processar(arquivo01, arquivo02)
        
        if resultado['sucesso']:
            acao = "atualizado" if resultado['houve_substituicao'] else "complementado"
            
            st.success("✅ Processo Finalizado!")
            st.info(f"📊 **{resultado['adicionados']}** registros novos adicionados")
            st.info(f"📈 Total de **{resultado['total_final']}** registros na base")
            st.info(f"🔄 Arquivo {acao} com sucesso")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                resultado['df_final'].to_excel(writer, index=False, sheet_name='Perturbacao_Sossego')
            
            output.seek(0)
            
            st.download_button(
                label="💾 Download do arquivo processado",
                data=output,
                file_name=resultado['nome_arquivo'],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_perturbacao"
            )
            
            if salvar_drive:
                st.warning("🔄 Integração com Google Drive em desenvolvimento")
        else:
            st.error(f"❌ Erro no processamento: {resultado['erro']}")
