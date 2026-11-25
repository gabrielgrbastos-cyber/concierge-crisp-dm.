"""Gera arquivos JSON pequenos no MESMO ESQUEMA do Yelp Open Dataset, só para testar o código.

Não são dados reais e os números que saem deles não valem como resultado. Servem para rodar os notebooks
ponta a ponta (ou numa integração contínua) sem baixar os ~9 GB do Yelp.

Uso:
    python scripts/gerar_yelp_teste.py data/teste
    YELP_DIR=data/teste jupyter nbconvert --execute notebooks/03a_modeling_yelp.ipynb
"""
import json
import sys
from pathlib import Path

import numpy as np

SEED = 7
BAIRROS = {
    "Center City": (39.9526, -75.1652), "Old City": (39.9522, -75.1440), "Fishtown": (39.9727, -75.1340),
    "South Philly": (39.9245, -75.1690), "University City": (39.9522, -75.1932),
    "Northern Liberties": (39.9637, -75.1406), "Chinatown": (39.9555, -75.1550), "Manayunk": (40.0262, -75.2245),
}
CULINARIAS = ["Pizza", "American (New)", "American (Traditional)", "Italian", "Chinese", "Mexican", "Japanese",
              "Sandwiches", "Breakfast & Brunch", "Burgers", "Thai", "Seafood", "Vietnamese", "Indian"]
DIAS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
POS = ["great", "love", "delicious", "amazing", "best", "fresh", "friendly"]
NEG = ["bad", "slow", "cold", "overpriced", "rude", "bland"]


def _ts(rng, ini, fim):
    s = rng.integers(np.datetime64(ini, "s").astype(int), np.datetime64(fim, "s").astype(int))
    return str(np.datetime64(int(s), "s")).replace("T", " ")


