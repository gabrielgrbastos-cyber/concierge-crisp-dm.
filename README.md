# 🍽️ Concierge · recomendador diário de onde comer

Projeto final de **Ciência de Dados em Ambiente de Negócios** (FGV RI, 2026.2), desenvolvido com o CRISP-DM.

**Grupo:** Fabrício Wenter, Gabriel Gandolfi, Luís Gustavo Barbosa e Murilo Pilão

O Concierge liga consumidores a restaurantes. Um questionário curto (pedir ou sair, região, culinárias, preço e
distância) gera todo dia um top 5 personalizado que leva direto ao pedido ou à reserva. O erro caro é o **falso
positivo** (recomendar um lugar de que a pessoa não gosta), por isso o produto privilegia a precisão no topo.

## Estrutura

```
data/raw/                       JSON do Yelp Open Dataset (fora do Git)
notebooks/
  01_data_understanding.ipynb   Fase 2 (P1/P2)
  03a_modeling_yelp.ipynb       Fases 3 e 4 com business + tip + checkin: modelos A e B, top 5, artefatos do app
  03b_modeling_reviews.ipynb    Fases 3 e 4 com a nota individual (review.json) e o RMSE do BU
  04_evaluation.ipynb           Fase 5: Business Case, Responsible AI e teste A/B
src/concierge/recomendador.py   regra do top 5, usada pelos notebooks e pelo app
app/app.py                      protótipo em Streamlit (Fase 6) com sorteio A/B e log de eventos
models/                         artefatos gerados pelo 03a (modelos + tabela de restaurantes)
reports/                        figuras e tabelas geradas pelos notebooks
scripts/gerar_yelp_teste.py     JSON falsos no esquema do Yelp, só para testar o código
scripts/filtrar_reviews.py      reduz o review.json (≈5 GB) às avaliações de Philadelphia (≈30 MB), para o 03b
tests/                          testes do recomendador
```

## Como rodar

**1. Ambiente** (Python 3.11 ou mais novo)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**2. Dados.** Baixe o Yelp Open Dataset em <https://www.yelp.com/dataset> (é preciso aceitar os termos) e coloque em
`data/raw/` os arquivos `yelp_academic_dataset_business.json`, `_tip.json` e `_checkin.json`. O `_review.json` é
opcional (só o 03b usa); para não carregar os 5 GB, rode antes `python scripts/filtrar_reviews.py data/raw`.

**3. Notebooks, nesta ordem**

| Ordem | Notebook | Tempo aproximado | Gera |
|---|---|---|---|
| 1 | `03a_modeling_yelp.ipynb` | alguns minutos | `models/concierge_yelp.joblib`, `models/restaurantes.parquet`, `reports/03a_yelp/` |
| 2 | `03b_modeling_reviews.ipynb` | mais longo: lê o `review.json` (≈5 GB) | `reports/03b_reviews/` |
| 3 | `04_evaluation.ipynb` | menos de 1 minuto | `reports/04_evaluation/` |

O 04 depende do 03a. O 03b é independente e, sem o `review.json`, roda numa amostra sintética (os números então
validam só o código).

**4. App**

```bash
streamlit run app/app.py
```

Cada sessão é sorteada para **controle** (lista atual dos apps: mesmos filtros, ordenada por movimento e nota) ou
**concierge** (modelos). Na barra lateral dá para escolher a variante à mão para comparar as duas; essas sessões ficam
marcadas e não entram na análise do A/B. Os eventos (lista exibida, clique em pedir/reservar, nota da recomendação) vão
para `logs/eventos.csv`, que o notebook 04 lê.

**5. Testes**

```bash
python -m pytest -q
```

Para rodar os notebooks sem o Yelp (por exemplo, para conferir que o código executa):

```bash
python scripts/gerar_yelp_teste.py data/teste
YELP_DIR=data/teste jupyter nbconvert --to notebook --execute --inplace notebooks/03a_modeling_yelp.ipynb
```

## Deploy (para a professora testar)

O app roda no **Streamlit Community Cloud** a partir deste repositório: em <https://share.streamlit.io>, "Create app",
escolha o repositório, a branch `main` e o arquivo `app/app.py`. Antes, faça o commit de `models/concierge_yelp.joblib`
e `models/restaurantes.parquet` gerados pelo 03a.

