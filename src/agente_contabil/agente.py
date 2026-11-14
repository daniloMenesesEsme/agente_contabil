"""Agente: o modelo entende a pergunta e chama as ferramentas; os números vêm da base."""
from functools import lru_cache

import anthropic

from . import config
from .ferramentas import FERRAMENTAS, executar

MAX_ITERACOES = 6
# Modelos que aceitam fallback automático no servidor em caso de recusa.
_COM_FALLBACK = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1"}


@lru_cache(maxsize=1)
def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic()  # lê ANTHROPIC_API_KEY do ambiente/.env


@lru_cache(maxsize=1)
def _sistema() -> str:
    return config.ARQ_PROMPT.read_text(encoding="utf-8")


def _chamar(mensagens: list) -> anthropic.types.Message:
    params = dict(
        model=config.MODELO,
        max_tokens=4000,
        system=_sistema(),
        tools=FERRAMENTAS,
        messages=mensagens,
        output_config={"effort": config.ESFORCO},
        cache_control={"type": "ephemeral"},  # cache do prompt + ferramentas: barateia chamadas repetidas
    )
    if config.MODELO in _COM_FALLBACK:
        return _cliente().beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params)
    return _cliente().messages.create(**params)


def perguntar(pergunta: str, ano: int | None = None) -> dict:
    ano = ano or config.ANO_PADRAO
    mensagens = [{"role": "user", "content": f"[Ano de referência: {ano}]\n{pergunta}"}]
    uso = {"entrada": 0, "saida": 0, "cache_lido": 0}
    consultas = []

    for _ in range(MAX_ITERACOES):
        resp = _chamar(mensagens)
        uso["entrada"] += resp.usage.input_tokens
        uso["saida"] += resp.usage.output_tokens
        uso["cache_lido"] += resp.usage.cache_read_input_tokens or 0

        if resp.stop_reason == "refusal":
            return {"resposta": "Não foi possível responder a esta pergunta.", "consultas": consultas, "uso": uso}
        if resp.stop_reason == "pause_turn":
            mensagens.append({"role": "assistant", "content": resp.content})
            continue
        chamadas = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not chamadas:
            texto = "\n".join(b.text for b in resp.content if b.type == "text").strip()
            return {"resposta": texto, "consultas": consultas, "uso": uso}

        mensagens.append({"role": "assistant", "content": resp.content})
        resultados = []
        for c in chamadas:
            conteudo, erro = executar(c.name, c.input)
            consultas.append({"ferramenta": c.name, "entrada": c.input})
            resultados.append({"type": "tool_result", "tool_use_id": c.id, "content": conteudo, "is_error": erro})
        mensagens.append({"role": "user", "content": resultados})  # todos os resultados numa mensagem só

    return {"resposta": "Limite de etapas atingido; reformule a pergunta.", "consultas": consultas, "uso": uso}
