import os
from datetime import datetime
from dotenv import load_dotenv

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

db = SQLAlchemy()


# ---------------------------
# Models
# ---------------------------
class Tutor(db.Model):
    __tablename__ = "tutores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    votos = db.relationship("Voto", backref="tutor", lazy=True, cascade="all, delete-orphan")


class Voto(db.Model):
    __tablename__ = "votos"
    id = db.Column(db.Integer, primary_key=True)
    aluno_nome = db.Column(db.String(160), nullable=False)
    serie = db.Column(db.String(40), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutores.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Config(db.Model):
    __tablename__ = "config"
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(80), unique=True, nullable=False)
    valor = db.Column(db.String(200), nullable=False)


# ---------------------------
# Helpers
# ---------------------------
def normalize_database_url(url: str) -> str:
    """
    - Accepts Render/Heroku-style 'postgres://' and converts to 'postgresql://'
    - Forces psycopg driver for SQLAlchemy: 'postgresql+psycopg://'
    - Adds sslmode=require when not present (safe default for Render external URL)
    """
    if not url:
        return url

    url = url.strip()

    # Render/Heroku sometimes uses "postgres://"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # Ensure SQLAlchemy uses psycopg3 driver (we install psycopg[binary])
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    # Add sslmode=require if not present (Render external needs it; internal tolerates it)
    if "sslmode=" not in url and url.startswith("postgresql+psycopg://"):
        if "?" in url:
            url = url + "&sslmode=require"
        else:
            url = url + "?sslmode=require"

    return url



