"""Módulo Acidente de Trânsito"""
import pandas as pd
import streamlit as st
from datetime import datetime
import io

class ProcessadorAcidenteTransito:
    def __init__(self):
        self.nome_arquivo_final = f"6-ACIDENTE-TRANSITO-{datetime.now().year}-QGP.xlsx"
    
    @staticmethod
    def normalizar_colunas(df):
        df.columns = [str(c).strip() for c in df.columns]
        return df
    
    @staticmethod
    def encontrar_coluna_data(df):
        exatos = [c for c in df.columns if str(c).strip().lower() == "data"]
        if exatos:
            return exatos[0]
        aproximados = [c for c in df.columns if "data" in str(c).strip().lower()]
        if aproximados:
            return aproximados[0]
        return None
    
    def processar_dados(self, df, data_inicio, data_fim):
        try:
            df = self.normalizar_colunas(df)
            coluna_data = self.encontrar_coluna_data(df)
            if not coluna_data:
                st.error("❌ Não foi possível encontrar a coluna de data.")
                return None
            df[coluna_data] = pd.to_datetime(df[coluna_data], errors='coerce')
            df = df.dropna(subset=[coluna_data])
            mascara = (df[coluna_data] >= pd.to_datetime(data_inicio)) & (df[coluna_data] <= pd.to_datetime(data_fim))
            df_filtrado = df[mascara].copy()
            if df_filtrado.empty:
                st.warning("⚠️ Nenhum registro encontrado.")
                return None
            return df_filtrado
        except Exception as e:
            st.error(f"❌ Erro: {str(e)}")
            return None
    
    def gerar_arquivo_excel(self, df):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='ACIDENTE_TRANSITO')
        return output.getvalue()

def interface_acidente_transito():
    st.title("🚗💥 Acidente de Trânsito")
    st.markdown("### 🔍 Processamento de dados de Acidentes")
    st.divider()
    processador = ProcessadorAcidenteTransito()
    st.subheader("📁 Upload do Arquivo")
    arquivo = st.file_uploader("Selecione o arquivo (Excel/CSV)", type=['xlsx', 'xls', 'csv'])
    if arquivo:
        try:
            df = pd.read_csv(arquivo) if arquivo.name.endswith('.csv') else pd.read_excel(arquivo)
            st.success(f"✅ Arquivo carregado! ({len(df)} registros)")
            col1, col2 = st.columns(2)
            with col1:
                data_inicio = st.date_input("📅 Data Início", value=datetime(datetime.now().year, 1, 1))
            with col2:
                data_fim = st.date_input("📅 Data Fim", value=datetime.now())
            if st.button("🔄 Processar Dados", type="primary", use_container_width=True):
                with st.spinner("Processando..."):
                    df_proc = processador.processar_dados(df, data_inicio, data_fim)
                    if df_proc is not None:
                        st.success(f"✅ Processado! {len(df_proc)} registros.")
                        st.dataframe(df_proc.head(10), use_container_width=True)
                        arquivo_excel = processador.gerar_arquivo_excel(df_proc)
                        st.download_button("📥 Download Excel", arquivo_excel, processador.nome_arquivo_final, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        except Exception as e:
            st.error(f"❌ Erro: {str(e)}")
    else:
        st.info("👆 Faça upload de um arquivo.")
