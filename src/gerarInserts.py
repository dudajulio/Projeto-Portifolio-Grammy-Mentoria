from pathlib import Path
import unicodedata
import json
import re

# ==============================================================================
# CONFIGURAÇÕES E CAMINHOS
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "src" else Path(__file__).resolve().parent
PASTA_SILVER = BASE_DIR / "data" / "silver"
PASTA_GOLD = BASE_DIR / "data" / "gold"
PASTA_GOLD.mkdir(parents=True, exist_ok=True)

ARTISTAS_PATH = PASTA_SILVER / "artistas_tratados.json"
ALBUNS_PATH = PASTA_SILVER / "albuns_tratados.json"
FAIXAS_PATH = PASTA_SILVER / "faixas_tratadas.json"
INDICACOES_PATH = PASTA_SILVER / "grammy_silver_tratado.json"

SAIDA_SQL_PATH = PASTA_GOLD / "povoamento_grammy.sql"

# ==============================================================================
# TRADUÇÃO DE CATEGORIAS (EN -> PT) E CLASSIFICAÇÃO NOS 27 CAMPOS DO GRAMMY
# ==============================================================================
TRADUCOES_CATEGORIAS_EXATAS = {
    "album of the year": "Álbum do Ano",
    "record of the year": "Gravação do Ano",
    "song of the year": "Canção do Ano",
    "best new artist": "Artista Revelação",
    "producer of the year, non-classical": "Produtor do Ano (Não Clássico)",
    "producer of the year, classical": "Produtor do Ano (Clássico)",
    "songwriter of the year, non-classical": "Compositor do Ano (Não Clássico)",
    "best pop solo performance": "Melhor Performance Solo de Pop",
    "best pop duo/group performance": "Melhor Performance de Dupla/Grupo de Pop",
    "best pop vocal album": "Melhor Álbum Vocal de Pop",
    "best traditional pop vocal album": "Melhor Álbum Vocal de Pop Tradicional",
    "best dance/electronic recording": "Melhor Gravação Dance/Eletrônica",
    "best dance pop recording": "Melhor Gravação Dance Pop",
    "best dance/electronic album": "Melhor Álbum Dance/Eletrônico",
    "best rock performance": "Melhor Performance de Rock",
    "best metal performance": "Melhor Performance de Metal",
    "best rock song": "Melhor Canção de Rock",
    "best rock album": "Melhor Álbum de Rock",
    "best alternative music performance": "Melhor Performance de Música Alternativa",
    "best alternative music album": "Melhor Álbum de Música Alternativa",
    "best r&b performance": "Melhor Performance de R&B",
    "best traditional r&b performance": "Melhor Performance de R&B Tradicional",
    "best r&b song": "Melhor Canção de R&B",
    "best progressive r&b album": "Melhor Álbum de R&B Progressivo",
    "best r&b album": "Melhor Álbum de R&B",
    "best rap performance": "Melhor Performance de Rap",
    "best melodic rap performance": "Melhor Performance de Rap Melódico",
    "best rap song": "Melhor Canção de Rap",
    "best rap album": "Melhor Álbum de Rap",
    "best country solo performance": "Melhor Performance Solo de Country",
    "best country duo/group performance": "Melhor Performance de Dupla/Grupo de Country",
    "best country song": "Melhor Canção de Country",
    "best country album": "Melhor Álbum de Country",
    "best jazz vocal album": "Melhor Álbum Vocal de Jazz",
    "best jazz instrumental album": "Melhor Álbum Instrumental de Jazz",
    "best latin pop album": "Melhor Álbum de Pop Latino",
    "best música urbana album": "Melhor Álbum de Música Urbana",
    "best musica urbana album": "Melhor Álbum de Música Urbana",
    "best gospel performance/song": "Melhor Performance/Canção Gospel",
    "best gospel album": "Melhor Álbum Gospel",
    "best compilation soundtrack for visual media": "Melhor Trilha Sonora de Compilação para Mídia Visual",
    "best score soundtrack for visual media": "Melhor Trilha Sonora Original para Mídia Visual",
    "best song written for visual media": "Melhor Canção Escrita para Mídia Visual",
    "best music video": "Melhor Videoclipe",
    "best music film": "Melhor Filme Musical",
}

