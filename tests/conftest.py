import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(autouse=True)
def regras_de_teste(monkeypatch):
    """Os testes usam uma base pequena e fixa (tests/dados), não o dados/regras_ncm.csv real:
    o arquivo real muda a cada revisão do contador e não pode quebrar os testes."""
    from agente_contabil import config, lote, ncm_tabela, regras, servicos, simples, texto_busca
    dados = Path(__file__).parent / "dados"
    monkeypatch.setattr(config, "ARQ_REGRAS", dados / "regras_teste.csv")
    monkeypatch.setattr(config, "ARQ_SERVICOS", dados / "regras_servicos_teste.csv")
    monkeypatch.setattr(config, "ARQ_SIMPLES", dados / "simples_teste.csv")
    monkeypatch.setattr(config, "ARQ_SINONIMOS", dados / "sinonimos_teste.csv")
    monkeypatch.setattr(config, "ARQ_AVISOS_BUSCA", dados / "avisos_busca_teste.csv")
    # tabela oficial da NCM: por padrão INDISPONÍVEL nos testes (os que precisam usam o fixture tabela_ncm)
    monkeypatch.setattr(config, "ARQ_NCM", dados / "nao_existe_ncm.csv")
    monkeypatch.setattr(config, "ARQ_NCM_META", dados / "nao_existe_ncm_meta.json")
    caches = (regras.carregar, servicos.carregar, simples.carregar, texto_busca.sinonimos,
              texto_busca._avisos_por_termo, ncm_tabela.carregar, ncm_tabela._indice, lote._consulta,
              lote._sugestoes, lote._verificacao)
    for c in caches:
        c.cache_clear()
    yield
    for c in caches:
        c.cache_clear()


@pytest.fixture
def tabela_ncm(monkeypatch):
    """Liga a mini tabela oficial de teste (tests/dados/ncm_tabela_teste.csv)."""
    from agente_contabil import config, ncm_tabela
    dados = Path(__file__).parent / "dados"
    monkeypatch.setattr(config, "ARQ_NCM", dados / "ncm_tabela_teste.csv")
    monkeypatch.setattr(config, "ARQ_NCM_META", dados / "ncm_tabela_meta_teste.json")
    from agente_contabil import lote
    for c in (ncm_tabela.carregar, ncm_tabela._indice, lote._consulta,
              lote._sugestoes, lote._verificacao):
        c.cache_clear()
    yield
    for c in (ncm_tabela.carregar, ncm_tabela._indice, lote._consulta,
              lote._sugestoes, lote._verificacao):
        c.cache_clear()
