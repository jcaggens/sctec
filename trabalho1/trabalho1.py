import pandas as pd

caminho = "./data/tabela_vendas_ZePequeno_corrigido.xlsx"
df = pd.read_excel(caminho)
print(df.head)