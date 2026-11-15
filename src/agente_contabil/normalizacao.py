import re
import unicodedata


def normalizar_ncm(ncm: str) -> str:
    """'1006.30.21' -> '10063021'. Mantém só dígitos."""
    return re.sub(r"\D", "", str(ncm or ""))


def ncm_valido(ncm: str) -> bool:
    """NCM completo tem 8 dígitos; prefixos (capítulo/posição) têm 2, 4 ou 6."""
    return len(normalizar_ncm(ncm)) in (2, 4, 6, 8)


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sem acentos, só letras/números/espaços."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", t.lower()).strip()


# Palavras sem conteúdo: "de" casaria qualquer descrição ("consultoria de marketing" x "pronto-socorro de ...").
STOPWORDS = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "ao", "aos", "as", "os",
             "um", "uma", "para", "por", "com", "sem", "ou", "que", "se", "ser"}


def tokens(texto: str) -> set[str]:
    return {p for p in normalizar_texto(texto).split() if len(p) > 1 and p not in STOPWORDS}
