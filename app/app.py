"""Concierge · protótipo do app (Fase 6 do CRISP-DM).

Rodar na raiz do repositório:
    streamlit run app/app.py

Precisa dos artefatos que o notebook 03a grava em models/. Cada sessão é sorteada para uma variante do teste A/B
(controle = lista atual dos apps; concierge = modelos) e os eventos vão para logs/eventos.csv, que o notebook 04 analisa.
"""
import csv
import hashlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from concierge import recomendador as rec  # noqa: E402

LOG = RAIZ / "logs" / "eventos.csv"
CAMPOS = ["ts", "sessao", "variante", "origem", "evento", "posicao", "business_id", "n_itens", "nota",
          "modo", "bairro", "culinarias", "teto", "raio_km"]
PRECOS = {1: "$ (barato)", 2: "$$", 3: "$$$", 4: "$$$$ (caro)"}

st.set_page_config(page_title="Concierge", page_icon="🍽️", layout="centered")


@st.cache_resource
def carregar():
    return rec.carregar(RAIZ / "models")


def registrar(evento, **campos):
    LOG.parent.mkdir(exist_ok=True)
    novo = not LOG.exists()
    linha = {c: "" for c in CAMPOS} | {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                         "sessao": st.session_state.sessao, "variante": st.session_state.variante,
                                         "origem": st.session_state.origem, "evento": evento} | campos
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        w.writerow(linha)


try:
    art, tab = carregar()
except FileNotFoundError:
    st.error("Modelos não encontrados em `models/`. Rode o notebook `03a_modeling_yelp.ipynb` antes (ver README).")
    st.stop()

# ---------------- sessão e sorteio do teste A/B
if "sessao" not in st.session_state:
    st.session_state.sessao = uuid.uuid4().hex[:12]
    st.session_state.resultado = None
    st.session_state.escolhidos = set()
    st.session_state.avaliado = False

with st.sidebar:
    st.header("Sobre")
    st.write(f"Protótipo acadêmico (FGV) com dados do Yelp Open Dataset, Philadelphia, até {art['data_base']}.")
    st.write(f"Modelo de qualidade: {art['nome_A']} · modelo de gosto: {art['nome_B']}.")
    st.subheader("Teste A/B")
    escolha = st.radio("Variante", ["sorteio", "concierge", "controle"], index=0,
                       help="Sorteio é o modo do piloto. As outras opções servem para comparar as duas listas.")
    if escolha == "sorteio":
        sorteio = int(hashlib.sha256(st.session_state.sessao.encode()).hexdigest(), 16) % 2
        st.session_state.variante, st.session_state.origem = ("concierge" if sorteio else "controle"), "sorteio"
    else:
        st.session_state.variante, st.session_state.origem = escolha, "manual"
    st.caption(f"Sessão {st.session_state.sessao} · variante **{st.session_state.variante}**")
    if LOG.exists():
        st.download_button("Baixar log de eventos", LOG.read_bytes(), "eventos.csv", "text/csv")

# ---------------- questionário
st.title("🍽️ Concierge")
st.write("Responda em poucos segundos e receba até 5 lugares para hoje.")

with st.form("questionario"):
    modo = st.radio("Você quer pedir ou sair para comer?", ["pedir", "sair"], horizontal=True,
                    format_func=lambda m: "Pedir em casa" if m == "pedir" else "Sair para comer")
    bairro = st.selectbox("Onde você está?", list(rec.BAIRROS))
    culinarias = st.multiselect("O que você quer comer hoje? (até 3)", sorted(art["culinarias"]), max_selections=3)
    teto = st.select_slider("Até quanto quer gastar?", options=list(PRECOS), value=2, format_func=PRECOS.get)
    raio = st.slider("Distância máxima (km)", 1.0, 8.0, 3.0, 0.5)
    st.caption("Tem alguma restrição alimentar? Confirme sempre com o restaurante: o Concierge não guarda nem usa essa "
               "informação.")
    enviar = st.form_submit_button("Ver recomendações", type="primary")

if enviar:
    if not culinarias:
        st.warning("Escolha pelo menos uma culinária.")
    else:
        out = rec.recomendar(tab, art, culinarias, teto, modo=modo, bairro=bairro, raio_km=raio,
                             variante=st.session_state.variante)
        st.session_state.resultado = {"out": out, "modo": modo, "bairro": bairro, "culinarias": culinarias,
                                      "teto": teto, "raio": raio}
        st.session_state.escolhidos, st.session_state.avaliado = set(), False
        registrar("exibicao", n_itens=len(out), modo=modo, bairro=bairro, culinarias="|".join(culinarias),
                  teto=teto, raio_km=raio)

# ---------------- resultado
res = st.session_state.resultado
if res is not None:
    out = res["out"]
    contexto = {"modo": res["modo"], "bairro": res["bairro"], "culinarias": "|".join(res["culinarias"]),
                "teto": res["teto"], "raio_km": res["raio"]}
    if out.empty:
        st.info("Nenhum lugar passou nos filtros e na checagem de qualidade. Tente aumentar a distância, o preço ou "
                "incluir outra culinária.")
    else:
        st.subheader("Para você hoje")
        acao = "Quero pedir" if res["modo"] == "pedir" else "Quero reservar"
        for i, r in out.iterrows():
            with st.container(border=True):
                st.markdown(f"**{i + 1}. {r['nome']}**" + ("  ·  ✨ descoberta" if r["descoberta"] else ""))
                st.caption(r["por que"])
                if r["business_id"] in st.session_state.escolhidos:
                    st.success("Boa escolha! No app real, aqui abriria o pedido ou a reserva.")
                elif st.button(acao, key=f"btn_{r['business_id']}"):
                    st.session_state.escolhidos.add(r["business_id"])
                    registrar("clique", posicao=i + 1, business_id=r["business_id"], n_itens=len(out), **contexto)
                    st.rerun()

        st.divider()
        if st.session_state.avaliado:
            st.write("Obrigado pela avaliação!")
        else:
            nota = st.radio("Como foi esta recomendação?", [1, 2, 3, 4, 5], index=None, horizontal=True)
            if st.button("Enviar avaliação", disabled=nota is None):
                registrar("feedback", nota=nota, n_itens=len(out), **contexto)
                st.session_state.avaliado = True
                st.rerun()
