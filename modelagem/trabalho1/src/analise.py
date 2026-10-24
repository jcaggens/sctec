import pandas as pd
from pathlib import Path


# ---------- dados ----------
# o script fica em src/, a pasta data/ fica um nível acima
pasta = Path(__file__).parent.parent
df = pd.read_csv(pasta / "data" / "vendas_limpas.csv", parse_dates=["Data"])

# faixa em volta da média que ainda conta como venda "média" (10%)
TOLERANCIA = 0.10

# referências fixas: calculadas com TODAS as vendas limpas de cada produto,
# para que "venda boa" não mude conforme o filtro usado na análise
media_produto = df.groupby("Produto")["Valor_Venda"].mean()
quartis_produto = df.groupby("Produto")["Valor_Venda"].quantile([0.25, 0.5, 0.75]).unstack()
quartis_geral = df["Valor_Venda"].quantile([0.25, 0.5, 0.75])


# ---------- regras de negócio (lambdas) ----------
# boa / média / ruim: compara o valor com a média do produto ± tolerância
classificar_venda = lambda valor, media: (
    "boa" if valor > media * (1 + TOLERANCIA)
    else "ruim" if valor < media * (1 - TOLERANCIA)
    else "média"
)

# faixa de valor pelos quartis (q é uma linha com Q1, Q2 e Q3)
faixa_valor = lambda valor, q: (
    "baixa" if valor <= q[0.25]
    else "média-baixa" if valor <= q[0.5]
    else "média-alta" if valor <= q[0.75]
    else "alta"
)


# ---------- funções auxiliares ----------
def _filtrar(produto=None, regiao=None, canal=None):
    """Filtra as vendas. Parâmetro vazio (None) significa 'todos'."""
    dados = df
    if produto:
        dados = dados[dados["Produto"] == produto.lower()]
    if regiao:
        dados = dados[dados["Região"] == regiao.lower()]
    if canal:
        dados = dados[dados["Canal"] == canal.lower()]
    return dados.copy()


def _aplicar_regras(dados):
    """Cria as colunas das regras de negócio aplicando as lambdas em cada venda."""
    dados["Classificação"] = [
        classificar_venda(valor, media_produto[produto])
        for valor, produto in zip(dados["Valor_Venda"], dados["Produto"])
    ]
    dados["FaixaProduto"] = [
        faixa_valor(valor, quartis_produto.loc[produto])
        for valor, produto in zip(dados["Valor_Venda"], dados["Produto"])
    ]
    dados["FaixaGeral"] = [faixa_valor(valor, quartis_geral) for valor in dados["Valor_Venda"]]
    return dados


def _resumo_por(dados, coluna):
    """Total, quantidade, ticket médio e contagem boa/média/ruim para cada valor de `coluna`."""
    tabela = dados.groupby(coluna)["Valor_Venda"].agg(
        total="sum", vendas="count", ticket_medio="mean"
    ).round(2)
    contagem = pd.crosstab(dados[coluna], dados["Classificação"])
    contagem = contagem.reindex(columns=["boa", "média", "ruim"], fill_value=0)
    return tabela.join(contagem)


# ---------- análises ----------
def vendas_por_mes(ano, mes, produto=None, regiao=None, canal=None):
    """Resumo do mês/ano pedido, por produto."""
    dados = _aplicar_regras(_filtrar(produto, regiao, canal))
    dados = dados[(dados["Ano"] == ano) & (dados["Mês"] == mes)]
    return _resumo_por(dados, "Produto")


def vendas_por_regiao(produto=None, canal=None):
    """Resumo por região (sul, sudeste...)."""
    dados = _aplicar_regras(_filtrar(produto=produto, canal=canal))
    return _resumo_por(dados, "Região")


def vendas_por_canal(produto=None, regiao=None):
    """Resumo por canal (e-commerce, loja física)."""
    dados = _aplicar_regras(_filtrar(produto=produto, regiao=regiao))
    return _resumo_por(dados, "Canal")


def ticket_medio(produto=None, regiao=None, canal=None):
    """Ticket médio e mediana por produto."""
    dados = _filtrar(produto, regiao, canal)
    return dados.groupby("Produto")["Valor_Venda"].agg(
        ticket_medio="mean", mediana="median", vendas="count"
    ).round(2)


def distribuicao_faixas(produto=None, regiao=None, canal=None):
    """Quantidade de vendas em cada faixa de valor (quartis do produto e quartis gerais)."""
    dados = _aplicar_regras(_filtrar(produto, regiao, canal))
    ordem = ["baixa", "média-baixa", "média-alta", "alta"]
    return pd.DataFrame({
        "FaixaProduto": dados["FaixaProduto"].value_counts().reindex(ordem, fill_value=0),
        "FaixaGeral": dados["FaixaGeral"].value_counts().reindex(ordem, fill_value=0),
    })


def comparacao_produtos(meses=12, regiao=None, canal=None, ate=None, somente_meses_com_dados=False):
    """Total vendido por mês de cada produto nos últimos `meses` meses.

    `ate` é a data final da janela. Se não for informada, usa a data mais
    recente dos dados.

    Por padrão a janela é de calendário: meses sem nenhuma venda aparecem
    como NaN. Com `somente_meses_com_dados=True`, devolve os últimos `meses`
    meses que têm alguma venda, sem mostrar os meses vazios no meio.
    """
    dados = _filtrar(regiao=regiao, canal=canal)
    ate = pd.Timestamp(ate) if ate is not None else df["Data"].max()
    dados = dados[dados["Data"] <= ate]

    if somente_meses_com_dados:
        meses_com_venda = dados["Data"].dt.to_period("M").drop_duplicates().sort_values()
        dados = dados[dados["Data"].dt.to_period("M").isin(meses_com_venda.tail(meses))]
        todos_os_meses = meses_com_venda.tail(meses)
    else:
        inicio = (ate.to_period("M") - (meses - 1)).to_timestamp()
        dados = dados[dados["Data"] >= inicio]
        todos_os_meses = pd.period_range(inicio.to_period("M"), ate.to_period("M"), freq="M")

    serie = dados.pivot_table(
        index=dados["Data"].dt.to_period("M"),
        columns="Produto",
        values="Valor_Venda",
        aggfunc="sum",
    )
    return serie.reindex(todos_os_meses).round(2)
