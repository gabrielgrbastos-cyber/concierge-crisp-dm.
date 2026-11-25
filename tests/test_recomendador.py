"""Testes do recomendador com uma tabela pequena feita à mão (não precisa do Yelp nem dos modelos treinados).

Rodar na raiz do repositório:  python -m pytest -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from concierge import recomendador as rec  # noqa: E402

LAT0, LON0 = rec.BAIRROS["Center City"]
ATRIBUTOS_B = ["user_n_prev_log", "afin_max", "afin_media", "dist_centroide_km", "dist_min_km", "user_preco_medio",
               "dif_preco", "user_share_delivery", "cand_delivery", "match_delivery", "cand_preco",
               "cand_chk_prev_log", "cand_chk_365d_log", "cand_tips_prev_log", "cand_idade_anos"]


class ModeloFalso:
    """Chance de escolha cresce com o movimento: imita o viés para populares do modelo real."""
    def predict_proba(self, X):
        p = np.clip(0.3 + 0.1 * X["cand_chk_prev_log"].to_numpy(), 0, 1)
        return np.c_[1 - p, p]


def restaurante(i, **kw):
    base = {"business_id": f"r{i}", "nome": f"R{i}", "stars": 4.5, "review_count": 100, "is_open": 1,
            "lat": LAT0 + 0.001 * i, "lon": LON0, "preco": 2.0, "delivery": 1.0, "reservas": 1.0,
            "culinarias": ["Japanese"], "prob_aprovacao": 0.9, "cand_chk_prev_log": 5.0,
            "cand_chk_365d_log": 2.0, "cand_tips_prev_log": 2.0, "cand_idade_anos": 5.0}
    return base | kw


@pytest.fixture
def tab():
    linhas = [restaurante(i, cand_chk_prev_log=6.0 + i * 0.1) for i in range(6)]            # populares e bons
    linhas += [
        restaurante(10, stars=3.0),                                                    # estabelecido com nota < 4
        restaurante(11, review_count=5, stars=2.0, prob_aprovacao=0.9, cand_chk_prev_log=0.5),  # novo, A aprova
        restaurante(12, review_count=5, stars=5.0, prob_aprovacao=0.1, cand_chk_prev_log=0.5),  # novo, A reprova
        restaurante(13, preco=4.0),                                                    # acima do teto
        restaurante(14, delivery=0.0),                                                 # não entrega
        restaurante(15, is_open=0),                                                    # fechado
        restaurante(16, culinarias=["Pizza"]),                                         # outra culinária
        restaurante(17, lat=LAT0 + 0.2),                                               # longe (~22 km)
    ]
    linhas += [restaurante(20 + i, cand_chk_prev_log=0.1) for i in range(6)]          # pouco movimento (outras cidades)
    for r in linhas[-6:]:
        r["culinarias"] = ["Thai"]
    return pd.DataFrame(linhas)


@pytest.fixture
def art():
    return {"modelo_B": ModeloFalso(), "limiar_B": 0.5, "limiar_A": 0.5, "atributos_B": ATRIBUTOS_B}


def test_atributos_par_tem_as_colunas_do_treino(tab):
    p = rec.perfil_questionario(["Japanese", "Thai"], 2, "pedir", "Center City")
    X = rec.atributos_par(p, tab)
    assert list(X.columns) == ATRIBUTOS_B
    assert X.loc[0, "afin_max"] == pytest.approx(0.5)          # 2 culinárias declaradas: metade do perfil em cada
    assert X.loc[0, "dist_centroide_km"] == pytest.approx(0.0, abs=1e-9)
    assert X.loc[0, "match_delivery"] == 1.0


def test_filtros_de_negocio(tab):
    cand = rec.candidatos(tab, ["Japanese"], 2, "pedir", "Center City", 3.0)
    assert not {"r13", "r14", "r15", "r16", "r17"} & set(cand["business_id"])
    assert (cand["preco"] <= 2).all() and (cand["delivery"] == 1).all()


def test_guarda_de_qualidade(tab, art):
    out = rec.recomendar(tab, art, ["Japanese"], 2, top=20, descoberta=False)
    ids = set(out["business_id"])
    assert "r10" not in ids          # estabelecido com nota 3.0
    assert "r12" not in ids          # novo e reprovado pelo modelo A
    assert len(out) <= 20


def test_top5_ordenado_pela_chance_de_escolha(tab, art):
    out = rec.recomendar(tab, art, ["Japanese"], 2, descoberta=False)
    assert len(out) == 5
    assert out["prob_escolha"].is_monotonic_decreasing


def test_vaga_de_descoberta(tab, art):
    out = rec.recomendar(tab, art, ["Japanese"], 2)
    assert out["descoberta"].sum() == 1 and out.iloc[-1]["business_id"] == "r11"
    assert out.iloc[-1]["por que"].startswith("descoberta")


def test_controle_ordena_por_movimento(tab, art):
    out = rec.recomendar(tab, art, ["Japanese"], 2, variante="controle")
    assert out.iloc[0]["business_id"] == "r5" and len(out) == 5


def test_sem_candidatos_devolve_vazio(tab, art):
    out = rec.recomendar(tab, art, ["Korean"], 2)
    assert out.empty and list(out.columns) == rec.COLUNAS_SAIDA


def test_culinaria_obrigatoria(tab, art):
    with pytest.raises(ValueError):
        rec.recomendar(tab, art, [], 2)
