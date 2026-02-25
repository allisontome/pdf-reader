import pdfplumber
import re
import pandas as pd

def processar_planilha_indices(arquivo_indices):
    if arquivo_indices.name.endswith('.csv'):
        df_indices = pd.read_csv(arquivo_indices, sep=None, engine='python')
    else:
        df_indices = pd.read_excel(arquivo_indices)
        
    col_data = df_indices.columns[0]
    col_coef = df_indices.columns[1]

    df_indices['Data_Formatada'] = pd.to_datetime(df_indices[col_data], format='%m/%d/%Y', errors='coerce')
    if df_indices['Data_Formatada'].isnull().all():
        df_indices['Data_Formatada'] = pd.to_datetime(df_indices[col_data], errors='coerce')

    df_indices['Competencia_Chave'] = df_indices['Data_Formatada'].dt.strftime('%m/%Y')

    def limpa_coeficiente(val):
        if isinstance(val, str):
            val = val.replace('.', '').replace(',', '.')
        return float(val)

    df_indices['Coef_Float'] = df_indices[col_coef].apply(limpa_coeficiente)
    return dict(zip(df_indices['Competencia_Chave'], df_indices['Coef_Float']))

def extrair_inss(arquivo_pdf, lista_termos, dicionario_coeficientes):
    resultados = {termo: [] for termo in lista_termos}
    
    with pdfplumber.open(arquivo_pdf) as pdf:
        competencia_atual = "Não identificada"
        esperando_data = False 

        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto: continue
            
            for linha in texto.split('\n'):
                linha_limpa = linha.strip()

                if "COMPET" in linha_limpa.upper() and "PER" in linha_limpa.upper():
                    esperando_data = True
                    continue 
                
                if esperando_data:
                    match_data = re.search(r'(?:^|\s)(\d{2}/\d{4})(?:\s|$)', linha_limpa)
                    if match_data:
                        competencia_atual = match_data.group(1)
                        esperando_data = False
                
                for termo in lista_termos:
                    if termo in linha_limpa.upper():
                        valores = re.findall(r'\d{1,3}(?:\.\d{3})*,\d{2}', linha_limpa)
                        valor_final_str = valores[-1] if valores else "0,00"
                        valor_float = float(valor_final_str.replace('.', '').replace(',', '.'))
                        coeficiente = dicionario_coeficientes.get(competencia_atual, 1.0)
                        
                        valor_corrigido = round(valor_float * coeficiente, 2)
                        
                        resultados[termo].append({
                            "Competência": competencia_atual,
                            "Tipo": "Débito",
                            "Origem": "INSS",
                            "Valor Original": valor_float,
                            "Valor da Correção": round(valor_corrigido - valor_float, 2),
                            "Valor Corrigido": valor_corrigido,
                            "Valor Corrigido em Dobro": round(valor_corrigido * 2, 2),
                            "Coeficiente": coeficiente,
                            "Observação": "-" # Coluna nova
                        })
                        break 
    return resultados

def extrair_bradesco(arquivo_pdf, lista_termos, dicionario_coeficientes):
    resultados = {termo: [] for termo in lista_termos}
    
    with pdfplumber.open(arquivo_pdf) as pdf:
        data_atual_banco = "Não identificada"
        saldo_anterior = None
        
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if not texto: continue
            
            linhas = texto.split('\n')
            
            for j, linha in enumerate(linhas):
                linha_limpa = linha.strip()

                match_data = re.search(r'(\d{2})/(\d{2})/(\d{4})', linha_limpa)
                if match_data:
                    data_atual_banco = f"{match_data.group(2)}/{match_data.group(3)}"
                
                valores_linha = re.findall(r'-?\d{1,3}(?:\.\d{3})*,\d{2}', linha_limpa)
                
                if len(valores_linha) >= 2:
                    valor_str_original = valores_linha[-2]
                    saldo_str_original = valores_linha[-1]
                    
                    valor_float = float(valor_str_original.replace('-', '').replace('.', '').replace(',', '.'))
                    saldo_atual = float(saldo_str_original.replace('-', '').replace('.', '').replace(',', '.'))
                    
                    tipo_transacao = "Desconhecido"
                    
                    if "-" in valor_str_original:
                        tipo_transacao = "Débito"
                    
                    if tipo_transacao == "Desconhecido" and saldo_anterior is not None:
                        diferenca = round(saldo_atual - saldo_anterior, 2)
                        if diferenca > 0:
                            tipo_transacao = "Crédito"
                        elif diferenca < 0:
                            tipo_transacao = "Débito"
                            
                    if tipo_transacao == "Desconhecido":
                        palavras_credito = ["RESGATE", "INSS", "REM", "TED", "DOC", "CREDITO", "SALARIO"]
                        bloco = linha_limpa.upper() + (" " + linhas[j-1].upper() if j>0 else "")
                        tipo_transacao = "Crédito" if any(p in bloco for p in palavras_credito) else "Débito"

                    saldo_anterior = saldo_atual
                    
                    historico_completo = linha_limpa
                    if j > 0:
                        historico_completo = linhas[j-1].strip() + " | " + historico_completo
                    if j < len(linhas) - 1:
                        prox_valores = re.findall(r'\d{1,3}(?:\.\d{3})*,\d{2}', linhas[j+1])
                        if len(prox_valores) < 2:
                            historico_completo += " | " + linhas[j+1].strip()
                            
                    for termo in lista_termos:
                        if termo in historico_completo.upper():
                            coeficiente = dicionario_coeficientes.get(data_atual_banco, 1.0)
                            
                            # --- A NOVA TRAVA DE CRÉDITO AQUI ---
                            if tipo_transacao == "Crédito":
                                valor_corrigido = 0.0
                                valor_da_correcao = 0.0
                                valor_em_dobro = 0.0
                                obs = "🚨 DEVOLUÇÃO (Ignorado no cálculo)"
                            else:
                                valor_corrigido = round(valor_float * coeficiente, 2)
                                valor_da_correcao = round(valor_corrigido - valor_float, 2)
                                valor_em_dobro = round(valor_corrigido * 2, 2)
                                obs = "-"
                            
                            resultados[termo].append({
                                "Competência": data_atual_banco,
                                "Tipo": tipo_transacao,
                                "Origem": historico_completo[:75] + "...",
                                "Valor Original": valor_float,
                                "Valor da Correção": valor_da_correcao,
                                "Valor Corrigido": valor_corrigido,
                                "Valor Corrigido em Dobro": valor_em_dobro,
                                "Coeficiente": coeficiente,
                                "Observação": obs # Coluna nova
                            })
                            break
                            
    return resultados