def ensure_schema():
    """
    Pequena migração automática:
    - Se o banco já existia (tabelas criadas sem algumas colunas), garante as colunas usadas pelo código.
    Isso evita erros do tipo: 'column tutores.created_at does not exist'.
    """
    try:
        from sqlalchemy import inspect, text as sql_text
        insp = inspect(db.engine)

        def add_column_if_missing(table: str, column: str, ddl: str):
            if table not in insp.get_table_names():
                return
            cols = [c.get("name") for c in insp.get_columns(table)]
            if column in cols:
                return
            print(f"[MIGRATE] adicionando coluna {table}.{column}")
            db.session.execute(sql_text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            db.session.commit()

        # Columns used by this app
        add_column_if_missing("tutores", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        add_column_if_missing("votos", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    except Exception as e:
        # Never crash the app because of migration helper
        print("[AVISO] ensure_schema falhou (seguindo sem migração automática):", e)

def get_capacidade() -> int:
    """Capacidade de alunos por tutor (entre 16 e 18)."""
    cfg = Config.query.filter_by(chave="capacidade").first()
    try:
        val = int(cfg.valor) if cfg else 18
    except Exception:
        val = 18
    return max(16, min(18, val))


def set_capacidade(value: int) -> int:
    value = max(16, min(18, int(value)))
    cfg = Config.query.filter_by(chave="capacidade").first()
    if not cfg:
        cfg = Config(chave="capacidade", valor=str(value))
        db.session.add(cfg)
    else:
        cfg.valor = str(value)
    db.session.commit()
    return value


def admin_password_ok(pwd: str) -> bool:
    return pwd == os.environ.get("ADMIN_PASSWORD", "1243##")


def require_admin():
    return session.get("admin") is True


# ---------------------------
# App factory
# ---------------------------
def create_app():
    app = Flask(__name__)

    # Secret key (set on Render!)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    raw_db_url = os.environ.get("DATABASE_URL", "")
    db_url = normalize_database_url(raw_db_url)

    # If DATABASE_URL is missing, don't crash (use local sqlite so deploy doesn't exit)
    if not db_url:
        db_url = "sqlite:///data.db"
        print("[AVISO] DATABASE_URL não definido. Usando SQLite local (data.db). "
              "No Render, configure DATABASE_URL em Environment para usar Postgres.")

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

        ensure_schema()
        # default capacidade
        if not Config.query.filter_by(chave="capacidade").first():
            db.session.add(Config(chave="capacidade", valor="18"))
            db.session.commit()

    # ---------------------------
    # Public routes
    # ---------------------------
    @app.get("/")
    def index():
        tutores = Tutor.query.filter_by(ativo=True).order_by(Tutor.nome.asc()).all()
        return render_template("index.html", tutores=tutores)

    @app.post("/api/votar")
    def api_votar():
        data = request.get_json(silent=True) or request.form
        aluno = (data.get("aluno") or "").strip()
        serie = (data.get("serie") or "").strip()
        tutor_id = data.get("tutor_id")

        if not aluno or not serie or not tutor_id:
            return jsonify({"ok": False, "error": "Preencha aluno, série e tutor."}), 400

        try:
            tutor_id = int(tutor_id)
        except Exception:
            return jsonify({"ok": False, "error": "Tutor inválido."}), 400

        tutor = Tutor.query.filter_by(id=tutor_id, ativo=True).first()
        if not tutor:
            return jsonify({"ok": False, "error": "Tutor não encontrado."}), 404

        voto = Voto(aluno_nome=aluno, serie=serie, tutor_id=tutor.id)
        db.session.add(voto)
        db.session.commit()

        return jsonify({"ok": True})

    # ---------------------------
    # Admin auth
    # ---------------------------
    @app.get("/gestao/login")
    def gestao_login_page():
        return render_template("login.html")

    @app.post("/gestao/login")
    def gestao_login():
        pwd = (request.form.get("senha") or "").strip()
        if admin_password_ok(pwd):
            session["admin"] = True
            return redirect(url_for("gestao"))
        return render_template("login.html", erro="Senha incorreta.")

    @app.get("/gestao/logout")
    def gestao_logout():
        session.clear()
        return redirect(url_for("index"))

    @app.get("/gestao")
    def gestao():
        if not require_admin():
            return redirect(url_for("gestao_login_page"))
        tutores = Tutor.query.order_by(Tutor.nome.asc()).all()
        capacidade = get_capacidade()
        return render_template("gestao.html", tutores=tutores, capacidade=capacidade)

    # ---------------------------
    # Admin APIs
    # ---------------------------
    @app.get("/api/admin/tutores")
    def api_admin_tutores_list():
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado"}), 401

        tutores = Tutor.query.order_by(Tutor.nome.asc()).all()
        return jsonify({"ok": True, "tutores": [
            {"id": t.id, "nome": t.nome, "ativo": t.ativo}
            for t in tutores
        ]})

    @app.post("/api/admin/tutores")
    def api_admin_tutores_add():
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado"}), 401

        data = request.get_json(silent=True) or {}
        nome = (data.get("nome") or "").strip()
        if not nome:
            return jsonify({"ok": False, "error": "Informe o nome do tutor."}), 400

        existing = Tutor.query.filter(db.func.lower(Tutor.nome) == nome.lower()).first()
        if existing:
            existing.ativo = True
            db.session.commit()
            return jsonify({"ok": True, "id": existing.id, "reused": True})

        t = Tutor(nome=nome, ativo=True)
        db.session.add(t)
        db.session.commit()
        return jsonify({"ok": True, "id": t.id})

    @app.delete("/api/admin/tutores/<int:tutor_id>")
    def api_admin_tutores_delete(tutor_id: int):
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado"}), 401

        t = Tutor.query.get(tutor_id)
        if not t:
            return jsonify({"ok": False, "error": "Tutor não encontrado"}), 404

        db.session.delete(t)
        db.session.commit()
        return jsonify({"ok": True})

    @app.post("/api/admin/capacidade")
    def api_admin_capacidade():
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado"}), 401
        data = request.get_json(silent=True) or {}
        cap = data.get("capacidade")
        if cap is None:
            return jsonify({"ok": False, "error": "capacidade ausente"}), 400
        cap = set_capacidade(int(cap))
        return jsonify({"ok": True, "capacidade": cap})

    @app.get("/api/admin/resultados")
    def api_admin_resultados():
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado"}), 401

        capacidade = get_capacidade()

        tutores = Tutor.query.order_by(Tutor.nome.asc()).all()
        out = []
        total_geral = 0

        for t in tutores:
            votos = (Voto.query
                     .filter_by(tutor_id=t.id)
                     .order_by(Voto.created_at.asc(), Voto.id.asc())
                     .all())
            total = len(votos)
            total_geral += total

            selecionados = votos[:capacidade]
            fora = votos[capacidade:]

            out.append({
                "id": t.id,
                "nome": t.nome,
                "ativo": t.ativo,
                "total": total,
                "capacidade": capacidade,
                "selecionados": [
                    {"aluno": v.aluno_nome, "serie": v.serie, "data": (v.created_at.isoformat() if v.created_at else "")}
                    for v in selecionados
                ],
                "fora": [
                    {"aluno": v.aluno_nome, "serie": v.serie, "data": (v.created_at.isoformat() if v.created_at else "")}
                    for v in fora
                ],
            })

        return jsonify({"ok": True, "capacidade": capacidade, "total_geral": total_geral, "resultados": out})

    return app


# Gunicorn entrypoint
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
