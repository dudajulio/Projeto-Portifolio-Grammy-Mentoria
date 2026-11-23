from pathlib import Path
import pandas as pd
import csv
import re

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS (ARQUITETURA MEDALLION: RAW -> SILVER)
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "src" else Path(__file__).resolve().parent
PASTA_RAW = BASE_DIR / "data" / "raw"
PASTA_SILVER = BASE_DIR / "data" / "silver"
PASTA_SILVER.mkdir(parents=True, exist_ok=True)

CSV_BRUTO = PASTA_RAW / "grammy.csv"
CSV_SANEADO = PASTA_SILVER / "grammy_saneado.csv"
RELATORIO_SANEAMENTO = PASTA_SILVER / "relatorio_saneamento_csv.txt"

SUFIXOS_GERACIONAIS = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv"}

# Duplas/grupos cujo '&' ou 'x' faz parte do nome oficial e não deve ser quebrado
DUPLAS_OFICIAIS = {
    "simon & garfunkel", "brooks & dunn", "hall & oates", "daryl hall & john oates",
    "tegan and sara", "florence + the machine", "florence and the machine",
    "mumford & sons", "of monsters and men", "earth, wind & fire",
    "kool & the gang", "sly & the family stone", "ike & tina turner",
    "sonny & cher", "captain & tennille", "ashford & simpson",
    "chloe x halle", "silk sonic", "twenty one pilots", "daft punk",
    "the chainsmokers", "disclosure", "justice", "chromeo",
    "macklemore & ryan lewis", "dan + shay", "sugarland", "lady antebellum",
    "the civil wars", "alison krauss & union station", "chick corea & bela fleck"
}

CONECTORES_PARCERIA = re.compile(
    r"\s+(?:feat\.?|featuring|with|duet with|vs\.?|x|&|\+)\s+",
    flags=re.IGNORECASE
)

def normalizar_linha_bruta(linha: str) -> str:
    """
    Remove o lixo '; ; ; ;' ao final das linhas (artefato de exportação do Excel)
    e desembrulha linhas inteiras que vieram entre aspas:
        "1,1958,...,False";;;;;;   ->   1,1958,...,False  (com "" -> ")
    """
    l = linha.rstrip("\r\n").rstrip()
    l = re.sub(r"[;\s]+$", "", l)
    if len(l) >= 2 and l.startswith('"') and l.endswith('"'):
        interior = l[1:-1]
        # só desembrulha se parecer uma linha inteira (começa com índice numérico + vírgula)
        if re.match(r"^\d*,", interior):
            l = interior.replace('""', '"')
    return l

def reconstruir_linhas_quebradas(caminho_csv: Path) -> pd.DataFrame:
    """
    Lê o CSV bruto reconstruindo registros quebrados por aspas desbalanceadas
    ou vírgulas extras em campos de texto livre (ex.: 'Nominee' / 'Workers').
    """
    with open(caminho_csv, "r", encoding="utf-8", errors="replace") as f:
        linhas_brutas = f.readlines()

    cabecalho = [c.strip() for c in next(csv.reader([normalizar_linha_bruta(linhas_brutas[0].lstrip("\ufeff"))]))]
    num_colunas = len(cabecalho)

    registros_unificados = []
    buffer = ""
    for linha in linhas_brutas[1:]:
        trecho = normalizar_linha_bruta(linha)
        if not trecho.strip():
            continue
        buffer = (buffer + " " + trecho).strip() if buffer else trecho
        if buffer.count('"') % 2 == 0:
            registros_unificados.append(buffer)
            buffer = ""
    if buffer:
        registros_unificados.append(buffer + '"')

    colunas_lower = [c.lower() for c in cabecalho]
    if "nominee" in colunas_lower:
        idx_texto = colunas_lower.index("nominee")
    elif "workers" in colunas_lower:
        idx_texto = colunas_lower.index("workers")
    else:
        idx_texto = num_colunas - 2 if colunas_lower[-1] in ("winner", "img", "url") else num_colunas - 1

    linhas_limpas = []
    reparadas = 0

    for reg in registros_unificados:
        try:
            campos = next(csv.reader([reg]))
        except csv.Error:
            campos = next(csv.reader([reg.replace('"', "")]))

        if len(campos) == num_colunas:
            linhas_limpas.append([c.strip() for c in campos])
        elif len(campos) > num_colunas:
            excesso = len(campos) - num_colunas
            inicio = campos[:idx_texto]
            meio_unido = ", ".join(c.strip() for c in campos[idx_texto : idx_texto + excesso + 1])
            fim = campos[idx_texto + excesso + 1 :]
            nova_linha = [c.strip() for c in (inicio + [meio_unido] + fim)]
            if len(nova_linha) == num_colunas:
                linhas_limpas.append(nova_linha)
                reparadas += 1

    df = pd.DataFrame(linhas_limpas, columns=cabecalho)
    df.attrs["linhas_reparadas"] = reparadas
    return df

