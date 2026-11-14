"""API HTTP. Rotas /ncm e /buscar não usam IA (custo zero); /perguntar usa o modelo."""
import os

import anthropic
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .busca import buscar_produto
from .calculo import consultar

app = FastAPI(title="Agente Contábil — IBS/CBS", version="0.1.0")


class Pergunta(BaseModel):
    pergunta: str
    ano: int | None = None


@app.get("/saude")
def saude():
    return {"ok": True, "ia_configurada": bool(os.getenv("ANTHROPIC_API_KEY"))}


@app.get("/ncm/{ncm}")
def rota_ncm(ncm: str, ano: int | None = Query(None)):
    r = consultar(ncm, ano)
    if "erro" in r:
        raise HTTPException(400, r["erro"])
    return r


@app.get("/buscar")
def rota_buscar(q: str = Query(..., min_length=2)):
    return buscar_produto(q)


@app.post("/perguntar")
def rota_perguntar(p: Pergunta):
    from .agente import perguntar  # importa só quando necessário
    try:
        return perguntar(p.pergunta, p.ano)
    except anthropic.AuthenticationError:
        raise HTTPException(500, "ANTHROPIC_API_KEY ausente ou inválida.")
    except anthropic.RateLimitError:
        raise HTTPException(429, "Limite da API atingido; tente novamente em instantes.")
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"Erro da API: {e.message}")
    except anthropic.APIConnectionError:
        raise HTTPException(503, "Sem conexão com a API.")
