import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(autouse=True)
def regras_de_teste(monkeypatch):
    """Os testes usam uma base pequena e fixa (tests/dados), não o dados/regras_ncm.csv real:
    o arquivo real muda a cada revisão do contador e não pode quebrar os testes."""
    from agente_contabil import config, regras
    monkeypatch.setattr(config, "ARQ_REGRAS", Path(__file__).parent / "dados" / "regras_teste.csv")
    regras.carregar.cache_clear()
    yield
    regras.carregar.cache_clear()
