import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(autouse=True)
def regras_de_teste(monkeypatch):
    """Os testes usam uma base pequena e fixa (tests/dados), não o dados/regras_ncm.csv real:
    o arquivo real muda a cada revisão do contador e não pode quebrar os testes."""
    from agente_contabil import config, regras, servicos, simples, texto_busca
    dados = Path(__file__).parent / "dados"
    monkeypatch.setattr(config, "ARQ_REGRAS", dados / "regras_teste.csv")
    monkeypatch.setattr(config, "ARQ_SERVICOS", dados / "regras_servicos_teste.csv")
    monkeypatch.setattr(config, "ARQ_SIMPLES", dados / "simples_teste.csv")
    monkeypatch.setattr(config, "ARQ_SINONIMOS", dados / "sinonimos_teste.csv")
    monkeypatch.setattr(config, "ARQ_AVISOS_BUSCA", dados / "avisos_busca_teste.csv")
    caches = (regras.carregar, servicos.carregar, simples.carregar, texto_busca.sinonimos,
              texto_busca._avisos_por_termo)
    for c in caches:
        c.cache_clear()
    yield
    for c in caches:
        c.cache_clear()
