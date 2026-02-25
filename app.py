import streamlit as st
import pandas as pd
from processador import processar_planilha_indices, extrair_inss, extrair_bradesco

st.set_page_config(page_title="Cálculo Judicial INSS/Bancos", page_icon="⚖️", layout="wide")

st.title("⚖️ Calculadora Judicial - INSS e Bancos")
st.write("Busque múltiplos termos, separe em planilhas e identifique Créditos e Débitos.")

st.write("### Selecione o tipo de documento:")
tipo_documento = st.radio("Tipo de documento", ["Extrato INSS", "Extrato Bancário (Bradesco)"], horizontal=True, label_visibility="collapsed")
st.write("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Configuração da Busca")
    st.info("💡 Separe os termos usando vírgula. Ex: **CARTAO, EMPRESTIMO, INSS**")
    
    texto_padrao = "CARTAO, EMPRESTIMO" if tipo_documento == "Extrato INSS" else "ASPECIR, SEBRASEG"
    termo_busca = st.text_input("Termos para buscar:", texto_padrao)
        
    arquivo_pdf = st.file_uploader("📄 Faça upload do Extrato (PDF)", type=["pdf"])

with col2:
    st.subheader("2. Tabela de Correção")
    arquivo_indices = st.file_uploader("📊 Faça upload dos Coeficientes (Excel/CSV)", type=["xlsx", "xls", "csv"])

if arquivo_pdf and arquivo_indices and termo_busca.strip() != "":
    try:
        lista_termos = [t.strip().upper() for t in termo_busca.split(',') if t.strip() != ""]
        dicionario_coeficientes = processar_planilha_indices(arquivo_indices)
        
        st.success(f"Calculando valores para os termos: **{', '.join(lista_termos)}**...")
        
        if tipo_documento == "Extrato INSS":
            resultados = extrair_inss(arquivo_pdf, lista_termos, dicionario_coeficientes)
        else:
            resultados = extrair_bradesco(arquivo_pdf, lista_termos, dicionario_coeficientes)
            
        encontrou_algum = False
        
        # Função para pintar de verde claro os estornos na tela
        def destacar_creditos(linha):
            if linha['Tipo'] == 'Crédito':
                return ['background-color: #d1e7dd; color: #0f5132'] * len(linha)
            return [''] * len(linha)
        
        for termo, dados in resultados.items():
            if len(dados) > 0:
                encontrou_algum = True
                st.write("---")
                st.write(f"### 📋 Resultados para: `{termo}` ({len(dados)} encontrados)")
                
                df_final = pd.DataFrame(dados)
                
                # Exibe a tabela na tela com o estilo aplicado
                st.dataframe(df_final.style.apply(destacar_creditos, axis=1).format({
                    "Valor Original": "R$ {:,.2f}",
                    "Valor da Correção": "R$ {:,.2f}",
                    "Valor Corrigido": "R$ {:,.2f}",
                    "Valor Corrigido em Dobro": "R$ {:,.2f}",
                    "Coeficiente": "{:.7f}"
                }))
                
                csv = df_final.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                
                st.download_button(
                    label=f"📥 Baixar Planilha - {termo}",
                    data=csv,
                    file_name=f"calculo_{termo.replace(' ', '_')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"btn_dw_{termo}" 
                )
                
        if not encontrou_algum:
            st.warning(f"Nenhum resultado encontrado para os termos procurados.")
            
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")

elif (arquivo_pdf or arquivo_indices) and not (arquivo_pdf and arquivo_indices):
    st.info("⚠️ Aguardando o upload dos dois arquivos (PDF e Planilha) para iniciar o cruzamento.")