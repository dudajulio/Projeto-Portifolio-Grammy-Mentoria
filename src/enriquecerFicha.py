from pathlib import Path
from collections import defaultdict
import unicodedata
import requests
import json
import time
import re

# ==============================================================================
# CONFIGURAÇÕES E CAMINHOS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "src" else Path(__file__).resolve().parent
PASTA_SILVER = BASE_DIR / "data" / "silver"

ARTISTAS_PATH = PASTA_SILVER / "artistas_tratados.json"
ALBUNS_PATH = PASTA_SILVER / "albuns_tratados.json"
FAIXAS_PATH = PASTA_SILVER / "faixas_tratadas.json"
INDICACOES_PATH = PASTA_SILVER / "grammy_silver_tratado.json"
CACHE_NOVO_ENT_PATH = PASTA_SILVER / "cache_novas_entidades.json"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "GrammyDataPipeline/2.0 (contato@projetoacademico.edu.br)"
})

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
OPENOPUS_API = "https://api.openopus.org"

GENERO_WD = {
    "Q6581097": "Male",
    "Q6581072": "Female",
    "Q1097630": "Non-binary",
    "Q1052281": "Female",
    "Q2449503": "Male",
}

MAPA_GENERO_CATEGORIA = {
    "pop": "Pop",
    "rock": "Rock",
    "r&b": "R&B",
    "rap": "Hip Hop",
    "hip hop": "Hip Hop",
    "country": "Country",
    "jazz": "Jazz",
    "classical": "Classical",
    "opera": "Classical",
    "orchestral": "Classical",
    "chamber music": "Classical",
    "electronic": "Electronic",
    "dance": "Dance",
    "latin": "Latin",
    "metal": "Metal",
    "alternative": "Alternative",
    "folk": "Folk",
    "blues": "Blues",
    "gospel": "Gospel",
    "christian": "Christian",
    "reggae": "Reggae",
    "soul": "Soul",
    "soundtrack": "Soundtrack",
    "americana": "Americana",
    "bluegrass": "Bluegrass",
    "world music": "World",
    "global music": "World",
    "african": "African",
}

PAPEIS_PROIBIDOS = {
    "composer", "composers", "lyricist", "lyricists", "songwriter", "songwriters",
    "producer", "producers", "executive producer", "co-producer", "vocal producer",
    "engineer", "engineers", "mixing engineer", "mastering engineer", "recording engineer",
    "artist", "artists", "featured artist", "various artists", "unknown", "n/a", "none",
    "arranger", "conductor", "soloist", "performer", "remixer", "art director"
}

def normalizar(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().strip().split())

