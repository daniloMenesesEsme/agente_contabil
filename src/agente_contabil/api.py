"""API HTTP. Rotas /ncm e /buscar não usam IA (custo zero); /perguntar usa o modelo."""
import os

import anthropic
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .busca import buscar_produto
from .calculo import consultar
from .ncm_tabela import identificar_ncm, verificar_ncm
from .ferramentas import _resposta_busca
from .servicos import consultar_servico
from .simples import consultar_simples

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
def rota_buscar(q: str = Query(..., min_length=2), completo: bool = Query(False)):
    """Lista de candidatos; com `completo=true`, {candidatos, avisos} (avisos de lacunas conhecidas)."""
    return _resposta_busca(q) if completo else buscar_produto(q)


@app.get("/identificar")
def rota_identificar(q: str = Query(..., min_length=2)):
    return identificar_ncm(q)


@app.get("/verificar")
def rota_verificar(ncm: str, produto: str = Query(..., min_length=2)):
    r = verificar_ncm(ncm, produto)
    if "erro" in r:
        raise HTTPException(400, r["erro"])
    return r


@app.get("/servico")
def rota_servico(q: str = Query(..., min_length=2), ano: int | None = Query(None)):
    r = consultar_servico(q, ano)
    if "erro" in r:
        raise HTTPException(400, r["erro"])
    return r


@app.get("/simples")
def rota_simples(anexo: str = Query("")):
    r = consultar_simples(anexo)
    if "erro" in r:
        raise HTTPException(400, r["erro"])
    return r


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
