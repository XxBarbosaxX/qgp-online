"""
Módulo Deslocamento Forçado
Processamento e atualização de dados de Deslocamento Forçado para QGP Online
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import io


class ProcessadorDeslocamentoForcado:
    """Classe para processar dados de Deslocamento Forçado"""
    
    def __init__(self):
        self.nome_arquivo_final = f"2-DESLOCAMENTO-FORCADO-{datetime.now().year}-QGP.xlsx"
    
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
        return None
    
    def processar_dados(self, df, data_inicio, data_fim):
        """Processa os dados de Deslocamento Forçado"""
        try:
            df = self.normalizar_colunas(df)
            
            coluna_data = self.encontrar_coluna_data(df)
            if not coluna_data:
                st.error("❌ Não foi possível encontrar a coluna de data no arquivo.")
                return None
            
            df[coluna_data] = pd.to_datetime(df[coluna_data], errors='coerce')
            df = df.dropna(subset=[coluna_data])
            
            mascara = (df[coluna_data] >= pd.to_datetime(data_inicio)) & \
                     (df[coluna_data] <= pd.to_datetime(data_fim))
            df_filtrado = df[mascara].copy()
            
            if df_filtrado.empty:
                st.warning("⚠️ Nenhum registro encontrado no período selecionado.")
                return None
            
            return df_filtrado
            
        except Exception as e:
            st.error(f"❌ Erro ao processar dados: {str(e)}")
            return None
    
    def gerar_arquivo_excel(self, df):
        """Gera arquivo Excel em memória"""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='DESLOCAMENTO_FORCADO')
        return output.getvalue()


def interface_deslocamento_forcado():
    """Interface principal do módulo Deslocamento Forçado"""
    st.title("🚨 Deslocamento Forçado")
    st.markdown("### 🔍 Processamento de dados de Deslocamento Forçado")
    st.divider()
    
    processador = ProcessadorDeslocamentoForcado()
    
    st.subheader("📁 Upload do Arquivo")
    arquivo_uploaded = st.file_uploader(
        "Selecione o arquivo de Deslocamento Forçado (Excel/CSV)",
        type=['xlsx', 'xls', 'csv'],
        help="Faça upload do arquivo de Deslocamento Forçado"
    )
    
    if arquivo_uploaded:
        try:
            if arquivo_uploaded.name.endswith('.csv'):
                df = pd.read_csv(arquivo_uploaded)
            else:
                df = pd.read_excel(arquivo_uploaded)
            
            st.success(f"✅ Arquivo carregado com sucesso! ({len(df)} registros)")
            
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input(
                    "📅 Data Início",
                    value=datetime(datetime.now().year, 1, 1)
                )
            with col2:
                data_fim = st.date_input(
                    "📅 Data Fim",
                    value=datetime.now()
                )
            
            if st.button("🔄 Processar Dados", type="primary", use_container_width=True):
                with st.spinner("Processando dados..."):
                    df_processado = processador.processar_dados(df, data_inicio, data_fim)
                    
                    if df_processado is not None:
                        st.success(f"✅ Processamento concluído! {len(df_processado)} registros filtrados.")
                        
                        st.subheader("📊 Prévia dos Dados")
                        st.dataframe(df_processado.head(10), use_container_width=True)
                        
                        st.subheader("📈 Estatísticas")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total de Registros", len(df_processado))
                        with col2:
                            st.metric("Colunas", len(df_processado.columns))
                        with col3:
                            st.metric("Período", f"{(data_fim - data_inicio).days} dias")
                        
                        arquivo_excel = processador.gerar_arquivo_excel(df_processado)
                        st.download_button(
                            label="📥 Download Excel Processado",
                            data=arquivo_excel,
                            file_name=processador.nome_arquivo_final,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
        
        except Exception as e:
            st.error(f"❌ Erro ao carregar arquivo: {str(e)}")
    else:
        st.info("👆 Faça upload de um arquivo para começar o processamento.")