def gerar(pasta: Path, n_rest=900, n_users=2500):
    rng = np.random.default_rng(SEED)
    pasta.mkdir(parents=True, exist_ok=True)
    qualidade = rng.normal(0, 0.6, n_rest)
    pop = (rng.pareto(1.4, n_rest) + 0.05) * np.exp(0.6 * qualidade)
    cul_rest, preco_rest, biz = [], [], []
    for i in range(n_rest):
        bairro = rng.choice(list(BAIRROS))
        lat0, lon0 = BAIRROS[bairro]
        cs = list(rng.choice(CULINARIAS, size=rng.integers(1, 3), replace=False))
        preco = int(rng.integers(1, 5))
        cul_rest.append(cs)
        preco_rest.append(preco)
        attrs = {
            "RestaurantsPriceRange2": str(preco) if rng.random() > 0.15 else "None",
            "RestaurantsDelivery": rng.choice(["True", "False", "None"], p=[.6, .35, .05]),
            "RestaurantsTakeOut": rng.choice(["True", "False"]),
            "RestaurantsReservations": "True" if preco >= 3 or rng.random() > .7 else "False",
            "OutdoorSeating": rng.choice(["True", "False"]),
            "GoodForKids": rng.choice(["True", "False"]),
            "RestaurantsGoodForGroups": rng.choice(["True", "False"]),
            "HasTV": rng.choice(["True", "False"]),
            "BusinessAcceptsCreditCards": "True",
            "RestaurantsTableService": rng.choice(["True", "False"]),
            "Alcohol": rng.choice(["u'none'", "'beer_and_wine'", "u'full_bar'"]),
            "NoiseLevel": rng.choice(["u'quiet'", "u'average'", "'loud'"]),
            "WiFi": rng.choice(["u'free'", "'no'", "None"]),
            "Ambience": "{'romantic': False, 'casual': %s, 'classy': %s, 'trendy': False}"
                        % (rng.random() > .3, rng.random() > .7),
            "GoodForMeal": "{'lunch': True, 'dinner': %s, 'brunch': False}" % (rng.random() > .2),
            "BusinessParking": "{'street': True, 'lot': %s, 'garage': False, 'valet': False}" % (rng.random() > .6),
        }
        if rng.random() < 0.1:
            attrs = None
        horas = None if rng.random() < 0.15 else {d: rng.choice(["11:0-22:0", "7:0-15:0", "17:0-2:0"]) for d in DIAS}
        stars = float(np.clip(np.round((3.7 + qualidade[i] + rng.normal(0, .3)) * 2) / 2, 1, 5))
        biz.append({"business_id": f"B{i:05d}", "name": f"Restaurante Teste {i}", "address": f"{i} Test St",
                    "city": "Philadelphia" if rng.random() > .02 else "Philadelphia ", "state": "PA",
                    "postal_code": "19107", "latitude": lat0 + rng.normal(0, .006), "longitude": lon0 + rng.normal(0, .006),
                    "stars": stars, "review_count": int(5 + pop[i] * 40), "is_open": int(rng.random() > .2),
                    "attributes": attrs, "categories": ", ".join(cs + ["Restaurants"]), "hours": horas})
    # alguns negócios que não são restaurantes, para o filtro ter o que filtrar
    for j in range(40):
        biz.append({"business_id": f"X{j:04d}", "name": f"Loja {j}", "address": "", "city": "Philadelphia",
                    "state": "PA", "postal_code": "19107", "latitude": 39.95, "longitude": -75.16, "stars": 4.0,
                    "review_count": 10, "is_open": 1, "attributes": None, "categories": "Shopping", "hours": None})

    afin = rng.dirichlet(np.full(len(CULINARIAS), 0.4), n_users)
    idx = {c: k for k, c in enumerate(CULINARIAS)}
    tips, reviews, checkins = [], [], []
    for u in range(n_users):
        k = int(np.clip(rng.zipf(1.8), 1, 60))
        gosto = np.array([max(afin[u, idx[c]] for c in cs) for cs in cul_rest])
        p = pop ** 0.7 * (0.02 + gosto) ** 1.3
        escolhidos = rng.choice(n_rest, size=min(k, n_rest), replace=False, p=p / p.sum())
        for b in escolhidos:
            nota = int(np.clip(np.round(3.8 + qualidade[b] + 4 * (gosto[b] - 0.07) + rng.normal(0, .8)), 1, 5))
            data = _ts(rng, "2010-01-01", "2022-01-15")
            reviews.append({"review_id": f"R{len(reviews):07d}", "user_id": f"U{u:05d}", "business_id": f"B{b:05d}",
                            "stars": float(nota), "useful": 0, "funny": 0, "cool": 0, "text": "teste", "date": data})
            if rng.random() < 0.6:
                palavra = rng.choice(POS if nota >= 4 else NEG)
                tips.append({"user_id": f"U{u:05d}", "business_id": f"B{b:05d}", "text": f"The food was {palavra}.",
                             "date": data, "compliment_count": int(rng.poisson(.2))})
    reviews += reviews[:30]  # duplicatas de propósito
    for i in range(n_rest):
        n = int(np.clip(pop[i] * 60, 1, 3000))
        datas = sorted(_ts(rng, "2010-06-01", "2022-01-15") for _ in range(n))
        checkins.append({"business_id": f"B{i:05d}", "date": ", ".join(datas)})
    users = [{"user_id": f"U{u:05d}", "name": f"U{u}", "review_count": 1, "yelping_since": "2010-01-01 00:00:00",
              "average_stars": 4.0} for u in range(n_users)]

    for nome, linhas in [("business", biz), ("tip", tips), ("checkin", checkins), ("review", reviews), ("user", users)]:
        with open(pasta / f"yelp_academic_dataset_{nome}.json", "w") as f:
            for linha in linhas:
                f.write(json.dumps(linha) + "\n")
    print(f"Gerado em {pasta}: {n_rest} restaurantes, {len(tips)} dicas, {len(reviews)} avaliações")


if __name__ == "__main__":
    gerar(Path(sys.argv[1] if len(sys.argv) > 1 else "data/teste"))
