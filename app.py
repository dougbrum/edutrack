from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import jwt
import os
import secrets
import bcrypt
import sqlite3
import os
from datetime import datetime, timedelta
from functools import wraps
from database import get_db, init_db

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

SECRET = os.environ.get("EDUTRACK_SECRET") or secrets.token_hex(32)

# ── auth helpers ──────────────────────────────────────────────────────────────
def make_token(user):
    payload = {
        "id": user["id"],
        "nome": user["nome"],
        "email": user["email"],
        "perfil": user["perfil"],
        "exp": datetime.utcnow() + timedelta(hours=8)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"erro": "Token ausente"}), 401
        try:
            payload = jwt.decode(token, SECRET, algorithms=["HS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado"}), 401
        except Exception:
            return jsonify({"erro": "Token inválido"}), 401
        return f(*args, **kwargs)
    return decorated

def require_perfil(*perfis):
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            if request.user["perfil"] not in perfis:
                return jsonify({"erro": "Acesso negado"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── frontend ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("public", "index.html")

# ── auth routes ───────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    db = get_db()
    user = db.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1",
                      (data.get("email", ""),)).fetchone()
    db.close()
    if not user:
        return jsonify({"erro": "Credenciais inválidas"}), 401
    if not bcrypt.checkpw(data.get("senha", "").encode(), user["senha_hash"].encode()):
        return jsonify({"erro": "Credenciais inválidas"}), 401
    token = make_token(user)
    return jsonify({"token": token, "usuario": {
        "id": user["id"], "nome": user["nome"],
        "email": user["email"], "perfil": user["perfil"]
    }})

@app.route("/api/me")
@require_auth
def me():
    return jsonify(request.user)

# ── usuarios ──────────────────────────────────────────────────────────────────
@app.route("/api/usuarios")
@require_perfil("admin")
def listar_usuarios():
    perfil = request.args.get("perfil")
    db = get_db()
    if perfil:
        rows = db.execute("SELECT id,nome,email,perfil,ativo FROM usuarios WHERE perfil=? ORDER BY nome", (perfil,)).fetchall()
    else:
        rows = db.execute("SELECT id,nome,email,perfil,ativo FROM usuarios ORDER BY nome").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/usuarios", methods=["POST"])
@require_perfil("admin")
def criar_usuario():
    d = request.json
    pw_hash = bcrypt.hashpw(d["senha"].encode(), bcrypt.gensalt()).decode()
    db = get_db()
    try:
        db.execute("INSERT INTO usuarios (nome,email,senha_hash,perfil) VALUES (?,?,?,?)",
                   (d["nome"], d["email"], pw_hash, d["perfil"]))
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"erro": "E-mail já cadastrado"}), 400
    db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/usuarios/<int:uid>", methods=["PUT"])
@require_perfil("admin")
def atualizar_usuario(uid):
    d = request.json
    db = get_db()
    db.execute("UPDATE usuarios SET nome=?,perfil=?,ativo=? WHERE id=?",
               (d["nome"], d["perfil"], d.get("ativo", 1), uid))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/usuarios/<int:uid>", methods=["DELETE"])
@require_perfil("admin")
def desativar_usuario(uid):
    db = get_db()
    db.execute("UPDATE usuarios SET ativo=0 WHERE id=?", (uid,))
    db.commit()
    db.close()
    return jsonify({"ok": True})

# ── turmas ────────────────────────────────────────────────────────────────────
@app.route("/api/turmas")
@require_auth
def listar_turmas():
    db = get_db()
    perfil = request.user["perfil"]
    uid = request.user["id"]

    if perfil == "professor":
        rows = db.execute("""
            SELECT DISTINCT t.* FROM turmas t
            JOIN turma_disciplina_professor tdp ON tdp.turma_id = t.id
            WHERE tdp.professor_id = ? AND t.ativa = 1
        """, (uid,)).fetchall()
    elif perfil == "aluno":
        rows = db.execute("""
            SELECT t.* FROM turmas t
            JOIN aluno_turma at ON at.turma_id = t.id
            WHERE at.aluno_id = ? AND t.ativa = 1
        """, (uid,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM turmas WHERE ativa=1 ORDER BY nome").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/turmas", methods=["POST"])
@require_perfil("admin")
def criar_turma():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO turmas (nome,ano,turno,ano_letivo) VALUES (?,?,?,?)",
               (d["nome"], d["ano"], d["turno"], d["ano_letivo"]))
    db.commit()
    db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/turmas/<int:tid>", methods=["PUT"])
