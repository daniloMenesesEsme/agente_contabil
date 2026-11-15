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


# (final do plural, troca, mínimo de letras que sobram). Aplicado igual na consulta e no índice,
# então só precisa ser consistente, não linguisticamente perfeito.
_PLURAIS = (("oes", "ao", 1), ("aes", "ao", 1), ("ais", "al", 2), ("eis", "el", 2), ("ois", "ol", 2),
            ("res", "r", 2), ("zes", "z", 2), ("ns", "m", 2))


def radical(palavra: str) -> str:
    """Tira o plural: 'carnes' -> 'carne', 'oleos' -> 'oleo', 'saboes' -> 'sabao', 'flores' -> 'flor'."""
    if len(palavra) <= 3:
        return palavra
    for fim, troca, minimo in _PLURAIS:
        if palavra.endswith(fim) and len(palavra) - len(fim) >= minimo:
            return palavra[:-len(fim)] + troca
    if palavra.endswith("s") and not palavra.endswith("ss"):
        return palavra[:-1]
    return palavra


def lista_tokens(texto: str) -> list[str]:
    """Radicais das palavras com conteúdo, na ordem em que aparecem e sem repetir."""
    vistos: list[str] = []
    for p in normalizar_texto(texto).split():
        if len(p) > 1 and p not in STOPWORDS and radical(p) not in vistos:
            vistos.append(radical(p))
    return vistos


def tokens(texto: str) -> set[str]:
    return set(lista_tokens(texto))
