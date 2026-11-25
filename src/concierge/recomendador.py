"""Top 5 do Concierge a partir do questionário.

Usado em três lugares, para que a regra seja a mesma em todos: a seção 7 do notebook 03a, o notebook 04 e o app.

Etapas da variante "concierge":
1. Filtros de negócio: aberto, faz delivery (pedir) ou aceita reserva (sair), preço até o teto, culinária escolhida,
   dentro do raio.
2. Guarda de qualidade (contra o falso positivo, o erro caro do BU):
   - restaurante com pelo menos MIN_AVALIACOES avaliações: nota atual >= 4 (a nota de hoje é legítima na hora de
     recomendar; ela só não pode entrar no treino de um modelo que prevê o passado);
   - restaurante novo, com poucas avaliações: probabilidade do modelo A >= limiar de A.
3. Ordenação pelo gosto: o modelo B estima a chance de a pessoa escolher o restaurante e ordena os candidatos. Só
   entra quem passa de um piso: FATOR_LIMIAR_B x o limiar de B escolhido por F0,5 no notebook 03a. O piso é menor que o
   limiar cheio porque o falso positivo caro (casa mal avaliada) já é barrado na etapa 2; com o limiar cheio, 26% das
   respostas ficavam sem nenhuma recomendação (notebook 04, seção 3.1). Se menos de `top` passarem, a lista fica menor.
4. Vaga de descoberta (mitigação do viés para populares): se nenhum item da lista estiver na metade de menor movimento
   da cidade, a última vaga vai para o restaurante de menor movimento com maior chance de escolha que passou na guarda
   de qualidade e no piso de B. Ele aparece marcado como "descoberta".

A variante "controle" reproduz a ordenação atual dos apps (mesmos filtros, ordenada por movimento e nota, sem modelo).
É o braço de controle do teste A/B.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BAIRROS = {
    "Center City": (39.9526, -75.1652), "Old City": (39.9522, -75.1440), "Fishtown": (39.9727, -75.1340),
    "South Philly": (39.9245, -75.1690), "University City": (39.9522, -75.1932),
    "Northern Liberties": (39.9637, -75.1406), "Chinatown": (39.9555, -75.1550), "Manayunk": (40.0262, -75.2245),
}
MIN_AVALIACOES = 20          # abaixo disso a nota média é instável e quem decide é o modelo A
FATOR_LIMIAR_B = 0.5         # piso do modelo B = 50% do limiar F0,5 (escolhido na análise de sensibilidade do 04)
N_PERFIL = 3                 # o questionário vale como 3 dicas (protocolo do questionário simulado do BU)
ARQ_MODELOS = "concierge_yelp.joblib"
ARQ_RESTAURANTES = "restaurantes.parquet"


def km(lat1, lon1, lat2, lon2):
    """Distância em km entre pontos dados em radianos (fórmula de haversine)."""
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def carregar(pasta_modelos: str | Path):
    """Lê os artefatos gerados pelo notebook 03a: modelos + tabela de restaurantes."""
    pasta = Path(pasta_modelos)
    art = joblib.load(pasta / ARQ_MODELOS)
    tab = pd.read_parquet(pasta / ARQ_RESTAURANTES)
    tab["culinarias"] = tab["culinarias"].apply(lambda cs: [str(c) for c in cs])
    return art, tab


def perfil_questionario(culinarias, faixa_preco, modo, bairro, n=N_PERFIL):
    """Converte as respostas do questionário no mesmo estado de usuário que o modelo B viu no treino."""
    lat0, lon0 = np.radians(BAIRROS[bairro])
    return {"n": n, "cont": {c: n / len(culinarias) for c in culinarias}, "lat": lat0, "lon": lon0,
            "preco_medio": float(faixa_preco), "share_delivery": 1.0 if modo == "pedir" else 0.0}


def atributos_par(perfil: dict, cand: pd.DataFrame) -> pd.DataFrame:
    """Atributos do par (usuário, restaurante), iguais aos de `linha()` no notebook 03a, calculados para 'hoje'."""
    n = perfil["n"]
    afin = [[perfil["cont"].get(c, 0.0) / n for c in cs] or [0.0] for cs in cand["culinarias"]]
    dist = km(np.radians(cand["lat"].to_numpy()), np.radians(cand["lon"].to_numpy()), perfil["lat"], perfil["lon"])
    deliv = cand["delivery"].to_numpy(dtype=float)
    usd = perfil["share_delivery"]
    return pd.DataFrame({
        "user_n_prev_log": np.log1p(n),
        "afin_max": [max(a) for a in afin],
        "afin_media": [float(np.mean(a)) for a in afin],
        "dist_centroide_km": dist,
        "dist_min_km": dist,
        "user_preco_medio": perfil["preco_medio"],
        "dif_preco": np.abs(cand["preco"].to_numpy(dtype=float) - perfil["preco_medio"]),
        "user_share_delivery": usd,
        "cand_delivery": deliv,
        "match_delivery": deliv * usd,
        "cand_preco": cand["preco"].to_numpy(dtype=float),
        "cand_chk_prev_log": cand["cand_chk_prev_log"].to_numpy(),
        "cand_chk_365d_log": cand["cand_chk_365d_log"].to_numpy(),
        "cand_tips_prev_log": cand["cand_tips_prev_log"].to_numpy(),
        "cand_idade_anos": cand["cand_idade_anos"].to_numpy(),
    }, index=cand.index)


def candidatos(tab, culinarias, faixa_preco, modo, bairro, raio_km):
    """Filtros de negócio, comuns às duas variantes."""
    lat0, lon0 = np.radians(BAIRROS[bairro])
    cand = tab[(tab["is_open"] == 1) & (tab["preco"] <= faixa_preco)]
    cand = cand[cand["delivery"] == 1] if modo == "pedir" else cand[cand["reservas"] == 1]
    cand = cand[cand["culinarias"].apply(lambda cs: bool(set(cs) & set(culinarias)))].copy()
    cand["dist_km"] = km(lat0, lon0, np.radians(cand["lat"].to_numpy()), np.radians(cand["lon"].to_numpy()))
    return cand[cand["dist_km"] <= raio_km]


def passa_qualidade(cand, limiar_a, min_avaliacoes=MIN_AVALIACOES):
    estabelecido = cand["review_count"] >= min_avaliacoes
    return np.where(estabelecido, cand["stars"] >= 4, cand["prob_aprovacao"] >= limiar_a)


def _motivo(r, culinarias):
    cul = ", ".join([c for c in r["culinarias"] if c in culinarias][:2])
    qual = (f"nota {r['stars']:.1f}" if r["review_count"] >= MIN_AVALIACOES
            else f"casa nova, aprovação prevista {r['prob_aprovacao']:.0%}")
    return f"{cul} · {'$' * int(r['preco'])} · {r['dist_km']:.1f} km · {qual}"


COLUNAS_SAIDA = ["business_id", "nome", "culinaria", "preco", "dist_km", "stars", "review_count",
                 "prob_aprovacao", "prob_escolha", "descoberta", "por que"]


def corte_movimento(tab):
    """Mediana de movimento (check-ins até hoje) dos restaurantes abertos: separa 'menor' e 'maior' movimento."""
    return float(tab.loc[tab["is_open"] == 1, "cand_chk_prev_log"].median())


def recomendar(tab, art, culinarias, faixa_preco, modo="pedir", bairro="Center City", raio_km=3.0, top=5,
               variante="concierge", descoberta=True, fator_limiar_b=FATOR_LIMIAR_B):
    """Devolve até `top` restaurantes (DataFrame; vazio se nenhum passar)."""
    if not culinarias:
        raise ValueError("Escolha pelo menos uma culinária.")
    cand = candidatos(tab, culinarias, faixa_preco, modo, bairro, raio_km)
    if variante == "controle":
        ok = cand.sort_values(["cand_chk_prev_log", "stars"], ascending=False).head(top).copy()
        ok["prob_escolha"] = np.nan
        ok["descoberta"] = False
        ok["por que"] = "entre os mais movimentados perto de você"
    else:
        cand = cand[passa_qualidade(cand, art["limiar_A"])]
        if cand.empty:
            return pd.DataFrame(columns=COLUNAS_SAIDA)
        X = atributos_par(perfil_questionario(culinarias, faixa_preco, modo, bairro), cand)
        cand["prob_escolha"] = art["modelo_B"].predict_proba(X[art["atributos_B"]])[:, 1]
        cand["descoberta"] = False
        cand = cand[cand["prob_escolha"] >= fator_limiar_b * art["limiar_B"]]
        ok = cand.sort_values("prob_escolha", ascending=False).head(top)
        if descoberta and len(ok):
            corte = corte_movimento(tab)
            if not (ok["cand_chk_prev_log"] <= corte).any():
                pequenos = cand[(cand["cand_chk_prev_log"] <= corte) & ~cand.index.isin(ok.index)]
                if len(pequenos):
                    extra = pequenos.sort_values("prob_escolha", ascending=False).head(1).assign(descoberta=True)
                    ok = pd.concat([ok.head(top - 1), extra])
        ok["por que"] = [("descoberta: casa menos conhecida e bem avaliada · " if r["descoberta"] else "")
                         + _motivo(r, culinarias) for _, r in ok.iterrows()]
    # culinárias pedidas primeiro, para a coluna mostrar o que a pessoa escolheu
    ok["culinaria"] = ok["culinarias"].apply(
        lambda cs: ", ".join(([c for c in cs if c in culinarias] + [c for c in cs if c not in culinarias])[:2]))
    return ok[COLUNAS_SAIDA].reset_index(drop=True)
