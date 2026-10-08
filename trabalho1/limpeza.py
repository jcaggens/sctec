import pandas as pd
from pathlib import Path

# fator da regra do IQR (1.5 é o valor convencional)
FATOR_IQR = 1.5


#importar dataset para df (caminho a partir da pasta do script, funciona de qualquer lugar)
pasta = Path(__file__).parent
caminho = pasta / "data" / "tabela_vendas_ZePequeno_corrigido.xlsx"
df = pd.read_excel(caminho)

#print(df.head)

# modificar tipo para data
df['Data'] = pd.to_datetime(df['Data'])
#print(df.info())

#extrair componentes da data
df["Ano"] = df["Data"].dt.year
df["Mês"] = df["Data"].dt.month
df["Dia"] = df["Data"].dt.day
df["DiaSemana"] = df["Data"].dt.day_name()

#corrigindo texto
for coluna in ["Região", "Canal", "Produto"]:
    df[coluna] = df[coluna].str.strip().str.lower()

#regiao e cidades
# cada cidade pertence a uma macrorregião
regiao_da_cidade = {
    "curitiba": "sul",
    "joinville": "sul",
    "blumenau": "sul",
    "florianópolis": "sul",
    "são paulo": "sudeste",
    "rio de janeiro": "sudeste",
}
# a cidade fica vazia quando a linha já veio só com a macrorregião
df["Cidade"] = df["Região"].where(df["Região"].isin(regiao_da_cidade))
df["Região"] = df["Região"].map(regiao_da_cidade).fillna(df["Região"])

#outliers
# 1) separar o que tem valor claramente inválido (antes de calcular os quartis,
#    senão eles esticariam os limites)
codigo_erro = df["Valor_Venda"].isna() | (df["Valor_Venda"] == 999999)
cancelado = df["Valor_Venda"] == 0

vendas_canceladas = df[cancelado]
vendas_erro = df[codigo_erro].assign(Motivo="999999 ou vazio")
restante = df[~codigo_erro & ~cancelado]

# 2) limites do IQR por produto
limites = restante.groupby("Produto")["Valor_Venda"].agg(
    Q1=lambda s: s.quantile(0.25),
    Q3=lambda s: s.quantile(0.75),
)
limites["IQR"] = limites["Q3"] - limites["Q1"]
limites["Limite_Inferior"] = limites["Q1"] - FATOR_IQR * limites["IQR"]
limites["Limite_Superior"] = limites["Q3"] + FATOR_IQR * limites["IQR"]

# cada venda recebe os limites do seu próprio produto
restante = restante.join(limites[["Limite_Inferior", "Limite_Superior"]], on="Produto")
acima = restante["Valor_Venda"] > restante["Limite_Superior"]
abaixo = restante["Valor_Venda"] < restante["Limite_Inferior"]

colunas = df.columns
vendas_acima = restante[acima][colunas].assign(Motivo="acima do limite")
vendas_abaixo = restante[abaixo][colunas].assign(Motivo="abaixo do limite")
vendas_limpas = restante[~acima & ~abaixo][colunas]
vendas_suspeitas = pd.concat([vendas_erro, vendas_acima, vendas_abaixo])

# salvar (utf-8-sig para o Excel abrir com acentos corretos)
vendas_limpas.to_csv(pasta / "data" / "vendas_limpas.csv", index=False, encoding="utf-8-sig")
vendas_suspeitas.to_csv(pasta / "data" / "vendas_suspeitas.csv", index=False, encoding="utf-8-sig")
vendas_canceladas.to_csv(pasta / "data" / "vendas_canceladas.csv", index=False, encoding="utf-8-sig")
limites.to_csv(pasta / "data" / "limites_iqr.csv", encoding="utf-8-sig")

# resumo para conferir que nenhuma linha se perdeu
print(f"Total de linhas: {len(df)}")
print(f"Limpas: {len(vendas_limpas)}")
print(f"Suspeitas: {len(vendas_suspeitas)}")
print(vendas_suspeitas["Motivo"].value_counts().to_string())
print(f"Canceladas/devoluções (0): {len(vendas_canceladas)}")
print("Limites do IQR por produto:")
print(limites.round(2).to_string())


#analises (serão movidas para analise.py)
#Vendas por mês

#Vendas por dia da semana

#Ultimos 30 dias

#Ultimos 90 dias

#Vendas por Regiao

#vendas por canal

#ticket médio

#comparaçao entre os produtos
