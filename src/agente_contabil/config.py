import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv é opcional
    pass

RAIZ = Path(__file__).resolve().parents[2]
DADOS = Path(os.getenv("DADOS_DIR", RAIZ / "dados"))
ARQ_REGRAS = DADOS / "regras_ncm.csv"
ARQ_PARAMETROS = DADOS / "parametros.json"
ARQ_PROMPT = RAIZ / "prompts" / "sistema.md"

MODELO = os.getenv("MODELO", "claude-opus-5-5")
ESFORCO = os.getenv("ESFORCO", "low")
ANO_PADRAO = int(os.getenv("ANO_PADRAO", "2027"))
