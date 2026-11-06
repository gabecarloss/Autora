-- Migração 0001: tabelas base do perfil (passo 1).
-- Demais tabelas (métricas, hipóteses, verificações, edições do usuário) entram
-- por migração no passo em que forem usadas.

CREATE TABLE rodada (
    id                INTEGER PRIMARY KEY,
    iniciada_em       TEXT NOT NULL,
    terminada_em      TEXT,
    origem            TEXT NOT NULL CHECK (origem IN ('automatica', 'manual', 'teste')),
    estado            TEXT NOT NULL CHECK (estado IN ('em_andamento', 'concluida', 'parcial', 'falhou')),
    videos_pedidos    INTEGER NOT NULL DEFAULT 0,
    videos_entregues  INTEGER NOT NULL DEFAULT 0,
    observacao        TEXT
);

CREATE TABLE versao_estilo (
    id           INTEGER PRIMARY KEY,
    numero       INTEGER NOT NULL UNIQUE,
    criada_em    TEXT NOT NULL,
    descricao    TEXT NOT NULL,
    origem       TEXT,
    detalhe_json TEXT
);

-- Biblioteca e material gerado no mesmo índice (seção 4), com origem marcada.
CREATE TABLE video (
    id               INTEGER PRIMARY KEY,
    origem           TEXT NOT NULL CHECK (origem IN ('pasta', 'gerado')),
    apelido_pasta    TEXT,
    caminho_relativo TEXT NOT NULL,
    hash_arquivo     TEXT,
    phash            TEXT,
    duracao_s        REAL,
    largura          INTEGER,
    altura           INTEGER,
    orientacao       TEXT CHECK (orientacao IN ('vertical', 'horizontal', 'quadrado')),
    tem_audio        INTEGER CHECK (tem_audio IN (0, 1)),
    transcricao      TEXT,
    analise_json     TEXT,
    indexado_em      TEXT,
    falha_indexacao  TEXT,
    CHECK ((origem = 'pasta') = (apelido_pasta IS NOT NULL)),
    UNIQUE (apelido_pasta, caminho_relativo)
);
CREATE INDEX video_phash ON video (phash);
CREATE INDEX video_hash_arquivo ON video (hash_arquivo);

CREATE TABLE post (
    id                 INTEGER PRIMARY KEY,
    rodada_id          INTEGER REFERENCES rodada (id),
    numero_na_rodada   INTEGER,
    criado_em          TEXT NOT NULL,
    estado             TEXT NOT NULL CHECK (estado IN (
                           'gerando', 'aguardando_revisao', 'aprovado', 'descartado',
                           'refazer', 'falhou', 'publicado')),
    plataforma         TEXT NOT NULL DEFAULT 'tiktok',
    formato            TEXT,
    fonte_material     TEXT CHECK (fonte_material IN ('pasta', 'gerado', 'hibrido')),
    tema               TEXT,
    gancho             TEXT,
    duracao_s          REAL,
    som_json           TEXT,
    voz                TEXT,
    horario_sugerido   TEXT,
    versao_estilo_id   INTEGER REFERENCES versao_estilo (id),
    referencia         TEXT,
    pasta_saida        TEXT,
    publicado_em       TEXT,
    id_na_plataforma   TEXT
);
CREATE INDEX post_rodada ON post (rodada_id);

-- Quais vídeos (e trechos) cada post usou. Base do "nunca repostar" (seção 4).
CREATE TABLE post_video (
    post_id        INTEGER NOT NULL REFERENCES post (id) ON DELETE CASCADE,
    video_id       INTEGER NOT NULL REFERENCES video (id),
    trecho_inicio_s REAL,
    trecho_fim_s    REAL,
    PRIMARY KEY (post_id, video_id, trecho_inicio_s)
);
CREATE INDEX post_video_video ON post_video (video_id);

CREATE TABLE etapa_execucao (
    id           INTEGER PRIMARY KEY,
    rodada_id    INTEGER NOT NULL REFERENCES rodada (id),
    post_id      INTEGER REFERENCES post (id),
    etapa        TEXT NOT NULL,
    iniciada_em  TEXT NOT NULL,
    terminada_em TEXT,
    estado       TEXT NOT NULL CHECK (estado IN ('em_andamento', 'ok', 'falhou', 'pulada')),
    erro         TEXT
);
CREATE INDEX etapa_rodada ON etapa_execucao (rodada_id);

-- Toda decisão relevante tem motivo (seção 3.1, "Como você raciocina antes de agir").
CREATE TABLE decisao (
    id              INTEGER PRIMARY KEY,
    rodada_id       INTEGER REFERENCES rodada (id),
    post_id         INTEGER REFERENCES post (id),
    campo           TEXT NOT NULL,
    escolha         TEXT NOT NULL,
    motivo          TEXT NOT NULL CHECK (length(trim(motivo)) > 0),
    raciocinio_json TEXT,
    criada_em       TEXT NOT NULL
);
CREATE INDEX decisao_post ON decisao (post_id);

-- Cada chamada a serviço: base da aba Custo e da tela Bastidores.
CREATE TABLE chamada_servico (
    id              INTEGER PRIMARY KEY,
    rodada_id       INTEGER REFERENCES rodada (id),
    post_id         INTEGER REFERENCES post (id),
    etapa           TEXT,
    servico         TEXT NOT NULL,
    provedor        TEXT,
    nivel           TEXT,
    tokens_entrada  INTEGER,
    tokens_saida    INTEGER,
    tokens_cache    INTEGER,
    custo_usd       REAL,
    duracao_ms      INTEGER,
    resultado       TEXT NOT NULL CHECK (resultado IN ('ok', 'falhou', 'reserva')),
    erro            TEXT,
    criada_em       TEXT NOT NULL
);
CREATE INDEX chamada_criada ON chamada_servico (criada_em);

-- Resumo diário dos logs: fica para sempre, mesmo depois da retenção (seção 9.5).
CREATE TABLE resumo_dia (
    data          TEXT PRIMARY KEY,
    eventos       INTEGER NOT NULL,
    erros         INTEGER NOT NULL,
    por_tipo_json TEXT NOT NULL,
    custo_usd     REAL NOT NULL,
    criado_em     TEXT NOT NULL
);