def carregar_json(caminho: Path):
    if caminho.exists():
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_json(caminho: Path, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# ==============================================================================
# 1. COMPLEMENTO DE FICHA TÉCNICA NAS OBRAS (PRODUTORES, COMPOSITORES, TÉCNICOS)
# ==============================================================================
def completar_ficha_tecnica_obra(obra: dict, artistas: dict) -> list[dict]:
    """
    Se a faixa ou álbum tiver poucos créditos técnicos, consulta as relações
    de gravação/álbum e de composição (work-rels) no MusicBrainz pelo MBID da obra.
    """
    mbid_obra = obra.get("mbid")
    tipo_obra = obra.get("tipo", "Faixa")
    creditos_atuais = list(obra.get("creditos") or [])

    if not mbid_obra or str(mbid_obra).startswith("openopus") or len(creditos_atuais) >= 3:
        return creditos_atuais

    vistos = {
        (normalizar(c.get("nome", "")), (c.get("funcao") or "contributor").lower())
        for c in creditos_atuais
    }

    try:
        endpoint = "release-group" if tipo_obra == "Album" else "recording"
        url = f"https://musicbrainz.org/ws/2/{endpoint}/{mbid_obra}"
        r = SESSION.get(url, params={"inc": "artist-rels+work-rels", "fmt": "json"}, timeout=6)
        time.sleep(1.05)

        if r.status_code == 200:
            detalhes = r.json()
            for rel in detalhes.get("relations", []):
                if rel.get("target-type") == "artist" and rel.get("artist"):
                    nome_prof = rel["artist"].get("name", "")
                    funcao = rel.get("type", "contributor").lower()
                    chave_c = (normalizar(nome_prof), funcao)
                    if normalizar(nome_prof) and normalizar(nome_prof) not in PAPEIS_PROIBIDOS and chave_c not in vistos:
                        creditos_atuais.append({
                            "origem": endpoint,
                            "funcao": funcao,
                            "nome": nome_prof,
                            "mbid": rel["artist"].get("id")
                        })
                        vistos.add(chave_c)
                        chave_art = normalizar(nome_prof)
                        if chave_art not in artistas:
                            artistas[chave_art] = {
                                "encontrado": True,
                                "pendente_enriquecimento": True,
                                "mbid": rel["artist"].get("id"),
                                "nome_mb": nome_prof,
                                "tipo": "Person",
                                "genero": None,
                                "pais": None,
                                "inicio": None,
                                "fim": None,
                            }

                elif rel.get("target-type") == "work" and rel.get("work"):
                    for w_rel in rel["work"].get("relations", []):
                        if w_rel.get("target-type") == "artist" and w_rel.get("artist"):
                            nome_comp = w_rel["artist"].get("name", "")
                            funcao_w = w_rel.get("type", "composer").lower()
                            chave_w = (normalizar(nome_comp), funcao_w)
                            if normalizar(nome_comp) and normalizar(nome_comp) not in PAPEIS_PROIBIDOS and chave_w not in vistos:
                                creditos_atuais.append({
                                    "origem": "work",
                                    "funcao": funcao_w,
                                    "nome": nome_comp,
                                    "mbid": w_rel["artist"].get("id")
                                })
                                vistos.add(chave_w)
                                chave_art = normalizar(nome_comp)
                                if chave_art not in artistas:
                                    artistas[chave_art] = {
                                        "encontrado": True,
                                        "pendente_enriquecimento": True,
                                        "mbid": w_rel["artist"].get("id"),
                                        "nome_mb": nome_comp,
                                        "tipo": "Person",
                                        "genero": None,
                                        "pais": None,
                                        "inicio": None,
                                        "fim": None,
                                    }
    except Exception:
        pass

    return creditos_atuais

# ==============================================================================
# 2. ENRIQUECIMENTO DE GÊNEROS MUSICAIS NAS FAIXAS E ÁLBUNS
# ==============================================================================
def inferir_genero_por_categorias(categorias: list[str]) -> list[str]:
    encontrados = []
    for cat in categorias:
        cat_low = cat.lower()
        for palavra, genero in MAPA_GENERO_CATEGORIA.items():
            if re.search(rf"\b{re.escape(palavra)}\b", cat_low) and genero not in encontrados:
                encontrados.append(genero)
    return encontrados

def buscar_generos_artista_mb(mbid: str, cache_generos_artista: dict) -> list[str]:
    if not mbid or str(mbid).startswith("openopus"):
        return []
    if mbid in cache_generos_artista:
        return cache_generos_artista[mbid]

    generos = []
    try:
        r = SESSION.get(
            f"https://musicbrainz.org/ws/2/artist/{mbid}",
            params={"inc": "tags+genres", "fmt": "json"},
            timeout=6
        )
        time.sleep(1.05)
        if r.status_code == 200:
            data = r.json()
            lista_g = data.get("genres") or data.get("tags") or []
            lista_ordenada = sorted(lista_g, key=lambda x: x.get("count", 0), reverse=True)
            generos = [g["name"].title() for g in lista_ordenada[:3] if g.get("name")]
    except Exception:
        pass

    cache_generos_artista[mbid] = generos
    return generos

# ==============================================================================
# 3. ENRIQUECIMENTO EM LOTE VIA WIKIDATA + OPEN OPUS + MUSICBRAINZ
# ==============================================================================
def buscar_qid_wikidata(nome: str) -> str | None:
    try:
        params = {
            "action": "wbsearchentities",
            "search": nome,
            "language": "en",
            "type": "item",
            "limit": 3,
            "format": "json"
        }
        r = SESSION.get(WIKIDATA_API, params=params, timeout=6)
        if r.status_code == 200:
            palavras_chave = (
                "musician", "singer", "producer", "composer", "songwriter",
                "engineer", "record", "band", "rapper", "conductor", "pianist",
                "guitarist", "drummer", "arranger", "artist"
            )
            for item in r.json().get("search", []):
                desc = item.get("description", "").lower()
                if any(p in desc for p in palavras_chave):
                    return item.get("id")
            resultados = r.json().get("search", [])
            if resultados:
                return resultados[0].get("id")
    except Exception:
        pass
    return None

def enriquecer_lote_wikidata(qids: list[str]) -> dict[str, dict]:
    resultado = {}
    if not qids:
        return resultado

    try:
        params = {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "claims|labels",
            "languages": "en|pt",
            "format": "json"
        }
        r = SESSION.get(WIKIDATA_API, params=params, timeout=10)
        if r.status_code != 200:
            return resultado

        entities = r.json().get("entities", {})
        paises_qids = set()
        dados_brutos = {}

        for qid, ent in entities.items():
            claims = ent.get("claims", {})
            instancias = [
                c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                for c in claims.get("P31", [])
            ]
            tipo = "Person" if "Q5" in instancias else ("Group" if instancias else "Person")

            genero = None
            for c in claims.get("P21", []):
                g_id = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                if g_id in GENERO_WD:
                    genero = GENERO_WD[g_id]
                    break

            inicio = None
            for prop_ini in ("P569", "P571"):
                if prop_ini in claims:
                    t_val = claims[prop_ini][0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
                    m = re.match(r"^[+-]?(\d{4}-\d{2}-\d{2})", t_val)
                    if m:
                        inicio = m.group(1).replace("-00-00", "-01-01")
                        break

            fim = None
            for prop_fim in ("P570", "P576"):
                if prop_fim in claims:
                    t_val = claims[prop_fim][0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
                    m = re.match(r"^[+-]?(\d{4}-\d{2}-\d{2})", t_val)
                    if m:
                        fim = m.group(1).replace("-00-00", "-01-01")
                        break

            pais_qid = None
            for prop_pais in ("P27", "P495"):
                if prop_pais in claims:
                    pais_qid = claims[prop_pais][0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                    if pais_qid:
                        paises_qids.add(pais_qid)
                        break

            dados_brutos[qid] = {
                "tipo": tipo,
                "genero": genero,
                "inicio": inicio,
                "fim": fim,
                "pais_qid": pais_qid
            }

        nomes_paises = {}
        if paises_qids:
            r_p = SESSION.get(
                WIKIDATA_API,
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(list(paises_qids)[:50]),
                    "props": "labels",
                    "languages": "en",
                    "format": "json"
                },
                timeout=8
            )
            if r_p.status_code == 200:
                for p_id, p_ent in r_p.json().get("entities", {}).items():
                    nomes_paises[p_id] = p_ent.get("labels", {}).get("en", {}).get("value")

        for qid, info in dados_brutos.items():
            resultado[qid] = {
                "tipo": info["tipo"],
                "genero": info["genero"],
                "pais": nomes_paises.get(info["pais_qid"]),
                "inicio": info["inicio"],
                "fim": info["fim"],
            }

    except Exception:
        pass
    return resultado

def buscar_open_opus_compositor(nome: str) -> dict | None:
    try:
        termo = requests.utils.quote(nome)
        r = SESSION.get(f"{OPENOPUS_API}/composer/list/search/{termo}.json", timeout=5)
        if r.status_code == 200:
            comps = r.json().get("composers", [])
            if comps:
                c = comps[0]
                return {
                    "nome_mb": c.get("complete_name") or c.get("name"),
                    "tipo": "Person",
                    "genero": None,
                    "pais": None,
                    "inicio": c.get("birth"),
                    "fim": c.get("death"),
                    "fonte_extra": "open_opus"
                }
    except Exception:
        pass
    return None

def buscar_mb_por_id(mbid: str) -> dict | None:
    if not mbid or str(mbid).startswith("openopus"):
        return None
    try:
        r = SESSION.get(f"https://musicbrainz.org/ws/2/artist/{mbid}", params={"fmt": "json"}, timeout=6)
        time.sleep(1.05)
        if r.status_code == 200:
            melhor = r.json()
            life = melhor.get("life-span", {})
            area = melhor.get("area") or {}
            return {
                "mbid": melhor.get("id"),
                "nome_mb": melhor.get("name"),
                "tipo": melhor.get("type", "Person"),
                "genero": melhor.get("gender"),
                "pais": melhor.get("country") or area.get("name"),
                "inicio": life.get("begin"),
                "fim": life.get("end"),
            }
    except Exception:
        pass
    return None

def propagar_creditos_completos_na_obra(obra: dict, artistas: dict):
    """
    Garante que TODOS os produtores, compositores e profissionais técnicos
    listados em obra['creditos'] estejam cadastrados em artistas_tratados.json
    e recebam seus dados pessoais completos diretamente dentro da obra.
    """
    creditos_enriquecidos = []
    for cred in obra.get("creditos") or []:
        nome_prof = cred.get("nome", "")
        chave_prof = normalizar(nome_prof)
        funcao_prof = (cred.get("funcao") or cred.get("papel") or "contributor").lower()

        if not chave_prof or chave_prof in PAPEIS_PROIBIDOS:
            continue

        info_ent = artistas.get(chave_prof, {})
        item_completo = {
            "chave_artista": chave_prof,
            "origem": cred.get("origem", "csv_grammy"),
            "funcao": funcao_prof,
            "nome": info_ent.get("nome_mb") or nome_prof,
            "mbid": info_ent.get("mbid") or cred.get("mbid"),
            "tipo": info_ent.get("tipo", "Person"),
            "genero": info_ent.get("genero"),
            "pais": info_ent.get("pais"),
            "inicio": info_ent.get("inicio") or cred.get("nasc"),
            "fim": info_ent.get("fim") or cred.get("falec"),
        }
        creditos_enriquecidos.append(item_completo)

    obra["creditos"] = creditos_enriquecidos

# ==============================================================================
# PIPELINE PRINCIPAL
# ==============================================================================
def executar_enriquecimento():
    t0 = time.time()
    artistas = carregar_json(ARTISTAS_PATH)
    albuns = carregar_json(ALBUNS_PATH)
    faixas = carregar_json(FAIXAS_PATH)
    indicacoes = carregar_json(INDICACOES_PATH)
    cache_ent = carregar_json(CACHE_NOVO_ENT_PATH)

    if not artistas:
        raise FileNotFoundError("Execute primeiro o script src/extrair.py!")

    # --------------------------------------------------------------------------
    # PARTE 1: GARANTIR QUE TODAS AS FAIXAS E ÁLBUNS TENHAM A FICHA TÉCNICA COMPLETA
    # --------------------------------------------------------------------------
    print("1) Verificando e completando produtores, compositores e técnicos nas faixas e álbuns...")
    for dicionario_obras in (faixas, albuns):
        for chave_obra, obra in dicionario_obras.items():
            obra["creditos"] = completar_ficha_tecnica_obra(obra, artistas)
            for cred in obra["creditos"]:
                chave_prof = normalizar(cred.get("nome", ""))
                if chave_prof and chave_prof not in PAPEIS_PROIBIDOS and chave_prof not in artistas:
                    artistas[chave_prof] = {
                        "encontrado": True,
                        "pendente_enriquecimento": True,
                        "mbid": cred.get("mbid"),
                        "nome_mb": cred.get("nome"),
                        "tipo": "Person",
                        "genero": None,
                        "pais": None,
                        "inicio": cred.get("nasc"),
                        "fim": cred.get("falec"),
                    }

    # --------------------------------------------------------------------------
    # PARTE 2: ENRIQUECER TODOS OS ARTISTAS, PRODUTORES, COMPOSITORES E TÉCNICOS
    # --------------------------------------------------------------------------
    pendentes = [
        (chave, dados)
        for chave, dados in artistas.items()
        if dados.get("pendente_enriquecimento") or (not dados.get("pais") and not dados.get("inicio"))
    ]
    print(f"2) Enriquecendo {len(pendentes)} artistas/produtores/compositores/técnicos...")

    com_mbid = [(c, d) for c, d in pendentes if d.get("mbid")]
    for idx, (chave, dados) in enumerate(com_mbid, 1):
        info_mb = buscar_mb_por_id(dados["mbid"])
        if info_mb:
            dados.update(info_mb)
            dados.pop("pendente_enriquecimento", None)
            artistas[chave] = dados
            cache_ent[chave] = dados
        if idx % 25 == 0:
            salvar_json(ARTISTAS_PATH, artistas)
            salvar_json(CACHE_NOVO_ENT_PATH, cache_ent)
            print(f"   [{int(time.time() - t0)}s] MBIDs resolvidos: {idx}/{len(com_mbid)}")

    ainda_pendentes = [
        (chave, dados)
        for chave, dados in artistas.items()
        if dados.get("pendente_enriquecimento") or (not dados.get("pais") and not dados.get("inicio"))
    ]

    mapa_chave_qid = {}
    for idx, (chave, dados) in enumerate(ainda_pendentes, 1):
        nome = dados.get("nome_mb") or chave
        oo = buscar_open_opus_compositor(nome)
        if oo and oo.get("inicio"):
            dados.update(oo)
            dados.pop("pendente_enriquecimento", None)
            artistas[chave] = dados
            cache_ent[chave] = dados
            continue

        qid = buscar_qid_wikidata(nome)
        if qid:
            mapa_chave_qid[chave] = qid

        if idx % 50 == 0:
            print(f"   [{int(time.time() - t0)}s] QIDs Wikidata localizados: {len(mapa_chave_qid)}/{idx}")

    lista_pares = list(mapa_chave_qid.items())
    for i in range(0, len(lista_pares), 50):
        bloco = lista_pares[i : i + 50]
        detalhes_lote = enriquecer_lote_wikidata([qid for _, qid in bloco])

        for chave, qid in bloco:
            if qid in detalhes_lote:
                info_wd = detalhes_lote[qid]
                for campo in ("tipo", "genero", "pais", "inicio", "fim"):
                    if info_wd.get(campo) and not artistas[chave].get(campo):
                        artistas[chave][campo] = info_wd[campo]
            artistas[chave].pop("pendente_enriquecimento", None)
            cache_ent[chave] = artistas[chave]

    for chave, dados in artistas.items():
        dados.pop("pendente_enriquecimento", None)

    # --------------------------------------------------------------------------
    # PARTE 3: PREENCHER GÊNEROS NAS FAIXAS/ÁLBUNS E PROPAGAR CRÉDITOS COMPLETOS
    # --------------------------------------------------------------------------
    print("3) Preenchendo gêneros nas faixas/álbuns e propagando ficha técnica completa...")
    categorias_por_obra = defaultdict(list)
    artista_por_obra = {}

    for reg in indicacoes:
        c_obra = reg.get("chave_obra")
        if c_obra:
            categorias_por_obra[c_obra].append(reg.get("categoria", ""))
            artista_por_obra[c_obra] = reg.get("chave_artista")

    cache_generos_art = {}
    for dicionario_obras in (faixas, albuns):
        for chave_obra, obra in dicionario_obras.items():
            generos_atuais = [g for g in (obra.get("generos") or []) if g]

            if not generos_atuais:
                generos_cat = inferir_genero_por_categorias(categorias_por_obra.get(chave_obra, []))
                if generos_cat:
                    generos_atuais = generos_cat

            if not generos_atuais:
                c_art = artista_por_obra.get(chave_obra)
                mbid_art = artistas.get(c_art, {}).get("mbid") if c_art else None
                generos_art = buscar_generos_artista_mb(mbid_art, cache_generos_art)
                if generos_art:
                    generos_atuais = generos_art

            if not generos_atuais:
                generos_atuais = ["Pop"]

            obra["generos"] = generos_atuais

            # Propaga os dados enriquecidos de todos os produtores, compositores e técnicos
            propagar_creditos_completos_na_obra(obra, artistas)

    # Propaga tanto o artista principal quanto a obra com toda a ficha técnica para grammy_silver_tratado.json
    for reg in indicacoes:
        c_art = reg.get("chave_artista")
        c_obra = reg.get("chave_obra")
        if c_art in artistas:
            reg["artista_principal"] = artistas[c_art]
        if c_obra in faixas:
            reg["obra"] = faixas[c_obra]
        elif c_obra in albuns:
            reg["obra"] = albuns[c_obra]

    salvar_json(ARTISTAS_PATH, artistas)
    salvar_json(FAIXAS_PATH, faixas)
    salvar_json(ALBUNS_PATH, albuns)
    salvar_json(INDICACOES_PATH, indicacoes)
    salvar_json(CACHE_NOVO_ENT_PATH, cache_ent)

    total_creditos_faixas = sum(len(v.get("creditos", [])) for v in faixas.values())
    total_creditos_albuns = sum(len(v.get("creditos", [])) for v in albuns.values())

    print("\n=== TODOS OS ARQUIVOS ATUALIZADOS COM SUCESSO ===")
    print(f"Tempo total                 : {int(time.time() - t0)}s")
    print(f"artistas_tratados.json      : {len(artistas)} artistas, produtores, compositores e técnicos")
    print(f"faixas_tratadas.json        : {len(faixas)} faixas ({total_creditos_faixas} créditos técnicos enriquecidos)")
    print(f"albuns_tratados.json        : {len(albuns)} álbuns ({total_creditos_albuns} créditos técnicos enriquecidos)")
    print(f"grammy_silver_tratado.json  : {len(indicacoes)} indicações sincronizadas")

if __name__ == "__main__":
    executar_enriquecimento()