import sqlite3
import bcrypt
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'edutrack.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha_hash TEXT NOT NULL,
        perfil TEXT NOT NULL CHECK(perfil IN ('admin','professor','aluno','responsavel')),
        ativo INTEGER DEFAULT 1,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS turmas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        ano TEXT NOT NULL,
        turno TEXT NOT NULL CHECK(turno IN ('Matutino','Vespertino','Noturno')),
        ano_letivo INTEGER NOT NULL,
        ativa INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS disciplinas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        carga_horaria INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS turma_disciplina_professor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turma_id INTEGER REFERENCES turmas(id),
        disciplina_id INTEGER REFERENCES disciplinas(id),
        professor_id INTEGER REFERENCES usuarios(id),
        UNIQUE(turma_id, disciplina_id)
    );

    CREATE TABLE IF NOT EXISTS aluno_turma (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id INTEGER REFERENCES usuarios(id),
        turma_id INTEGER REFERENCES turmas(id),
        UNIQUE(aluno_id, turma_id)
    );

    CREATE TABLE IF NOT EXISTS notas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id INTEGER REFERENCES usuarios(id),
        turma_id INTEGER REFERENCES turmas(id),
        disciplina_id INTEGER REFERENCES disciplinas(id),
        bimestre INTEGER NOT NULL CHECK(bimestre IN (1,2,3,4)),
        nota REAL NOT NULL CHECK(nota >= 0 AND nota <= 10),
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(aluno_id, turma_id, disciplina_id, bimestre)
    );

    CREATE TABLE IF NOT EXISTS frequencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aluno_id INTEGER REFERENCES usuarios(id),
        turma_id INTEGER REFERENCES turmas(id),
        disciplina_id INTEGER REFERENCES disciplinas(id),
        data DATE NOT NULL,
        presente INTEGER NOT NULL DEFAULT 1,
        UNIQUE(aluno_id, turma_id, disciplina_id, data)
    );

    CREATE TABLE IF NOT EXISTS comunicados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        corpo TEXT NOT NULL,
        autor_id INTEGER REFERENCES usuarios(id),
        turma_id INTEGER,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS leitura_comunicado (
        usuario_id INTEGER REFERENCES usuarios(id),
        comunicado_id INTEGER REFERENCES comunicados(id),
        lido_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(usuario_id, comunicado_id)
    );
    """)

    # Seed data
    def hash_pw(pw):
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    # Check if already seeded
    existing = c.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if existing == 0:
        # Admin
        c.execute("INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
                  ("Coordenador Admin", "admin@edutrack.com", hash_pw("admin123"), "admin"))
        # Professors
        c.execute("INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
                  ("Prof. Ana Souza", "ana@edutrack.com", hash_pw("prof123"), "professor"))
        c.execute("INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
                  ("Prof. Carlos Lima", "carlos@edutrack.com", hash_pw("prof123"), "professor"))
        # Students
        for i, (nome, email) in enumerate([
            ("João Silva", "joao@edutrack.com"),
            ("Maria Oliveira", "maria@edutrack.com"),
            ("Pedro Santos", "pedro@edutrack.com"),
            ("Larissa Costa", "larissa@edutrack.com"),
            ("Lucas Ferreira", "lucas@edutrack.com"),
        ]):
            c.execute("INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?,?,?,?)",
                      (nome, email, hash_pw("aluno123"), "aluno"))

        # Turmas
        c.execute("INSERT INTO turmas (nome, ano, turno, ano_letivo) VALUES (?,?,?,?)",
                  ("6º Ano A", "6", "Matutino", 2026))
        c.execute("INSERT INTO turmas (nome, ano, turno, ano_letivo) VALUES (?,?,?,?)",
                  ("7º Ano B", "7", "Vespertino", 2026))

        # Disciplinas
        for disc in [("Matemática", 120), ("Português", 120), ("Ciências", 80),
                     ("História", 80), ("Geografia", 80), ("Inglês", 60)]:
            c.execute("INSERT INTO disciplinas (nome, carga_horaria) VALUES (?,?)", disc)

        # Associate professors to turma+disciplina
        # Prof Ana -> Turma 1, Mat+Port; Turma 2, Mat
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (1,1,2)")
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (1,2,2)")
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (2,1,2)")
        # Prof Carlos -> Turma 1, Ciências+História; Turma 2, Port+Ciências
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (1,3,3)")
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (1,4,3)")
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (2,2,3)")
        c.execute("INSERT INTO turma_disciplina_professor (turma_id, disciplina_id, professor_id) VALUES (2,3,3)")

        # Enroll students: alunos 4-8 (ids) into turma 1
        for aluno_id in range(4, 9):
            turma = 1 if aluno_id <= 6 else 2
            c.execute("INSERT INTO aluno_turma (aluno_id, turma_id) VALUES (?,?)", (aluno_id, turma))

        # Seed some notes
        import random
        random.seed(42)
        for aluno_id in range(4, 9):
            turma = 1 if aluno_id <= 6 else 2
            discs = [1, 2, 3, 4] if turma == 1 else [1, 2, 3]
            for disc_id in discs:
                for bim in range(1, 4):
                    nota = round(random.uniform(5.0, 10.0), 1)
                    c.execute("""INSERT OR IGNORE INTO notas (aluno_id,turma_id,disciplina_id,bimestre,nota)
                                 VALUES (?,?,?,?,?)""", (aluno_id, turma, disc_id, bim, nota))

        # Seed comunicados
        c.execute("INSERT INTO comunicados (titulo, corpo, autor_id, turma_id) VALUES (?,?,?,?)",
                  ("Reunião de Pais — Maio 2026",
                   "Prezados responsáveis, informamos que a reunião bimestral de pais e mestres ocorrerá no dia 10/05/2026 às 14h no auditório da escola. Contamos com a presença de todos.",
                   1, None))
        c.execute("INSERT INTO comunicados (titulo, corpo, autor_id, turma_id) VALUES (?,?,?,?)",
                  ("Prova Bimestral — 6º Ano A",
                   "Informamos que a prova do 1º bimestre ocorrerá nos dias 25 e 26 de abril. Estudem pelo material distribuído em sala.",
                   2, 1))

    conn.commit()
    conn.close()