@require_perfil("admin")
def atualizar_turma(tid):
    d = request.json
    db = get_db()
    db.execute("UPDATE turmas SET nome=?,ano=?,turno=?,ano_letivo=?,ativa=? WHERE id=?",
               (d["nome"], d["ano"], d["turno"], d["ano_letivo"], d.get("ativa",1), tid))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/turmas/<int:tid>/alunos")
@require_auth
def alunos_da_turma(tid):
    db = get_db()
    rows = db.execute("""
        SELECT u.id, u.nome, u.email FROM usuarios u
        JOIN aluno_turma at ON at.aluno_id = u.id
        WHERE at.turma_id = ? AND u.ativo = 1 ORDER BY u.nome
    """, (tid,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/turmas/<int:tid>/alunos", methods=["POST"])
@require_perfil("admin")
def matricular_aluno(tid):
    d = request.json
    db = get_db()
    try:
        db.execute("INSERT INTO aluno_turma (aluno_id,turma_id) VALUES (?,?)", (d["aluno_id"], tid))
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"erro": "Aluno já matriculado"}), 400
    db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/turmas/<int:tid>/alunos/<int:aid>", methods=["DELETE"])
@require_perfil("admin")
def desmatricular_aluno(tid, aid):
    db = get_db()
    db.execute("DELETE FROM aluno_turma WHERE turma_id=? AND aluno_id=?", (tid, aid))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/turmas/<int:tid>/disciplinas")