CAMPOS_GRAMMY_EXATOS = {
    "album of the year": "General Field",
    "record of the year": "General Field",
    "song of the year": "General Field",
    "best new artist": "General Field",
    "producer of the year, non-classical": "General Field",
    "songwriter of the year, non-classical": "General Field",
}

def normalizar(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().strip().split())

def traduzir_categoria_pt(nome_en: str) -> str:
    """Traduz o nome da categoria do Grammy do inglês para português."""
    chave = normalizar(nome_en)
    if chave in TRADUCOES_CATEGORIAS_EXATAS:
        return TRADUCOES_CATEGORIAS_EXATAS[chave]

    texto = nome_en.strip()
    substituicoes = [
        (r"\bBest\b", "Melhor"),
        (r"\bAlbum Of The Year\b", "Álbum do Ano"),
        (r"\bRecord Of The Year\b", "Gravação do Ano"),
        (r"\bSong Of The Year\b", "Canção do Ano"),
        (r"\bOf The Year\b", "do Ano"),
        (r"\bVocal Album\b", "Álbum Vocal"),
        (r"\bInstrumental Album\b", "Álbum Instrumental"),
        (r"\bAlbum\b", "Álbum"),
        (r"\bSong\b", "Canção"),
        (r"\bRecording\b", "Gravação"),
        (r"\bSolo Performance\b", "Performance Solo"),
        (r"\bDuo/Group Performance\b", "Performance de Dupla/Grupo"),
        (r"\bPerformance\b", "Performance"),
        (r"\bProducer\b", "Produtor"),
        (r"\bSongwriter\b", "Compositor"),
        (r"\bArrangement\b", "Arranjo"),
        (r"\bComposition\b", "Composição"),
        (r"\bOpera\b", "Ópera"),
        (r"\bOrchestral\b", "Orquestral"),
        (r"\bChamber Music\b", "Música de Câmara"),
        (r"\bClassical\b", "Clássico"),
        (r"\bTraditional\b", "Tradicional"),
        (r"\bContemporary\b", "Contemporâneo"),
        (r"\bNew Artist\b", "Artista Revelação"),
    ]
    for padrao, troca in substituicoes:
        texto = re.sub(padrao, troca, texto, flags=re.IGNORECASE)
    return texto

