from fastapi.testclient import TestClient

from agente_contabil.api import app

c = TestClient(app)


def test_rotas_sem_ia():
    assert c.get("/saude").json()["ok"]
    r = c.get("/ncm/10063021?ano=2026")
    assert r.status_code == 200 and r.json()["regime"] == "aliquota_zero"
    assert c.get("/ncm/abc").status_code == 400
    assert c.get("/buscar?q=leite").json()[0]["ncm_prefixo"] == "0401"