@require_auth
def disciplinas_da_turma(tid):
    db = get_db()
    uid = request.user["id"]
    perfil = request.user["perfil"]
    if perfil == "professor":
        rows = db.execute("""
            SELECT d.id, d.nome, d.carga_horaria, u.nome as professor_nome
            FROM disciplinas d
            JOIN turma_disciplina_professor tdp ON tdp.disciplina_id = d.id
            JOIN usuarios u ON u.id = tdp.professor_id
            WHERE tdp.turma_id = ? AND tdp.professor_id = ?
        """, (tid, uid)).fetchall()
    else:
        rows = db.execute("""
            SELECT d.id, d.nome, d.carga_horaria, u.nome as professor_nome
            FROM disciplinas d
            JOIN turma_disciplina_professor tdp ON tdp.disciplina_id = d.id
            JOIN usuarios u ON u.id = tdp.professor_id
            WHERE tdp.turma_id = ?
        """, (tid,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── disciplinas ───────────────────────────────────────────────────────────────
@app.route("/api/disciplinas")
@require_auth
def listar_disciplinas():
    db = get_db()
    rows = db.execute("SELECT * FROM disciplinas ORDER BY nome").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/disciplinas", methods=["POST"])
@require_perfil("admin")
def criar_disciplina():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO disciplinas (nome, carga_horaria) VALUES (?,?)", (d["nome"], d["carga_horaria"]))
    db.commit()
    db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/turmas/<int:tid>/vincular", methods=["POST"])
@require_perfil("admin")
def vincular_professor(tid):
    d = request.json
    db = get_db()
    try:
        db.execute("INSERT INTO turma_disciplina_professor (turma_id,disciplina_id,professor_id) VALUES (?,?,?)",
                   (tid, d["disciplina_id"], d["professor_id"]))
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return jsonify({"erro": "Vínculo já existente"}), 400
    db.close()
    return jsonify({"ok": True}), 201

# ── notas ──────────────────────────────────────────────────────────────────────
@app.route("/api/notas")
@require_auth
def listar_notas():
    db = get_db()
    turma_id = request.args.get("turma_id")
    disc_id  = request.args.get("disciplina_id")
    aluno_id = request.args.get("aluno_id") or (request.user["id"] if request.user["perfil"]=="aluno" else None)

    query = """
        SELECT n.*, u.nome as aluno_nome, d.nome as disciplina_nome
        FROM notas n
        JOIN usuarios u ON u.id = n.aluno_id
        JOIN disciplinas d ON d.id = n.disciplina_id
        WHERE 1=1
    """
    params = []
    if turma_id:
        query += " AND n.turma_id=?"; params.append(turma_id)
    if disc_id:
        query += " AND n.disciplina_id=?"; params.append(disc_id)
    if aluno_id:
        query += " AND n.aluno_id=?"; params.append(aluno_id)
    query += " ORDER BY u.nome, n.disciplina_id, n.bimestre"

    rows = db.execute(query, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/notas", methods=["POST"])
@require_perfil("professor", "admin")
def lancar_nota():
    d = request.json
    db = get_db()
    db.execute("""
        INSERT INTO notas (aluno_id, turma_id, disciplina_id, bimestre, nota)
        VALUES (?,?,?,?,?)
        ON CONFLICT(aluno_id,turma_id,disciplina_id,bimestre)
        DO UPDATE SET nota=excluded.nota, atualizado_em=CURRENT_TIMESTAMP
    """, (d["aluno_id"], d["turma_id"], d["disciplina_id"], d["bimestre"], d["nota"]))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/notas/bulk", methods=["POST"])
@require_perfil("professor", "admin")
def lancar_notas_bulk():
    items = request.json  # list of {aluno_id, turma_id, disciplina_id, bimestre, nota}
    db = get_db()
    for d in items:
        db.execute("""
            INSERT INTO notas (aluno_id, turma_id, disciplina_id, bimestre, nota)
            VALUES (?,?,?,?,?)
            ON CONFLICT(aluno_id,turma_id,disciplina_id,bimestre)
            DO UPDATE SET nota=excluded.nota, atualizado_em=CURRENT_TIMESTAMP
        """, (d["aluno_id"], d["turma_id"], d["disciplina_id"], d["bimestre"], d["nota"]))
    db.commit()
    db.close()
    return jsonify({"ok": True})

# ── frequências ───────────────────────────────────────────────────────────────
@app.route("/api/frequencias")
@require_auth
def listar_frequencias():
    db = get_db()
    turma_id = request.args.get("turma_id")
    disc_id  = request.args.get("disciplina_id")
    aluno_id = request.args.get("aluno_id") or (request.user["id"] if request.user["perfil"]=="aluno" else None)

    query = """
        SELECT f.*, u.nome as aluno_nome, d.nome as disciplina_nome
        FROM frequencias f
        JOIN usuarios u ON u.id = f.aluno_id
        JOIN disciplinas d ON d.id = f.disciplina_id
        WHERE 1=1
    """
    params = []
    if turma_id:  query += " AND f.turma_id=?";      params.append(turma_id)
    if disc_id:   query += " AND f.disciplina_id=?"; params.append(disc_id)
    if aluno_id:  query += " AND f.aluno_id=?";      params.append(aluno_id)
    query += " ORDER BY f.data DESC, u.nome"

    rows = db.execute(query, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/frequencias/bulk", methods=["POST"])
@require_perfil("professor", "admin")
def registrar_frequencias():
    items = request.json
    db = get_db()
    for d in items:
        db.execute("""
            INSERT INTO frequencias (aluno_id, turma_id, disciplina_id, data, presente)
            VALUES (?,?,?,?,?)
            ON CONFLICT(aluno_id,turma_id,disciplina_id,data)
            DO UPDATE SET presente=excluded.presente
        """, (d["aluno_id"], d["turma_id"], d["disciplina_id"], d["data"], d["presente"]))
    db.commit()
    db.close()
    return jsonify({"ok": True})

# ── comunicados ───────────────────────────────────────────────────────────────
@app.route("/api/comunicados")
@require_auth
def listar_comunicados():
    db = get_db()
    uid = request.user["id"]
    rows = db.execute("""
        SELECT c.*, u.nome as autor_nome,
               CASE WHEN l.usuario_id IS NOT NULL THEN 1 ELSE 0 END as lido
        FROM comunicados c
        JOIN usuarios u ON u.id = c.autor_id
        LEFT JOIN leitura_comunicado l ON l.comunicado_id=c.id AND l.usuario_id=?
        ORDER BY c.criado_em DESC
    """, (uid,)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/comunicados", methods=["POST"])
@require_perfil("admin", "professor")
def criar_comunicado():
    d = request.json
    db = get_db()
    db.execute("INSERT INTO comunicados (titulo,corpo,autor_id,turma_id) VALUES (?,?,?,?)",
               (d["titulo"], d["corpo"], request.user["id"], d.get("turma_id")))
    db.commit()
    db.close()
    return jsonify({"ok": True}), 201

@app.route("/api/comunicados/<int:cid>/lido", methods=["POST"])
@require_auth
def marcar_lido(cid):
    db = get_db()
    db.execute("INSERT OR IGNORE INTO leitura_comunicado (usuario_id,comunicado_id) VALUES (?,?)",
               (request.user["id"], cid))
    db.commit()
    db.close()
    return jsonify({"ok": True})

# ── relatórios ────────────────────────────────────────────────────────────────
@app.route("/api/relatorios/boletim/<int:aluno_id>")
@require_auth
def boletim(aluno_id):
    db = get_db()
    perfil = request.user["perfil"]
    if perfil == "aluno" and request.user["id"] != aluno_id:
        return jsonify({"erro": "Acesso negado"}), 403

    aluno = db.execute("SELECT id, nome, email FROM usuarios WHERE id=?", (aluno_id,)).fetchone()
    if not aluno:
        return jsonify({"erro": "Aluno não encontrado"}), 404

    turmas = db.execute("""
        SELECT t.id, t.nome FROM turmas t
        JOIN aluno_turma at ON at.turma_id = t.id
        WHERE at.aluno_id = ?
    """, (aluno_id,)).fetchall()

    resultado = []
    for turma in turmas:
        disciplinas = db.execute("""
            SELECT d.id, d.nome FROM disciplinas d
            JOIN turma_disciplina_professor tdp ON tdp.disciplina_id = d.id
            WHERE tdp.turma_id = ?
        """, (turma["id"],)).fetchall()

        disc_data = []
        for disc in disciplinas:
            notas = db.execute("""
                SELECT bimestre, nota FROM notas
                WHERE aluno_id=? AND turma_id=? AND disciplina_id=?
                ORDER BY bimestre
            """, (aluno_id, turma["id"], disc["id"])).fetchall()

            notas_dict = {n["bimestre"]: n["nota"] for n in notas}
            vals = [notas_dict.get(b) for b in [1,2,3,4]]
            media = round(sum(v for v in vals if v is not None) / max(1, sum(1 for v in vals if v is not None)), 1) if any(v is not None for v in vals) else None

            # frequência
            total_aulas = db.execute("""
                SELECT COUNT(*) FROM frequencias WHERE aluno_id=? AND turma_id=? AND disciplina_id=?
            """, (aluno_id, turma["id"], disc["id"])).fetchone()[0]
            presencas = db.execute("""
                SELECT COUNT(*) FROM frequencias WHERE aluno_id=? AND turma_id=? AND disciplina_id=? AND presente=1
            """, (aluno_id, turma["id"], disc["id"])).fetchone()[0]
            freq_pct = round(presencas/total_aulas*100) if total_aulas > 0 else None

            situacao = "—"
            if media is not None:
                if media >= 7.0: situacao = "Aprovado"
                elif media >= 5.0: situacao = "Recuperação"
                else: situacao = "Reprovado"

            disc_data.append({
                "disciplina": disc["nome"],
                "b1": notas_dict.get(1), "b2": notas_dict.get(2),
                "b3": notas_dict.get(3), "b4": notas_dict.get(4),
                "media": media, "frequencia": freq_pct, "situacao": situacao
            })

        resultado.append({"turma": dict(turma), "disciplinas": disc_data})

    db.close()
    return jsonify({"aluno": dict(aluno), "turmas": resultado})

@app.route("/api/relatorios/turma/<int:tid>")
@require_perfil("admin", "professor")
def relatorio_turma(tid):
    db = get_db()
    alunos = db.execute("""
        SELECT u.id, u.nome FROM usuarios u
        JOIN aluno_turma at ON at.aluno_id = u.id
        WHERE at.turma_id = ? AND u.ativo=1 ORDER BY u.nome
    """, (tid,)).fetchall()

    disciplinas = db.execute("""
        SELECT DISTINCT d.id, d.nome FROM disciplinas d
        JOIN turma_disciplina_professor tdp ON tdp.disciplina_id = d.id
        WHERE tdp.turma_id = ?
    """, (tid,)).fetchall()

    rows = []
    for aluno in alunos:
        medias = {}
        for disc in disciplinas:
            notas = db.execute("""
                SELECT nota FROM notas WHERE aluno_id=? AND turma_id=? AND disciplina_id=?
            """, (aluno["id"], tid, disc["id"])).fetchall()
            vals = [n["nota"] for n in notas]
            medias[disc["nome"]] = round(sum(vals)/len(vals), 1) if vals else None
        rows.append({"aluno": aluno["nome"], "medias": medias})

    db.close()
    return jsonify({"disciplinas": [d["nome"] for d in disciplinas], "alunos": rows})

# ── dashboard stats ───────────────────────────────────────────────────────────
@app.route("/api/dashboard")
@require_auth
def dashboard():
    db = get_db()
    perfil = request.user["perfil"]
    uid = request.user["id"]
    data = {}

    if perfil == "admin":
        data["total_alunos"]     = db.execute("SELECT COUNT(*) FROM usuarios WHERE perfil='aluno' AND ativo=1").fetchone()[0]
        data["total_professores"]= db.execute("SELECT COUNT(*) FROM usuarios WHERE perfil='professor' AND ativo=1").fetchone()[0]
        data["total_turmas"]     = db.execute("SELECT COUNT(*) FROM turmas WHERE ativa=1").fetchone()[0]
        data["total_disciplinas"]= db.execute("SELECT COUNT(*) FROM disciplinas").fetchone()[0]
        data["comunicados_recentes"] = [dict(r) for r in db.execute(
            "SELECT c.titulo, c.criado_em, u.nome as autor FROM comunicados c JOIN usuarios u ON u.id=c.autor_id ORDER BY c.criado_em DESC LIMIT 5"
        ).fetchall()]

    elif perfil == "professor":
        turmas = db.execute("""
            SELECT COUNT(DISTINCT turma_id) FROM turma_disciplina_professor WHERE professor_id=?
        """, (uid,)).fetchone()[0]
        data["minhas_turmas"] = turmas
        data["minhas_disciplinas"] = db.execute("""
            SELECT COUNT(DISTINCT disciplina_id) FROM turma_disciplina_professor WHERE professor_id=?
        """, (uid,)).fetchone()[0]
        data["total_alunos"] = db.execute("""
            SELECT COUNT(DISTINCT at.aluno_id) FROM aluno_turma at
            JOIN turma_disciplina_professor tdp ON tdp.turma_id=at.turma_id
            WHERE tdp.professor_id=?
        """, (uid,)).fetchone()[0]

    elif perfil == "aluno":
        turma = db.execute("SELECT turma_id FROM aluno_turma WHERE aluno_id=?", (uid,)).fetchone()
        if turma:
            data["minha_turma"] = dict(db.execute("SELECT nome FROM turmas WHERE id=?", (turma["turma_id"],)).fetchone())
        notas = db.execute("SELECT nota FROM notas WHERE aluno_id=?", (uid,)).fetchall()
        vals = [n["nota"] for n in notas]
        data["media_geral"] = round(sum(vals)/len(vals), 1) if vals else None
        total_freq = db.execute("SELECT COUNT(*) FROM frequencias WHERE aluno_id=?", (uid,)).fetchone()[0]
        pres_freq  = db.execute("SELECT COUNT(*) FROM frequencias WHERE aluno_id=? AND presente=1", (uid,)).fetchone()[0]
        data["frequencia_geral"] = round(pres_freq/total_freq*100) if total_freq > 0 else None

    db.close()
    return jsonify(data)

if __name__ == "__main__":
    init_db()
    print("\n✅ EduTrack iniciado!")
    print("   Acesse: http://localhost:5000\n")
    print("   Logins de teste:")
    print("   Admin:     admin@edutrack.com   / admin123")
    print("   Professor: ana@edutrack.com     / prof123")
    print("   Aluno:     joao@edutrack.com    / aluno123\n")
    app.run(debug=True, port=5000)
