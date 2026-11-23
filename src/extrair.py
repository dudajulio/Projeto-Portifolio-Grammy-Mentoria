from pathlib import Path
from collections import Counter
import unicodedata
import pandas as pd
import requests
import json
import time
import re

# ==============================================================================
# CONFIGURAÇÕES E CAMINHOS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "src" else Path(__file__).resolve().parent
PASTA_RAW = BASE_DIR / "data" / "raw"
PASTA_BRONZE = BASE_DIR / "data" / "bronze"
PASTA_SILVER = BASE_DIR / "data" / "silver"

PASTA_BRONZE.mkdir(parents=True, exist_ok=True)
PASTA_SILVER.mkdir(parents=True, exist_ok=True)

# Caches Bronze (somente leitura para não sobrescrever os originais)
CACHE_ENTIDADES_PATH = PASTA_BRONZE / "cache_entidades_v2.json"
CACHE_OBRAS_PATH = PASTA_BRONZE / "cache_obras_v2.json"

# Cache auxiliar novo na Silver (para retomada rápida sem perder progresso)
CACHE_NOVO_ENT_PATH = PASTA_SILVER / "cache_novas_entidades.json"
CACHE_NOVO_OBRAS_PATH = PASTA_SILVER / "cache_novas_obras.json"

# Novos arquivos consolidados na camada Silver
SAIDA_ARTISTAS_PATH = PASTA_SILVER / "artistas_tratados.json"
SAIDA_ALBUNS_PATH = PASTA_SILVER / "albuns_tratados.json"
SAIDA_FAIXAS_PATH = PASTA_SILVER / "faixas_tratadas.json"
SAIDA_INDICACOES_PATH = PASTA_SILVER / "grammy_silver_tratado.json"

LIMITE_ALBUNS = 250
LIMITE_FAIXAS = 250
ANOS_MIN_MAX = (1958, 2024)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "GrammyDataPipeline/2.0 (mariaeduardajuliosantos@gmail.com)"
})

SUFIXOS_GERACIONAIS = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv"}

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

PAPEIS_PROIBIDOS = {
    "composer", "composers", "lyricist", "lyricists", "songwriter", "songwriters",
    "producer", "producers", "executive producer", "co-producer", "vocal producer",
    "engineer", "engineers", "mixing engineer", "mastering engineer", "recording engineer",
    "artist", "artists", "featured artist", "various artists", "unknown", "n/a", "none",
    "arranger", "conductor", "soloist", "performer", "remixer", "art director"
}

# ==============================================================================
# FUNÇÕES UTILITÁRIAS E PARSE DE CRÉDITOS / PARCERIAS / CERIMÔNIA
# ==============================================================================
def normalizar(texto: str) -> str:
    if not texto or pd.isna(texto):
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().strip().split())

