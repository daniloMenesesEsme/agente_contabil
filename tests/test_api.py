from fastapi.testclient import TestClient

from agente_contabil.api import app

c = TestClient(app)


def test_rotas_sem_ia():
    assert c.get("/saude").json()["ok"]
    r = c.get("/ncm/10063021?ano=2026")
    assert r.status_code == 200 and r.json()["regime"] == "aliquota_zero"
    assert c.get("/ncm/abc").status_code == 400
    assert c.get("/buscar?q=leite").json()[0]["ncm_prefixo"] == "0401"


def test_rotas_servico_e_simples_sem_ia():
    r = c.get("/servico?q=ensino médio&ano=2026")
    assert r.status_code == 200 and r.json()["encontrados"][0]["item"] == "II-3"
    assert c.get("/servico?q=ensino&ano=1999").status_code == 400
    assert c.get("/simples").json()["anexos_disponiveis"]
    assert c.get("/simples?anexo=I").json()["anexo"] == "SN-I"
    assert c.get("/simples?anexo=ZZ").status_code == 400


def test_buscar_completo_traz_avisos_e_o_padrao_continua_lista():
    assert isinstance(c.get("/buscar?q=leite").json(), list)
    r = c.get("/buscar?q=medicamentos&completo=true").json()
    assert set(r) == {"candidatos", "avisos"} and any("AVISO DE TESTE" in a for a in r["avisos"])