def classificar_tipo_categoria(nome_cat: str) -> str:
    """
    Classifica a categoria em um dos 27 Fields oficiais do Grammy
    (todos com <= 50 caracteres para caber em VARCHAR(50)).
    """
    c = normalizar(nome_cat)

    if c in CAMPOS_GRAMMY_EXATOS:
        return CAMPOS_GRAMMY_EXATOS[c]

    # 27. Packaging, Notes & Historical
    if any(p in c for p in ("package", "packaging", "album notes", "liner notes", "historical", "boxed or special limited edition")):
        return "Packaging, Notes & Historical"

    # 26. Production, Engineering, Composition & Arrangement
    if any(p in c for p in ("engineered", "engineering", "producer of the year", "remixed", "remixer", "immersive audio", "surround sound", "arrangement", "instrumental composition", "songwriter of the year")):
        return "Production, Engineering, Composition & Arrangement"

    # 25. Classical
    if any(p in c for p in ("classical", "orchestral", "opera", "choral", "chamber music", "small ensemble", "soloist", "compendium", "contemporary classical")):
        return "Classical"

    # 24. Music Video & Film
    if any(p in c for p in ("music video", "music film", "long form video", "short form video")):
        return "Music Video & Film"

    # 23. Visual Media
    if any(p in c for p in ("visual media", "motion picture", "television", "soundtrack", "score", "video games")):
        return "Visual Media"

    # 22. Spoken Word Poetry
    if "spoken word poetry" in c:
        return "Spoken Word Poetry"

    # 21. Audiobook, Narration & Storytelling
    if any(p in c for p in ("audiobook", "narration", "storytelling", "spoken word", "non-musical")):
        return "Audiobook, Narration & Storytelling"

    # 20. Comedy
    if "comedy" in c:
        return "Comedy"

    # 19. Children's Music
    if "children" in c:
        return "Children's Music"

    # 18. New Age, Ambient & Chant
    if any(p in c for p in ("new age", "ambient", "chant")):
        return "New Age, Ambient & Chant"

    # 17. Reggae
    if "reggae" in c:
        return "Reggae"

    # 16. African Music
    if "african" in c:
        return "African Music"

    # 15. Global Music
    if any(p in c for p in ("global music", "world music", "world traditional")):
        return "Global Music"

    # 14. Latin
    if any(p in c for p in ("latin", "musica urbana", "mexican", "tejano", "norteno", "tropical", "salsa", "merengue", "banda", "mariachi", "brazilian", "mpb", "samba")):
        return "Latin"

    # 13. Gospel & Contemporary Christian
    if any(p in c for p in ("gospel", "christian", "inspirational")):
        return "Gospel & Contemporary Christian"

    # 12. American Roots
    if any(p in c for p in ("american roots", "americana", "bluegrass", "traditional blues", "contemporary blues", "folk", "regional roots", "zydeco", "cajun", "polka", "native american", "hawaiian")):
        return "American Roots"

    # 11. Country
    if any(p in c for p in ("country", "western")):
        return "Country"

    # 10. Musical Theater
    if any(p in c for p in ("musical theater", "musical show")):
        return "Musical Theater"

    # 9. Contemporary Instrumental
    if "contemporary instrumental" in c:
        return "Contemporary Instrumental"

    # 8. Traditional Pop
    if "traditional pop" in c:
        return "Traditional Pop"

    # 7. Jazz
    if "jazz" in c:
        return "Jazz"

    # 6. Rap
    if any(p in c for p in ("rap", "hip hop", "hip-hop")):
        return "Rap"

    # 5. R&B
    if any(p in c for p in ("r&b", "rhythm & blues", "urban contemporary", "soul")):
        return "R&B"

    # 4. Alternative
    if "alternative" in c:
        return "Alternative"

    # 3. Rock & Metal
    if any(p in c for p in ("rock", "metal", "hard rock", "punk")):
        return "Rock & Metal"

    # 2. Pop & Dance/Electronic
    if any(p in c for p in ("pop", "dance", "electronic", "disco")):
        return "Pop & Dance/Electronic"

    # 1. General Field (fallback para categorias históricas gerais)
    return "General Field"

# ==============================================================================
# FUNÇÕES UTILITÁRIAS E SANITIZAÇÃO SQL
# ==============================================================================
def carregar_json(caminho: Path):
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

def esc_sql(valor, max_len: int | None = None) -> str:
    """Escapa strings para MySQL e respeita estritamente o tamanho do VARCHAR."""
    if valor is None:
        return "NULL"
    texto = str(valor).strip()
    if not texto:
        return "NULL"
    if max_len is not None and len(texto) > max_len:
        texto = texto[:max_len].rstrip()
    texto = (
        texto.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\x00", "")
    )
    return f"'{texto}'"

def formatar_data_sql(data_str: str | None, fallback: str | None = None) -> str:
    """
    Converte datas parciais ('1981', '1981-09', '1981-09-04') em DATE válido
    para MySQL com NO_ZERO_IN_DATE / NO_ZERO_DATE ativo.
    """
    if data_str:
        s = str(data_str).strip()
        m_full = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        if m_full:
            ano, mes, dia = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
            if 1000 <= ano <= 2026:
                mes = mes if 1 <= mes <= 12 else 1
                dia = dia if 1 <= dia <= 28 else 1
                return f"'{ano:04d}-{mes:02d}-{dia:02d}'"
        m_ym = re.match(r"^(\d{4})-(\d{2})$", s)
        if m_ym:
            ano, mes = int(m_ym.group(1)), int(m_ym.group(2))
            if 1000 <= ano <= 2026:
                mes = mes if 1 <= mes <= 12 else 1
                return f"'{ano:04d}-{mes:02d}-01'"
        m_y = re.match(r"^(\d{4})$", s)
        if m_y:
            ano = int(m_y.group(1))
            if 1000 <= ano <= 2026:
                return f"'{ano:04d}-01-01'"

    return f"'{fallback}'" if fallback else "NULL"

