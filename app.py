import streamlit as st
import pdfplumber
import re
import pandas as pd

st.set_page_config(page_title="Cálculo Judicial INSS", page_icon="⚖️", layout="wide")

st.title("⚖️ Extrator e Calculadora Judicial - INSS")
st.write("Extrai descontos do PDF e cruza com a tabela de coeficientes de correção monetária.")

# --- 1. CONFIGURAÇÕES E UPLOADS ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Configuração da Busca")
    termo_busca = st.text_input("Termo para buscar no PDF (ex: CARTAO, CONSIGNACAO):", "CARTAO")
    arquivo_pdf = st.file_uploader("📄 Faça upload do Extrato (PDF)", type=["pdf"])

with col2:
    st.subheader("2. Tabela de Correção")
    st.info("A planilha deve ter a Data (MM/DD/AAAA) na Coluna A e o Coeficiente na Coluna B.")
    arquivo_indices = st.file_uploader("📊 Faça upload dos Coeficientes (Excel ou CSV)", type=["xlsx", "xls", "csv"])

# --- 2. PROCESSAMENTO ---
if arquivo_pdf and arquivo_indices and termo_busca.strip() != "":
    
    # Processando a Planilha de Índices
    try:
        if arquivo_indices.name.endswith('.csv'):
            df_indices = pd.read_csv(arquivo_indices, sep=None, engine='python')
        else:
            df_indices = pd.read_excel(arquivo_indices)
            
        col_data = df_indices.columns[0]
        col_coef = df_indices.columns[1]

        # Converte a coluna de data para o formato datetime
        df_indices['Data_Formatada'] = pd.to_datetime(df_indices[col_data], format='%m/%d/%Y', errors='coerce')
        if df_indices['Data_Formatada'].isnull().all():
            df_indices['Data_Formatada'] = pd.to_datetime(df_indices[col_data], errors='coerce')

        # Cria a chave MM/AAAA para bater igualzinho com o PDF
        df_indices['Competencia_Chave'] = df_indices['Data_Formatada'].dt.strftime('%m/%Y')

        # Limpa o coeficiente 
        def limpa_coeficiente(val):
            if isinstance(val, str):
                val = val.replace('.', '').replace(',', '.')
            return float(val)

        df_indices['Coef_Float'] = df_indices[col_coef].apply(limpa_coeficiente)
        
        # Cria um "dicionário" com as chaves
        dicionario_coeficientes = dict(zip(df_indices['Competencia_Chave'], df_indices['Coef_Float']))
        
    except Exception as e:
        st.error(f"Erro ao ler a planilha de índices: {e}")
        st.stop()


    # Processando o PDF
    st.success("Arquivos carregados! Calculando valores...")
    
    with pdfplumber.open(arquivo_pdf) as pdf:
        competencia_atual = "Não identificada"
        esperando_data = False 
        dados_encontrados = []

        for i, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text()
            if not texto: continue
            
            for linha in texto.split('\n'):
                linha_limpa = linha.strip()

                # Gatilho da Competência
                if "COMPET" in linha_limpa.upper() and "PER" in linha_limpa.upper():
                    esperando_data = True
                    continue 
                
                # Captura a Competência (MM/AAAA)
                if esperando_data:
                    match_data = re.search(r'(?:^|\s)(\d{2}/\d{4})(?:\s|$)', linha_limpa)
                    if match_data:
                        competencia_atual = match_data.group(1)
                        esperando_data = False
                
                # Busca o Desconto
                if termo_busca.upper() in linha_limpa.upper():
                    valores = re.findall(r'\d{1,3}(?:\.\d{3})*,\d{2}', linha_limpa)
                    valor_final_str = valores[-1] if valores else "0,00"
                    
                    # Converte o valor "114,41" para número matemático 114.41
                    valor_float = float(valor_final_str.replace('.', '').replace(',', '.'))
                    
                    # Busca o coeficiente
                    coeficiente = dicionario_coeficientes.get(competencia_atual, 1.0)
                    
                    # --- A MÁGICA DOS CÁLCULOS COM ARREDONDAMENTO (NOVO) ---
                    # Usa round(valor, 2) para garantir no máximo 2 casas decimais na planilha
                    valor_corrigido = round(valor_float * coeficiente, 2)
                    
                    # O "Juros" (Valor a mais da correção) é o valor corrigido menos o original
                    valor_da_correcao = round(valor_corrigido - valor_float, 2)
                    
                    # Valor em dobro
                    valor_corrigido_dobro = round(valor_corrigido * 2, 2)
                    
                    dados_encontrados.append({
                        "Competência": competencia_atual,
                        "Desconto Original": valor_float,
                        "Valor da Correção": valor_da_correcao,
                        "Valor Corrigido": valor_corrigido,
                        "Valor Corrigido em Dobro": valor_corrigido_dobro,
                        "Coeficiente Utilizado": coeficiente
                    })

        # --- EXIBE OS RESULTADOS E GERA A PLANILHA ---
        if len(dados_encontrados) > 0:
            st.write("---")
            st.write(f"### 📋 Resultado dos Cálculos ({len(dados_encontrados)} descontos encontrados)")
            
            df_final = pd.DataFrame(dados_encontrados)
            
            # Mostra uma prévia na tela formatada com "R$"
            st.dataframe(df_final.style.format({
                "Desconto Original": "R$ {:,.2f}",
                "Valor da Correção": "R$ {:,.2f}",
                "Valor Corrigido": "R$ {:,.2f}",
                "Valor Corrigido em Dobro": "R$ {:,.2f}",
                "Coeficiente Utilizado": "{:.7f}"
            }))
            
            # Exporta para Excel (csv) com a pontuação certa do Brasil
            csv = df_final.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            
            st.download_button(
                label="📥 Baixar Planilha de Cálculos (Excel)",
                data=csv,
                file_name="calculo_judicial_inss.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning(f"Nenhum desconto encontrado para o termo: **{termo_busca}**")
elif (arquivo_pdf or arquivo_indices) and not (arquivo_pdf and arquivo_indices):
    st.info("⚠️ Aguardando o upload dos dois arquivos (PDF e Planilha de Coeficientes) para iniciar o cruzamento.")