def carregar_json(caminho: Path) -> dict:
    if caminho.exists():
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_json(caminho: Path, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def detectar_csv() -> Path:
    for candidato in [
        PASTA_SILVER / "grammy_saneado.csv",
        PASTA_RAW / "grammy_saneado.csv",
        PASTA_RAW / "grammy_limpo.csv",
        PASTA_RAW / "grammy.csv",
    ]:
        if candidato.exists():
            return candidato
    raise FileNotFoundError("Nenhum arquivo CSV encontrado em data/silver ou data/raw.")

def extrair_numero_edicao(ceremony_str: str, ano_fallback: int) -> int:
    if ceremony_str and not pd.isna(ceremony_str):
        m = re.search(r"(\d+)", str(ceremony_str))
        if m:
            return int(m.group(1))
    return 1 if ano_fallback <= 1959 else ano_fallback - 1958

def extrair_ficha_do_nominee(nominee_str: str) -> list[dict]:
    if not nominee_str or pd.isna(nominee_str):
        return []

    creditos = []
    vistos = set()

    def adicionar_credito(nome_bruto: str, funcao_credito: str):
        nome_limpo = nome_bruto.strip(" ,;")
        if not nome_limpo:
            return

        if nome_limpo.lower() in DUPLAS_OFICIAIS:
            candidatos = [nome_limpo]
        else:
            candidatos = CONECTORES_PARCERIA.split(nome_limpo)

        for sub_nome in candidatos:
            n = sub_nome.strip(" ,;")
            n_norm = normalizar(n)
            if n_norm and len(n_norm) >= 2 and n_norm not in PAPEIS_PROIBIDOS:
                chave = (n_norm, funcao_credito)
                if chave not in vistos:
                    creditos.append({
                        "origem": "csv_grammy",
                        "funcao": funcao_credito,
                        "nome": n,
                        "mbid": None
                    })
                    vistos.add(chave)

    for bloco in str(nominee_str).split(";"):
        bloco = bloco.strip()
        if not bloco:
            continue

        funcao_par = None
        for m_par in re.finditer(r"\(([^()]+)\)", bloco):
            conteudo_par = m_par.group(1).strip()
            m_feat = re.match(r"^(?:feat\.?|featuring|with)\s+(.+)$", conteudo_par, flags=re.IGNORECASE)
            if m_feat:
                for convidado in re.split(r",|\s+&\s+|\s+and\s+", m_feat.group(1)):
                    adicionar_credito(convidado, "featured artist")
            else:
                funcao_par = conteudo_par.lower()

        bloco_sem_par = re.sub(r"\([^()]*\)", "", bloco).strip()
        nome_base = bloco_sem_par
        funcao_base = funcao_par or "performer"

        if "," in bloco_sem_par:
            esq, dir_txt = bloco_sem_par.rsplit(",", 1)
            dir_limpo = dir_txt.strip()
            if dir_limpo.lower() in SUFIXOS_GERACIONAIS:
                nome_base = f"{esq.strip()}, {dir_limpo}"
            else:
                nome_base = esq.strip()
                funcao_base = dir_limpo.lower()

        adicionar_credito(nome_base, funcao_base)

    return creditos

def classificar_tipo_obra(categoria: str) -> str:
    cat = normalizar(categoria)
    palavras_album = ["album", "soundtrack", "score", "compilation", "opera", "musical theater"]
    return "Album" if any(p in cat for p in palavras_album) else "Faixa"

# ==============================================================================
# CONSULTAS OTIMIZADAS (CACHE -> MUSICBRAINZ)
# ==============================================================================
def buscar_entidade_mb(nome: str, cache_ent: dict) -> dict | None:
    chave = normalizar(nome)
    if not chave or chave in PAPEIS_PROIBIDOS:
        return None
    if chave in cache_ent:
        return cache_ent[chave] if cache_ent[chave].get("encontrado") else None

    try:
        url = "https://musicbrainz.org/ws/2/artist"
        params = {"query": f'artist:"{nome}"', "fmt": "json", "limit": 1}
        r = SESSION.get(url, params=params, timeout=6)
        time.sleep(1.05)

        if r.status_code == 200:
            artistas = r.json().get("artists", [])
            if artistas:
                melhor = artistas[0]
                life = melhor.get("life-span", {})
                area = melhor.get("area") or {}
                registro = {
                    "encontrado": True,
                    "mbid": melhor.get("id"),
                    "nome_mb": melhor.get("name"),
                    "tipo": melhor.get("type", "Person"),
                    "genero": melhor.get("gender"),
                    "pais": melhor.get("country") or area.get("name"),
                    "inicio": life.get("begin"),
                    "fim": life.get("end"),
                }
                cache_ent[chave] = registro
                return registro
        cache_ent[chave] = {"encontrado": False}
    except Exception:
        pass
    return None

def buscar_obra_completa_mb(
    titulo: str, artista: str, tipo_esperado: str, creditos_csv: list[dict], cache_obras: dict
) -> dict | None:
    chave = f"{normalizar(artista)}|||{normalizar(titulo)}"

    # 1. Reaproveita instantaneamente do cache Bronze ou do cache novo da Silver
    if chave in cache_obras:
        if not cache_obras[chave].get("encontrado"):
            return None

        obra_cache = dict(cache_obras[chave])
        creditos_padronizados = []
        vistos = set()

        for c in obra_cache.get("creditos", []):
            funcao_c = (c.get("funcao") or c.get("papel") or c.get("role") or "contributor").lower()
            nome_c = c.get("nome", "")
            if nome_c:
                item = dict(c)
                item["funcao"] = funcao_c
                creditos_padronizados.append(item)
                vistos.add((normalizar(nome_c), funcao_c))

        for c in creditos_csv:
            funcao_c = (c.get("funcao") or c.get("papel") or "performer").lower()
            chave_c = (normalizar(c["nome"]), funcao_c)
            if chave_c not in vistos:
                creditos_padronizados.append({
                    "origem": "csv_grammy",
                    "funcao": funcao_c,
                    "nome": c["nome"],
                    "mbid": None
                })
                vistos.add(chave_c)

        obra_cache["creditos"] = creditos_padronizados
        cache_obras[chave] = obra_cache

        if tipo_esperado == "Album" or obra_cache.get("duracao_ms"):
            return obra_cache

    # 2. Consulta MusicBrainz (1 chamada de busca + 1 chamada de ficha técnica completa)
    try:
        endpoint = "release-group" if tipo_esperado == "Album" else "recording"
        query = f'{endpoint}:"{titulo}" AND artist:"{artista}"'
        url = f"https://musicbrainz.org/ws/2/{endpoint}"
        params = {"query": query, "fmt": "json", "limit": 3}

        r = SESSION.get(url, params=params, timeout=6)
        time.sleep(1.05)

        if r.status_code != 200:
            return None

        resultados = r.json().get(f"{endpoint}s", [])
        if not resultados:
            cache_obras[chave] = {"encontrado": False}
            return None

        escolhido = resultados[0]
        if tipo_esperado == "Faixa":
            com_duracao = [x for x in resultados if x.get("length")]
            if not com_duracao:
                cache_obras[chave] = {"encontrado": False}
                return None
            escolhido = com_duracao[0]

        mbid = escolhido.get("id")
        duracao_ms = escolhido.get("length") if tipo_esperado == "Faixa" else None
        data_lanc = escolhido.get("first-release-date") or escolhido.get("date")
        generos = [t["name"].title() for t in escolhido.get("tags", [])[:3] if t.get("name")]

        url_detalhe = f"https://musicbrainz.org/ws/2/{endpoint}/{mbid}"
        params_det = {"inc": "artist-rels+work-rels+tags", "fmt": "json"}
        r_det = SESSION.get(url_detalhe, params=params_det, timeout=6)
        time.sleep(1.05)

        creditos_finais = []
        vistos = set()

        for c in creditos_csv:
            funcao_c = (c.get("funcao") or c.get("papel") or "performer").lower()
            chave_c = (normalizar(c["nome"]), funcao_c)
            if chave_c not in vistos:
                creditos_finais.append({
                    "origem": "csv_grammy",
                    "funcao": funcao_c,
                    "nome": c["nome"],
                    "mbid": None
                })
                vistos.add(chave_c)

        if r_det.status_code == 200:
            detalhes = r_det.json()
            if tipo_esperado == "Faixa" and not duracao_ms:
                duracao_ms = detalhes.get("length")

            if not generos:
                generos = [t["name"].title() for t in detalhes.get("tags", [])[:3] if t.get("name")]

            for rel in detalhes.get("relations", []):
                if rel.get("target-type") == "artist" and rel.get("artist"):
                    nome_prof = rel["artist"].get("name", "")
                    funcao = rel.get("type", "contributor").lower()
                    chave_cred = (normalizar(nome_prof), funcao)
                    if normalizar(nome_prof) not in PAPEIS_PROIBIDOS and chave_cred not in vistos:
                        creditos_finais.append({
                            "origem": endpoint,
                            "funcao": funcao,
                            "nome": nome_prof,
                            "mbid": rel["artist"].get("id")
                        })
                        vistos.add(chave_cred)

        if tipo_esperado == "Faixa" and (not duracao_ms or int(duracao_ms) <= 0):
            cache_obras[chave] = {"encontrado": False}
            return None

        registro_obra = {
            "encontrado": True,
            "fonte": "musicbrainz",
            "tipo": tipo_esperado,
            "mbid": mbid,
            "titulo": escolhido.get("title", titulo),
            "duracao_ms": int(duracao_ms) if duracao_ms else None,
            "data_lancamento": data_lanc,
            "gravadora": None,
            "origem_gravadora": None,
            "generos": generos,
            "interpretes": [artista],
            "creditos": creditos_finais
        }
        cache_obras[chave] = registro_obra
        return registro_obra

    except Exception:
        return None

# ==============================================================================
# CRUZAMENTO DE INDICAÇÕES E PIPELINE PRINCIPAL
# ==============================================================================
def cruzar_indicacoes_csv(df: pd.DataFrame, cache_obras_chaves: set) -> list[dict]:
    contagem_artista = Counter(df["artista_principal"])
    vitorias_artista = Counter(df[df["Winner"] == True]["artista_principal"]) if "Winner" in df.columns else Counter()
    obras_agrupadas = {}

    for _, row in df.iterrows():
        ano = int(row["Year"])
        cerimonia_nome = (
            str(row["Ceremony"]).strip()
            if "Ceremony" in df.columns and pd.notna(row["Ceremony"]) and str(row["Ceremony"]).strip()
            else f"{extrair_numero_edicao(None, ano)}th Annual GRAMMY Awards"
        )
        edicao = extrair_numero_edicao(cerimonia_nome, ano)

        categoria = str(row["Award Name"]).strip()
        titulo = str(row["Work"]).strip()
        artista = row["artista_principal"]
        venceu = bool(row["Winner"]) if "Winner" in df.columns and pd.notna(row["Winner"]) else False
        tipo_obra = classificar_tipo_obra(categoria)

        chave_obra = f"{normalizar(artista)}|||{normalizar(titulo)}|||{tipo_obra}"
        chave_cache = f"{normalizar(artista)}|||{normalizar(titulo)}"

        if chave_obra not in obras_agrupadas:
            obras_agrupadas[chave_obra] = {
                "chave_obra": chave_obra,
                "esta_no_cache": 1 if chave_cache in cache_obras_chaves else 0,
                "artista": artista,
                "titulo": titulo,
                "tipo_obra": tipo_obra,
                "score_artista": contagem_artista[artista],
                "vitorias_artista": vitorias_artista[artista],
                "indicacoes": [],
                "creditos_consolidados": [],
                "_vistos_cred": set(),
                "_vistos_ind": set(),
            }

        grupo = obras_agrupadas[chave_obra]

        chave_ind = (edicao, ano, normalizar(categoria))
        if chave_ind not in grupo["_vistos_ind"]:
            grupo["indicacoes"].append({
                "edicao": edicao,
                "cerimonia_nome": cerimonia_nome,
                "ano": ano,
                "categoria": categoria,
                "venceu": venceu
            })
            grupo["_vistos_ind"].add(chave_ind)

        for cred in row["creditos_parsed"]:
            funcao_c = cred.get("funcao", "performer")
            chave_c = (normalizar(cred["nome"]), funcao_c)
            if chave_c not in grupo["_vistos_cred"]:
                grupo["creditos_consolidados"].append(cred)
                grupo["_vistos_cred"].add(chave_c)

    lista_grupos = list(obras_agrupadas.values())
    # Prioriza obras já tratadas no cache + artistas mais indicados + vencedores
    lista_grupos.sort(
        key=lambda g: (
            g["esta_no_cache"],
            g["score_artista"],
            sum(1 for i in g["indicacoes"] if i["venceu"]),
            g["vitorias_artista"],
            len(g["indicacoes"]),
            max(i["ano"] for i in g["indicacoes"])
        ),
        reverse=True
    )
    return lista_grupos

def salvar_arquivos_silver(
    artistas_dict: dict, albuns_dict: dict, faixas_dict: dict, indicacoes_list: list,
    cache_ent_novo: dict, cache_obras_novo: dict
):
    salvar_json(SAIDA_ARTISTAS_PATH, artistas_dict)
    salvar_json(SAIDA_ALBUNS_PATH, albuns_dict)
    salvar_json(SAIDA_FAIXAS_PATH, faixas_dict)
    salvar_json(SAIDA_INDICACOES_PATH, indicacoes_list)
    salvar_json(CACHE_NOVO_ENT_PATH, cache_ent_novo)
    salvar_json(CACHE_NOVO_OBRAS_PATH, cache_obras_novo)

def executar_pipeline():
    t0 = time.time()
    csv_path = detectar_csv()
    print(f"Lendo dataset: {csv_path}")
    df = pd.read_csv(csv_path, engine="python", on_bad_lines="warn")

    col_ano = "Year" if "Year" in df.columns else df.columns[0]
    col_cat = "Award Name" if "Award Name" in df.columns else "Category"
    col_work = "Work" if "Work" in df.columns else "Nominee"
    col_nom = "Nominee" if "Nominee" in df.columns else "Workers"

    df = df.dropna(subset=[col_ano, col_cat, col_work, col_nom]).copy()
    df[col_ano] = pd.to_numeric(df[col_ano], errors="coerce")
    df = df[(df[col_ano] >= ANOS_MIN_MAX[0]) & (df[col_ano] <= ANOS_MIN_MAX[1])]

    df["creditos_parsed"] = df[col_nom].apply(extrair_ficha_do_nominee)
    df = df[df["creditos_parsed"].map(len) > 0].copy()

    if "Artista_Principal" in df.columns:
        df["artista_principal"] = df["Artista_Principal"].fillna(
            df["creditos_parsed"].apply(lambda lst: lst[0]["nome"])
        )
    else:
        df["artista_principal"] = df["creditos_parsed"].apply(lambda lst: lst[0]["nome"])

    # Mescla cache Bronze (somente leitura) + cache novo da Silver
    cache_ent = {**carregar_json(CACHE_ENTIDADES_PATH), **carregar_json(CACHE_NOVO_ENT_PATH)}
    cache_obras = {**carregar_json(CACHE_OBRAS_PATH), **carregar_json(CACHE_NOVO_OBRAS_PATH)}

    chaves_validas_cache = {k for k, v in cache_obras.items() if v.get("encontrado")}
    obras_cruzadas = cruzar_indicacoes_csv(df, chaves_validas_cache)
    print(f"Obras únicas após cruzamento: {len(obras_cruzadas)} ({len(chaves_validas_cache)} já em cache)")

    artistas_silver = {}
    albuns_silver = {}
    faixas_silver = {}
    registros_silver = []

    descartados = 0
    print(f"Processando até {LIMITE_ALBUNS} álbuns e {LIMITE_FAIXAS} faixas completas...")

    for grupo in obras_cruzadas:
        if len(albuns_silver) >= LIMITE_ALBUNS and len(faixas_silver) >= LIMITE_FAIXAS:
            break

        tipo_obra = grupo["tipo_obra"]
        chave_obra = grupo["chave_obra"]

        if tipo_obra == "Album" and len(albuns_silver) >= LIMITE_ALBUNS:
            continue
        if tipo_obra == "Faixa" and len(faixas_silver) >= LIMITE_FAIXAS:
            continue

        artista = grupo["artista"]
        titulo_obra = grupo["titulo"]
        creditos_csv = grupo["creditos_consolidados"]

        entidade = buscar_entidade_mb(artista, cache_ent)
        if not entidade:
            descartados += 1
            continue

        obra = buscar_obra_completa_mb(titulo_obra, artista, tipo_obra, creditos_csv, cache_obras)
        if not obra:
            descartados += 1
            continue

        artistas_silver[normalizar(artista)] = entidade

        # Aproveita dados do cache para todos os profissionais da ficha técnica (sem fazer 15 requisições extras por música)
        for cred in obra.get("creditos", []):
            nome_prof = cred.get("nome", "")
            chave_prof = normalizar(nome_prof)
            if not chave_prof or chave_prof in artistas_silver:
                continue

            if chave_prof in cache_ent and cache_ent[chave_prof].get("encontrado"):
                artistas_silver[chave_prof] = cache_ent[chave_prof]
            else:
                artistas_silver[chave_prof] = {
                    "encontrado": True,
                    "mbid": cred.get("mbid"),
                    "nome_mb": nome_prof,
                    "tipo": "Person",
                    "genero": None,
                    "pais": None,
                    "inicio": cred.get("nasc"),
                    "fim": cred.get("falec"),
                }

        if tipo_obra == "Album":
            albuns_silver[chave_obra] = obra
        else:
            faixas_silver[chave_obra] = obra

        for ind in grupo["indicacoes"]:
            registros_silver.append({
                "edicao": ind["edicao"],
                "cerimonia_nome": ind["cerimonia_nome"],
                "ano": ind["ano"],
                "categoria": ind["categoria"],
                "venceu": ind["venceu"],
                "chave_artista": normalizar(artista),
                "chave_obra": chave_obra,
                "artista_principal": entidade,
                "obra": obra
            })

        total_obras = len(albuns_silver) + len(faixas_silver)
        if total_obras % 10 == 0:
            salvar_arquivos_silver(
                artistas_silver, albuns_silver, faixas_silver, registros_silver, cache_ent, cache_obras
            )
            elapsed = int(time.time() - t0)
            print(
                f"[{elapsed}s] Álbuns: {len(albuns_silver)}/{LIMITE_ALBUNS} | "
                f"Faixas: {len(faixas_silver)}/{LIMITE_FAIXAS} | "
                f"Artistas: {len(artistas_silver)} | Indicações: {len(registros_silver)}"
            )

    salvar_arquivos_silver(
        artistas_silver, albuns_silver, faixas_silver, registros_silver, cache_ent, cache_obras
    )

    print("\n=== RESUMO FINAL DOS NOVOS ARQUIVOS SILVER ===")
    print(f"Tempo total              : {int(time.time() - t0)}s")
    print(f"Artistas únicos tratados : {len(artistas_silver)} -> {SAIDA_ARTISTAS_PATH}")
    print(f"Álbuns únicos aprovados  : {len(albuns_silver)}/{LIMITE_ALBUNS} -> {SAIDA_ALBUNS_PATH}")
    print(f"Faixas únicas aprovadas  : {len(faixas_silver)}/{LIMITE_FAIXAS} -> {SAIDA_FAIXAS_PATH}")
    print(f"Indicações cruzadas      : {len(registros_silver)} -> {SAIDA_INDICACOES_PATH}")
    print(f"Obras descartadas        : {descartados}")

if __name__ == "__main__":
    executar_pipeline()