Os termos do Yelp restringem a redistribuição dos dados, e `restaurantes.parquet` contém nomes e coordenadas do Yelp.
Por isso o repositório deve ser **privado**, com a professora como colaboradora, e o app compartilhado só com ela
(o Community Cloud aceita repositórios privados e apps com acesso restrito por e-mail). O log do app no Community Cloud
é apagado quando o app reinicia: baixe o CSV pela barra lateral antes.

## Decisões de projeto

| Tema | Decisão | Onde |
|---|---|---|
| Alvo | 03a: aprovação do restaurante (nota ≥ 4) e escolha revelada (dica); 03b: nota individual ≥ 4 e RMSE | 03a, 03b |
| Custo do erro | limiar escolhido por F0,5 na validação (precisão pesa 2× o recall) | 03a, 03b |
| Vazamento | atributos só com o passado, corte temporal, snapshots do Yelp fora dos atributos, teste usado uma vez | 03a, 03b |
| Guarda de qualidade | casa com 20+ avaliações precisa de nota ≥ 4; casa nova passa só se o modelo A aprovar | `recomendador.py` |
| Viés para populares | vaga de descoberta para casas de menor movimento; cobertura, exposição por porte e Gini medidos | 04, seção 4 |
| Teste A/B | sorteio por usuário, conversão da sessão como métrica principal, checagem de SRM | app, 04 seção 5 |
| LGPD | sem gênero, idade, raça ou renda; localização por bairro e raio; restrições alimentares não são guardadas | app, 04 |

## Resultados com os dados reais

Base: Yelp Open Dataset, restaurantes de Philadelphia (5.855 restaurantes, 87 mil dicas de 34 mil usuários, 1,2 milhão
de check-ins). Os notebooks 03a e 04 rodaram com `business`, `tip` e `checkin`.

**Limitação assumida:** sem o `review.json`, não há a nota que cada pessoa deu a cada restaurante. A preferência
pessoal é medida por uma *proxy*, a dica (`tip`): ela mostra que a pessoa foi ao restaurante, não que gostou. A
qualidade vem da nota média do restaurante, que é uma fotografia do fim da base. Por isso o 03b, que usaria a nota
individual e o RMSE prometido no BU, está executado sobre a amostra sintética e só valida o código; ele roda com a base
real assim que o `review.json` filtrado estiver em `data/raw/`.

| Etapa | Resultado no teste | Referência |
|---|---|---|
| Hipótese do BU (2.1 do 03a) | culinária favorita recebe 23,4% das visitas seguintes | 17,2% ao acaso (p < 0,001); tom das dicas igual na favorita e nas demais |
| Modelo A, aprovação (random forest) | AUC 0,821, precisão 78,3% | popularidade: AUC 0,588, precisão 49,6% |
| Modelo A em casas com menos de 20 avaliações | AUC 0,744, precisão 74,4%, taxa de falso positivo 7,9% | é onde ele decide no app |
| Modelo B, escolha (gradient boosting) | AUC 0,864; escolhido em 1º entre 5 em 67,5% dos casos; MRR 0,813 | popularidade: 40,7% e 0,603; ao acaso: 20% e 0,457 |
| Top 5 em 576 respostas simuladas | 0% das indicações em casa estabelecida com nota < 4; 8,9% de respostas sem recomendação | lista atual: 32,2% e 1,6% |
| Viés para populares | 14,2% das indicações vão para a metade de menor movimento | lista atual: 2,0% |

Ajuste feito na Fase 5: com o limiar cheio do modelo B, 25,7% das respostas ficavam sem recomendação. Como a casa mal
avaliada já é barrada pela guarda de qualidade, o B passou a usar um piso de 50% do limiar (precisão de B no teste cai
de 76,0% para 55,5%, contra 20% ao acaso) e as respostas vazias caíram para 8,9%. A tabela completa está no notebook 04,
seção 3.1.

Limite conhecido: em Manayunk, com poucos restaurantes no raio de 3 km, só 5,6% das respostas têm 3 ou mais
recomendações.
