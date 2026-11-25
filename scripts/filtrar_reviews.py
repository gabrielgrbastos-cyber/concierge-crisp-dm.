"""Reduz o review.json do Yelp (≈5 GB) às avaliações de restaurantes de Philadelphia, só com as colunas usadas.

Não precisa de nenhuma biblioteca além do Python. Lê o arquivo linha a linha (pouca memória) e grava
`review_philadelphia.json.gz` (≈30 MB) na mesma pasta. O notebook 03b lê esse arquivo direto.

Uso (na raiz do repositório, com os JSON do Yelp em data/raw/):
    python scripts/filtrar_reviews.py data/raw
"""
import gzip
import json
import sys
import time
from pathlib import Path

CIDADE = "philadelphia"
COLUNAS = ["review_id", "user_id", "business_id", "stars", "date"]
CHAVE = '"business_id"'


def ids_restaurantes(arq_business: Path) -> set:
    ids = set()
    with open(arq_business, encoding="utf-8") as f:
        for linha in f:
            b = json.loads(linha)
            if (b.get("city") or "").strip().casefold() == CIDADE and "Restaurants" in (b.get("categories") or ""):
                ids.add(b["business_id"])
    return ids


def filtrar(pasta: Path):
    ids = ids_restaurantes(pasta / "yelp_academic_dataset_business.json")
    print(f"Restaurantes em Philadelphia: {len(ids):,}")
    entrada, saida = pasta / "yelp_academic_dataset_review.json", pasta / "review_philadelphia.json.gz"
    t0, lidas, mantidas = time.time(), 0, 0
    with open(entrada, encoding="utf-8") as f, gzip.open(saida, "wt", encoding="utf-8") as out:
        for linha in f:
            lidas += 1
            i = linha.find(CHAVE)                       # acha o business_id sem decodificar a linha inteira
            if i < 0:
                continue
            j = linha.find('"', linha.find(":", i + len(CHAVE)) + 1) + 1
            if linha[j: linha.find('"', j)] not in ids:
                continue
            r = json.loads(linha)
            out.write(json.dumps({c: r[c] for c in COLUNAS}) + "\n")
            mantidas += 1
            if mantidas % 100_000 == 0:
                print(f"  {lidas:,} lidas | {mantidas:,} mantidas | {time.time() - t0:.0f}s")
    print(f"Pronto: {mantidas:,} avaliações de {lidas:,} em {time.time() - t0:.0f}s -> {saida} "
          f"({saida.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    filtrar(Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw"))