def limpar_titulo_obra(work_str: str) -> str:
    """Remove sufixos de participação '(feat. ...)' do título da obra."""
    if not work_str or pd.isna(work_str):
        return ""
    limpo = re.sub(r"\((?:feat\.?|featuring|with)[^()]*\)", "", str(work_str), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", limpo).strip()

def extrair_artista_principal(nominee_str: str) -> str:
    """
    Isola o primeiro artista principal válido, separando colaborações
    e preservando duplas oficiais e sufixos geracionais ('Jr.', 'III').
    """
    if not nominee_str or pd.isna(nominee_str):
        return ""
    primeiro_bloco = str(nominee_str).split(";")[0].strip()
    sem_parenteses = re.sub(r"\([^()]*\)", "", primeiro_bloco).strip()

    if "," in sem_parenteses:
        esq, dir_txt = sem_parenteses.rsplit(",", 1)
        if dir_txt.strip().lower() in SUFIXOS_GERACIONAIS:
            base = f"{esq.strip()}, {dir_txt.strip()}"
        else:
            base = esq.strip()
    else:
        base = sem_parenteses

    if base.lower() in DUPLAS_OFICIAIS:
        return base

    partes = CONECTORES_PARCERIA.split(base)
    return partes[0].strip() if partes else base

def sanear_dataset():
    if not CSV_BRUTO.exists():
        raise FileNotFoundError(f"Arquivo bruto não encontrado: {CSV_BRUTO}")

    df = reconstruir_linhas_quebradas(CSV_BRUTO)
    total_inicial = len(df)
    reparadas = df.attrs.get("linhas_reparadas", 0)

    # Padroniza nomes das colunas (incluindo Ceremony)
    mapa_renomear = {}
    for col in df.columns:
        c_low = col.lower().strip()
        if c_low in ("year", "edicao"):
            mapa_renomear[col] = "Year"
        elif c_low in ("grammy award", "ceremony", "cerimonia", "edition", "edicao_nome"):
            mapa_renomear[col] = "Ceremony"
        elif c_low in ("category", "award name", "categoria"):
            mapa_renomear[col] = "Award Name"
        elif c_low in ("work", "obra"):
            mapa_renomear[col] = "Work"
        elif c_low == "nominee":
            mapa_renomear[col] = "Nominee"
        elif c_low == "workers":
            mapa_renomear[col] = "Workers"
        elif c_low.strip("; ") in ("winner", "venceu"):
            mapa_renomear[col] = "Winner"
    df = df.rename(columns=mapa_renomear)

    df = df.replace(r"^\s*$", pd.NA, regex=True)

    # 1. Valida ano numérico e intervalo real (1958-2024)
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Year", "Award Name"])
    df["Year"] = df["Year"].astype(int)
    df = df[(df["Year"] >= 1958) & (df["Year"] <= 2024)].copy()

    # 2. Remove categorias individuais (sem obra)
    antes_work = len(df)
    df = df.dropna(subset=["Work", "Nominee"]).copy()
    removidas_sem_obra = antes_work - len(df)

    # 3. Limpa espaços nas colunas textuais e remove '(feat. ...)' dos títulos das obras
    for col in ["Ceremony", "Award Name", "Work", "Nominee"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    df["Work"] = df["Work"].apply(limpar_titulo_obra)

    # 4. Extrai artista principal
    df["Artista_Principal"] = df["Nominee"].apply(extrair_artista_principal)
    df = df[df["Artista_Principal"].str.len() > 1]

    # 5. Padroniza coluna booleana 'Winner'
    if "Winner" not in df.columns:
        raise ValueError(f"Coluna Winner não encontrada. Colunas: {list(df.columns)}")
    VERDADEIROS = {"true", "1", "1.0", "yes", "y", "sim", "s", "winner", "vencedor", "venceu"}
    df["Winner"] = df["Winner"].astype(str).str.strip().str.strip(";").str.lower().isin(VERDADEIROS)
    if not df["Winner"].any():
        raise ValueError("Nenhum vencedor detectado: verifique a coluna Winner no CSV bruto.")

    # 6. Remove duplicatas exatas
    antes_dedup = len(df)
    df = df.drop_duplicates(subset=["Year", "Award Name", "Work", "Nominee"]).copy()
    duplicadas_removidas = antes_dedup - len(df)

    # 7. Mantém apenas as colunas úteis para o banco relacional (incluindo Ceremony)
    colunas_uteis = ["Year", "Ceremony", "Award Name", "Work", "Nominee", "Winner", "Artista_Principal"]
    df = df[[c for c in colunas_uteis if c in df.columns]].copy()

    df.to_csv(CSV_SANEADO, index=False, encoding="utf-8")

    resumo = [
        "=== RELATÓRIO DE SANEAMENTO DO CSV (RAW -> SILVER) ===",
        f"Arquivo de origem                  : {CSV_BRUTO.name}",
        f"Registros reconstruídos do bruto   : {total_inicial} ({reparadas} linhas reparadas)",
        f"Removidos (categorias sem obra)    : {removidas_sem_obra}",
        f"Removidos (duplicatas exatas)      : {duplicadas_removidas}",
        f"Colunas mantidas                   : {', '.join(df.columns)}",
        f"Total final de registros saneados  : {len(df)}",
        f"Vencedores (Winner=True)           : {int(df['Winner'].sum())}",
        f"Intervalo de edições               : {df['Year'].min()} a {df['Year'].max()}",
        f"Arquivo gerado                     : {CSV_SANEADO}",
    ]

    texto_relatorio = "\n".join(resumo)
    print("\n" + texto_relatorio)
    with open(RELATORIO_SANEAMENTO, "w", encoding="utf-8") as f:
        f.write(texto_relatorio + "\n")

if __name__ == "__main__":
    sanear_dataset()