def ms_para_time_sql(duracao_ms: int | None) -> str:
    """Converte milissegundos para formato TIME ('HH:MM:SS') válido no MySQL."""
    if not duracao_ms or int(duracao_ms) <= 0:
        return "'00:03:30'"
    total_seg = max(1, int(round(int(duracao_ms) / 1000)))
    horas = total_seg // 3600
    minutos = (total_seg % 3600) // 60
    segundos = total_seg % 60
    return f"'{horas:02d}:{minutos:02d}:{segundos:02d}'"

def classificar_papel_pessoa(funcao: str) -> str:
    """Classifica uma função em 'artista', 'produtor', 'compositor' ou 'tecnico'."""
    f = normalizar(funcao)
    if any(p in f for p in ("performer", "artist", "vocal", "featured", "soloist", "band", "ensemble", "choir", "rap")):
        return "artista"
    if any(p in f for p in ("producer", "produ")):
        return "produtor"
    if any(p in f for p in ("composer", "lyricist", "songwriter", "writer", "librettist", "author")):
        return "compositor"
    return "tecnico"

# ==============================================================================
# GERADOR DE SQL PARA AS 14 TABELAS DO DDL
# ==============================================================================
def gerar_sql_completo():
    artistas_json = carregar_json(ARTISTAS_PATH)
    albuns_json = carregar_json(ALBUNS_PATH)
    faixas_json = carregar_json(FAIXAS_PATH)
    indicacoes_json = carregar_json(INDICACOES_PATH)

    # --------------------------------------------------------------------------
    # 1. MAPEAMENTO DE GRAVADORAS
    # --------------------------------------------------------------------------
    gravadoras_map = {}  # chave_norm -> (idGravadora, nome, origem)
    gravadoras_map["independente"] = (1, "Independente / Não Informada", "Desconhecida")
    prox_id_grav = 2

    for album in albuns_json.values():
        nome_g = (album.get("gravadora") or "").strip()
        if nome_g:
            chave_g = normalizar(nome_g)
            if chave_g not in gravadoras_map:
                origem_g = (album.get("origem_gravadora") or "Internacional").strip()
                gravadoras_map[chave_g] = (prox_id_grav, nome_g, origem_g)
                prox_id_grav += 1

    # --------------------------------------------------------------------------
    # 2. MAPEAMENTO DE CATEGORIAS (TRADUZIDAS + 27 FIELDS) E CERIMÔNIAS
    # --------------------------------------------------------------------------
    categorias_map = {}  # chave_norm -> (idCategoria, nome_pt, tipoCategoria)
    prox_id_cat = 1
    cerimonias_map = {}  # edicao -> dataRealizacao

    for reg in indicacoes_json:
        cat_nome = (reg.get("categoria") or "").strip()
        if cat_nome:
            chave_c = normalizar(cat_nome)
            if chave_c not in categorias_map:
                nome_pt = traduzir_categoria_pt(cat_nome)
                tipo_cat = classificar_tipo_categoria(cat_nome)
                categorias_map[chave_c] = (prox_id_cat, nome_pt, tipo_cat)
                prox_id_cat += 1

        edicao = int(reg.get("edicao", 1))
        ano = int(reg.get("ano", 1959))
        if edicao not in cerimonias_map:
            cerimonias_map[edicao] = f"{ano:04d}-02-15"

    # --------------------------------------------------------------------------
    # 3. CONSOLIDAÇÃO DE PESSOAS E SUAS FLAGS
    # --------------------------------------------------------------------------
    pessoas_map = {}  # chave_norm -> dict completo da Pessoa
    prox_id_pessoa = 1

    def obter_ou_criar_pessoa(chave_p: str, dados_base: dict | None = None) -> int:
        nonlocal prox_id_pessoa
        if chave_p not in pessoas_map:
            info = dados_base or artistas_json.get(chave_p) or {}
            nome_real = (info.get("nome_mb") or chave_p.title()).strip()
            tipo_art = info.get("tipo") or "Person"
            pessoas_map[chave_p] = {
                "idPessoa": prox_id_pessoa,
                "Nome": nome_real,
                "dataNascimento": info.get("inicio"),
                "dataFalecimento": info.get("fim"),
                "Nacionalidade": info.get("pais"),
                "ArtistaFlag": 0,
                "nomeArtistico": nome_real[:45],
                "tipoArtistico": tipo_art[:45],
                "Produtor_Flag": 0,
                "Compositor_Flag": 0,
                "ProfissionalTec_Flag": 0,
            }
            prox_id_pessoa += 1
        return pessoas_map[chave_p]["idPessoa"]

    for chave_art, dados_art in artistas_json.items():
        obter_ou_criar_pessoa(chave_art, dados_art)

    # --------------------------------------------------------------------------
    # 4. MAPEAMENTO DE ÁLBUNS E GÊNEROS DO ÁLBUM
    # --------------------------------------------------------------------------
    albuns_id_map = {}      # chave_obra -> idAlbum
    albuns_titulo_map = {}  # (chave_artista, titulo_norm) -> idAlbum
    albuns_rows = []
    generos_album_rows = set()
    participou_rows = set()
    prox_id_album = 1

    for chave_obra, alb in albuns_json.items():
        id_alb = prox_id_album
        prox_id_album += 1
        albuns_id_map[chave_obra] = id_alb

        titulo_alb = (alb.get("titulo") or "Álbum Sem Título").strip()
        chave_art_princ = chave_obra.split("|||")[0]
        albuns_titulo_map[(chave_art_princ, normalizar(titulo_alb))] = id_alb

        chave_g = normalizar(alb.get("gravadora") or "")
        id_grav = gravadoras_map[chave_g][0] if chave_g in gravadoras_map else 1

        data_lanc = formatar_data_sql(alb.get("data_lancamento"), fallback="2000-01-01")
        albuns_rows.append((id_alb, titulo_alb, data_lanc, id_grav))

        generos_lista = alb.get("generos") or ["Pop"]
        for gen in generos_lista:
            g_limpo = str(gen).strip()[:45]
            if g_limpo:
                generos_album_rows.add((id_alb, g_limpo))

        for interp in alb.get("interpretes") or []:
            c_int = normalizar(interp)
            if c_int:
                id_p = obter_ou_criar_pessoa(c_int)
                pessoas_map[c_int]["ArtistaFlag"] = 1
                participou_rows.add((id_p, id_alb))

        for cred in alb.get("creditos") or []:
            c_prof = normalizar(cred.get("nome") or "")
            if not c_prof:
                continue
            id_p = obter_ou_criar_pessoa(c_prof, cred)
            papel = classificar_papel_pessoa(cred.get("funcao", ""))
            if papel == "artista":
                pessoas_map[c_prof]["ArtistaFlag"] = 1
            elif papel == "produtor":
                pessoas_map[c_prof]["Produtor_Flag"] = 1
            elif papel == "compositor":
                pessoas_map[c_prof]["Compositor_Flag"] = 1
            else:
                pessoas_map[c_prof]["ProfissionalTec_Flag"] = 1
            participou_rows.add((id_p, id_alb))

    # --------------------------------------------------------------------------
    # 5. MAPEAMENTO DE FAIXAS, FICHA TÉCNICA E RELAÇÃO COM ÁLBUNS (contem)
    # --------------------------------------------------------------------------
    faixas_id_map = {}  # chave_obra -> idFaixa
    faixas_rows = []
    contem_rows = set()
    interpreta_rows = set()
    produziu_rows = set()
    compos_rows = set()
    realizou_rows = {}  # (idPessoa, idFaixa) -> funcao
    prox_id_faixa = 1

    for chave_obra, fx in faixas_json.items():
        id_fx = prox_id_faixa
        prox_id_faixa += 1
        faixas_id_map[chave_obra] = id_fx

        titulo_fx = (fx.get("titulo") or "Faixa Sem Título").strip()
        duracao_sql = ms_para_time_sql(fx.get("duracao_ms"))
        generos_fx = fx.get("generos") or ["Pop"]
        genero_principal = str(generos_fx[0]).strip()[:50] if generos_fx else "Pop"

        chave_art_princ = chave_obra.split("|||")[0]
        album_vinculado = albuns_titulo_map.get((chave_art_princ, normalizar(titulo_fx)))
        if not album_vinculado:
            for (c_art, _), id_a in albuns_titulo_map.items():
                if c_art == chave_art_princ:
                    album_vinculado = id_a
                    break

        is_single = 0 if album_vinculado else 1
        faixas_rows.append((id_fx, titulo_fx, duracao_sql, genero_principal, is_single))

        if album_vinculado:
            contem_rows.add((album_vinculado, id_fx))

        for interp in fx.get("interpretes") or []:
            c_int = normalizar(interp)
            if c_int:
                id_p = obter_ou_criar_pessoa(c_int)
                pessoas_map[c_int]["ArtistaFlag"] = 1
                interpreta_rows.add((id_p, id_fx))

        for cred in fx.get("creditos") or []:
            c_prof = normalizar(cred.get("nome") or "")
            if not c_prof:
                continue
            id_p = obter_ou_criar_pessoa(c_prof, cred)
            funcao_raw = (cred.get("funcao") or "contributor").strip()
            papel = classificar_papel_pessoa(funcao_raw)

            if papel == "artista":
                pessoas_map[c_prof]["ArtistaFlag"] = 1
                interpreta_rows.add((id_p, id_fx))
            elif papel == "produtor":
                pessoas_map[c_prof]["Produtor_Flag"] = 1
                produziu_rows.add((id_p, id_fx))
            elif papel == "compositor":
                pessoas_map[c_prof]["Compositor_Flag"] = 1
                compos_rows.add((id_p, id_fx))
            else:
                pessoas_map[c_prof]["ProfissionalTec_Flag"] = 1
                chave_rel = (id_p, id_fx)
                if chave_rel not in realizou_rows:
                    realizou_rows[chave_rel] = funcao_raw[:45]
                elif funcao_raw[:45] not in realizou_rows[chave_rel]:
                    combinado = f"{realizou_rows[chave_rel]}, {funcao_raw}"
                    realizou_rows[chave_rel] = combinado[:45]

    for p in pessoas_map.values():
        if (p["ArtistaFlag"] + p["Produtor_Flag"] + p["Compositor_Flag"] + p["ProfissionalTec_Flag"]) == 0:
            p["ArtistaFlag"] = 1

    # --------------------------------------------------------------------------
    # 6. MAPEAMENTO DE INDICAÇÕES (Indicação)
    # --------------------------------------------------------------------------
    indicacoes_rows = []
    prox_id_ind = 1

    for reg in indicacoes_json:
        c_cat = normalizar(reg.get("categoria") or "")
        if c_cat not in categorias_map:
            continue
        id_cat = categorias_map[c_cat][0]
        edicao = int(reg.get("edicao", 1))
        venceu = 1 if reg.get("venceu") else 0

        c_art = reg.get("chave_artista") or ""
        id_pessoa = obter_ou_criar_pessoa(c_art)
        pessoas_map[c_art]["ArtistaFlag"] = 1

        c_obra = reg.get("chave_obra") or ""
        id_alb = albuns_id_map.get(c_obra)
        id_fx = faixas_id_map.get(c_obra)

        if not id_alb and not id_fx:
            continue

        indicacoes_rows.append((
            prox_id_ind,
            venceu,
            id_cat,
            edicao,
            id_alb if id_alb else "NULL",
            id_fx if id_fx else "NULL",
            id_pessoa
        ))
        prox_id_ind += 1

    # ==========================================================================
    # ESCRITA DO ARQUIVO SQL ORDENADO PELAS CHAVES ESTRANGEIRAS
    # ==========================================================================
    linhas = [
        "-- =============================================================================",
        "-- SCRIPT DE POVOAMENTO DO BANCO DE DADOS GRAMMY (14 TABELAS - SCHEMA `mydb`)",
        "-- =============================================================================",
        "USE `mydb`;",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "START TRANSACTION;",
        "",
        "-- 1. Tabela `Gravadora`",
    ]

    for _, (id_g, nome_g, origem_g) in sorted(gravadoras_map.items(), key=lambda x: x[1][0]):
        linhas.append(
            f"INSERT INTO `Gravadora` (`idGravadora`, `nome`, `origem`) VALUES "
            f"({id_g}, {esc_sql(nome_g, 100)}, {esc_sql(origem_g, 50)});"
        )

    linhas.append("\n-- 2. Tabela `Categoria` (Traduzidas PT-BR + 27 Fields Oficiais)")
    for _, (id_c, nome_c, tipo_c) in sorted(categorias_map.items(), key=lambda x: x[1][0]):
        linhas.append(
            f"INSERT INTO `Categoria` (`idCategoria`, `nome`, `tipoCategoria`) VALUES "
            f"({id_c}, {esc_sql(nome_c, 100)}, {esc_sql(tipo_c, 50)});"
        )

    linhas.append("\n-- 3. Tabela `Cerimonia`")
    for edicao, data_real in sorted(cerimonias_map.items()):
        linhas.append(
            f"INSERT INTO `Cerimonia` (`edicao`, `dataRealizacao`) VALUES "
            f"({edicao}, '{data_real}');"
        )

    linhas.append("\n-- 4. Tabela `Pessoa` (Artistas, Produtores, Compositores e Profissionais Técnicos)")
    for p in sorted(pessoas_map.values(), key=lambda x: x["idPessoa"]):
        linhas.append(
            "INSERT INTO `Pessoa` (`idPessoa`, `Nome`, `dataNascimento`, `dataFalecimento`, "
            "`Nacionalidade`, `ArtistaFlag`, `nomeArtistico`, `tipoArtistico`, "
            "`Produtor_Flag`, `Compositor_Flag`, `ProfissionalTec_Flag`) VALUES ("
            f"{p['idPessoa']}, {esc_sql(p['Nome'], 450)}, {formatar_data_sql(p['dataNascimento'])}, "
            f"{formatar_data_sql(p['dataFalecimento'])}, {esc_sql(p['Nacionalidade'], 50)}, "
            f"{p['ArtistaFlag']}, {esc_sql(p['nomeArtistico'], 45)}, {esc_sql(p['tipoArtistico'], 45)}, "
            f"{p['Produtor_Flag']}, {p['Compositor_Flag']}, {p['ProfissionalTec_Flag']});"
        )

    linhas.append("\n-- 5. Tabela `Album`")
    for id_a, nome_a, data_a, id_g in albuns_rows:
        linhas.append(
            f"INSERT INTO `Album` (`idAlbum`, `nome`, `dataLancamento`, `Gravadora_idGravadora`) VALUES "
            f"({id_a}, {esc_sql(nome_a, 450)}, {data_a}, {id_g});"
        )

    linhas.append("\n-- 6. Tabela `Faixa`")
    for id_f, nome_f, dur_f, gen_f, single_f in faixas_rows:
        linhas.append(
            f"INSERT INTO `Faixa` (`idFaixa`, `nome`, `duração`, `genero`, `single`) VALUES "
            f"({id_f}, {esc_sql(nome_f, 110)}, {dur_f}, {esc_sql(gen_f, 50)}, {single_f});"
        )

    linhas.append("\n-- 7. Tabela `Genero` (Gêneros dos Álbuns)")
    for id_a, gen_a in sorted(generos_album_rows):
        linhas.append(
            f"INSERT INTO `Genero` (`Album_idAlbum`, `genero`) VALUES ({id_a}, {esc_sql(gen_a, 45)});"
        )

    linhas.append("\n-- 8. Tabela `contem` (Relação Álbum x Faixa)")
    for id_a, id_f in sorted(contem_rows):
        linhas.append(
            f"INSERT INTO `contem` (`Album_idAlbum`, `Faixa_idFaixa`) VALUES ({id_a}, {id_f});"
        )

    linhas.append("\n-- 9. Tabela `participou` (Relação Pessoa x Álbum)")
    for id_p, id_a in sorted(participou_rows):
        linhas.append(
            f"INSERT INTO `participou` (`Pessoa_idPessoa`, `Album_idAlbum`) VALUES ({id_p}, {id_a});"
        )

    linhas.append("\n-- 10. Tabela `interpreta` (Relação Intérprete x Faixa)")
    for id_p, id_f in sorted(interpreta_rows):
        linhas.append(
            f"INSERT INTO `interpreta` (`Pessoa_idPessoa`, `Faixa_idFaixa`) VALUES ({id_p}, {id_f});"
        )

    linhas.append("\n-- 11. Tabela `produziu` (Relação Produtor x Faixa)")
    for id_p, id_f in sorted(produziu_rows):
        linhas.append(
            f"INSERT INTO `produziu` (`Pessoa_idPessoa`, `Faixa_idFaixa`) VALUES ({id_p}, {id_f});"
        )

    linhas.append("\n-- 12. Tabela `compos` (Relação Compositor/Letrista x Faixa)")
    for id_p, id_f in sorted(compos_rows):
        linhas.append(
            f"INSERT INTO `compos` (`Pessoa_idPessoa`, `Faixa_idFaixa`) VALUES ({id_p}, {id_f});"
        )

    linhas.append("\n-- 13. Tabela `realizou` (Relação Profissional Técnico x Faixa)")
    for (id_p, id_f), func_t in sorted(realizou_rows.items()):
        linhas.append(
            f"INSERT INTO `realizou` (`Pessoa_idPessoa`, `Faixa_idFaixa`, `funcao`) VALUES "
            f"({id_p}, {id_f}, {esc_sql(func_t, 45)});"
        )

    linhas.append("\n-- 14. Tabela `Indicação`")
    for id_i, venc, id_c, ed, id_a, id_f, id_p in indicacoes_rows:
        linhas.append(
            "INSERT INTO `Indicação` (`idIndicacao`, `venceu`, `Categoria_idCategoria`, "
            "`Cerimonia_edicao`, `Album_idAlbum`, `Faixa_idFaixa`, `Pessoa_idPessoa`) VALUES ("
            f"{id_i}, {venc}, {id_c}, {ed}, {id_a}, {id_f}, {id_p});"
        )

    linhas.extend([
        "",
        "COMMIT;",
        "SET FOREIGN_KEY_CHECKS = 1;",
        ""
    ])

    with open(SAIDA_SQL_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    print("=== POVOAMENTO SQL GERADO COM SUCESSO ===")
    print(f"Arquivo gerado : {SAIDA_SQL_PATH}")
    print(f"1. Gravadora   : {len(gravadoras_map)}")
    print(f"2. Categoria   : {len(categorias_map)}")
    print(f"3. Cerimonia   : {len(cerimonias_map)}")
    print(f"4. Pessoa      : {len(pessoas_map)}")
    print(f"5. Album       : {len(albuns_rows)}")
    print(f"6. Faixa       : {len(faixas_rows)}")
    print(f"7. Genero      : {len(generos_album_rows)}")
    print(f"8. contem      : {len(contem_rows)}")
    print(f"9. participou  : {len(participou_rows)}")
    print(f"10. interpreta : {len(interpreta_rows)}")
    print(f"11. produziu   : {len(produziu_rows)}")
    print(f"12. compos     : {len(compos_rows)}")
    print(f"13. realizou   : {len(realizou_rows)}")
    print(f"14. Indicação  : {len(indicacoes_rows)}")

if __name__ == "__main__":
    gerar_sql_completo()