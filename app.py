import os
import datetime as _dt
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text, inspect
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

DEFAULT_ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1243##")
DEFAULT_SECRET_KEY = os.environ.get("SECRET_KEY", "bicudo-2026-secret-key")
DEFAULT_CAPACITY = 16

# Séries fixas (não muda)
SERIES = [
    "6º Ano A", "6º Ano B", "6º Ano C", "6º Ano D",
    "7º Ano A", "7º Ano B", "7º Ano C", "7º Ano D",
    "8º Ano A", "8º Ano B", "8º Ano C", "8º Ano D",
    "9º Ano A", "9º Ano B", "9º Ano C", "9º Ano D",
    "1º Ano A", "1º Ano B", "1º Ano C",
    "2º Ano A", "2º Tec",
    "3º Ano A", "3º Ano B",
]

# Tutores fixos (não muda). True=Ativo, False=Inativo
TUTORES_SEMENTE = [
    ("ALINE DAL PONTE SABBAG", True),
    ("ALINE PRISCILA GARCIA DA SILVA", True),
    ("ANDREIA DE FATIMA GOMES PIEMONTE", True),
    ("ANTONIO JOSÉ DO SANTOS JUNIOR", True),
    ("CAIO HENRIQUE ESTRELA CARDIA", True),
    ("CLEBER ALBERTO GOMES", True),
    ("CRISTINA BALDINOTI", True),
    ("EDCARLOS DOS SANTOS", True),
    ("EDINEIA APARECIDA DE SOUSA", True),
    ("ELIANE ANDREA DIOMEDES", True),
    ("ELIZA GILIOLLI DOS SANTOS", True),
    ("FELIPE BEIRO DE ALMEIDA", True),
    ("FLAVIO HENRIQUE CHAVES FILHO", True),
    ("GABRIEL RODRIGUES DA SILVA", True),
    ("GISLAINE DIAS CAPUTO", True),
    ("GRAZIELLE CHRISTINE MARANGONI SCARMANHÃ", True),
    ("GRAZIELLE DE OLIVEIRA SANTOS", True),
    ("ITALO BERTONCINI", True),
    ("IZAIAS NOGUEIRA RODRIGUES", False),
    ("JANAINA TOGNON", True),
    ("JAQUELINE PADERES SCORSAFAVA GARCIA", True),
    ("JOSELILIAN LOPES MIRALHA", True),
    ("JULIANA DE FATIMA SILVA SEGANTIN", True),
    ("Juliana Goes", True),
    ("KLEER GONÇALVES DOS SANTOS", True),
    ("LEANDRO HENRIQUE DE SOUZA BEZERRA", True),
    ("LUCILENE ARAUJO ROMANIW RAYMUNDO", True),
    ("LURDES DOS SANTOS ELIAS LIMA", False),
    ("MAGDA APARECIDA DE OLIVEIRA PRADO", True),
    ("MARCIA CRISTINA SIGEMURA", False),
    ("MARCIO ENRIQUE STANCKEVIZ", True),
    ("MARIA CANDIDA BRANCO DOS SANTOS", True),
    ("MARIA LUIZA MARTINS DE ARAUJO", True),
    ("MARIANA PAIVA RAMOS", True),
    ("MARIANA SAKER DE CASTRO PAIVA", True),
    ("MATHEUS SANTOS DE OLIVEIRA", True),
    ("MILCE FERREIRA DE MOURA", True),
    ("MIRIAM BEIRO DE ALMEIDA", True),
    ("NATHÁLIA VERONESE MARTINS", True),
    ("ORIEL DE OLIVEIRA E SILVA", True),
    ("RAFAEL MARTINS DOS SANTOS", False),
    ("RAQUEL CRISTINA ROSSIGALLI BOLFI", True),
    ("RENATO DAVID VALENTE", True),
    ("RODRIGO BATISTA", True),
    ("ROSANA APARECIDA ROSSI NOGUEIRA", True),
    ("SAMUEL MACEDO PERICO", True),
    ("SAVIA BETHANIA CAVALCANTI", True),
    ("SILENE BERTASSI", True),
    ("SONIA MARIA NABAS DOS SANTOS", True),
    ("SUELI BATISTETTI VICENTE", True),
    ("SUZANA CARTLA VIANA JANUÁRIO", True),
    ("VERA CLAUDIA FERRES ANSUINO", True),
]


def normalize_database_url(url: str | None) -> str | None:
    """Normaliza URL do Render + psycopg3 + SSL externo."""
    if not url:
        return None
    url = url.strip()

    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    if "oregon-postgres.render.com" in url and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"

    return url


# =========================
# MODELOS (namespaced)
# =========================
# Usamos nomes de tabelas com prefixo "tv_" para NÃO conflitar com tabelas antigas
# no mesmo banco (tutores/votos/config etc.).
class TVConfig(db.Model):
    # nome próprio para não conflitar com tabelas antigas
    __tablename__ = "tv_app_config"
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(256), nullable=False)


class TVTutor(db.Model):
    __tablename__ = "tv_tutores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160), unique=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=_dt.datetime.utcnow, nullable=False)


class TVVoto(db.Model):
    __tablename__ = "tv_votos"
    id = db.Column(db.Integer, primary_key=True)
    aluno_nome = db.Column(db.String(160), nullable=False)
    serie = db.Column(db.String(40), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tv_tutores.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=_dt.datetime.utcnow, nullable=False)

    tutor = db.relationship("TVTutor", backref=db.backref("votos", lazy=True))


# =========================
# SCHEMA GUARD (auto-fix)
# =========================
def _colset(insp, table_name: str) -> set[str]:
    try:
        return {c["name"] for c in insp.get_columns(table_name)}
    except Exception:
        return set()


def ensure_tv_schema() -> None:
    """Garante que as tabelas tv_* existam e tenham as colunas necessárias.

    Isso evita os erros comuns do Render quando o banco já tinha tabelas antigas
    com outro formato (create_all() não migra schema).
    """
    engine = db.engine
    dialect = engine.dialect.name
    with engine.begin() as conn:
        # 1) cria tabelas se não existirem (DDL por dialeto)
        if dialect == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tv_app_config (
                      key TEXT PRIMARY KEY,
                      value TEXT NOT NULL
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tv_tutores (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      nome TEXT UNIQUE NOT NULL,
                      ativo INTEGER NOT NULL DEFAULT 1,
                      created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tv_votos (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      aluno_nome TEXT NOT NULL,
                      serie TEXT NOT NULL,
                      tutor_id INTEGER NOT NULL,
                      created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    """
                )
            )
        else:
            # Postgres (Render)
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tv_app_config (
                      key VARCHAR(64) PRIMARY KEY,
                      value VARCHAR(256) NOT NULL
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tv_tutores (
                      id SERIAL PRIMARY KEY,
                      nome VARCHAR(160) UNIQUE NOT NULL,
                      ativo BOOLEAN NOT NULL DEFAULT TRUE,
                      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS tv_votos (
                      id SERIAL PRIMARY KEY,
                      aluno_nome VARCHAR(160) NOT NULL,
                      serie VARCHAR(40) NOT NULL,
                      tutor_id INTEGER NOT NULL REFERENCES tv_tutores(id),
                      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
            )

        # Recarrega inspector depois do DDL (evita cache)
        insp = inspect(conn)

        # Recarrega o inspector após DDL (evita cache)
        insp = inspect(conn)

        # 2) adiciona colunas faltantes (caso já exista tabela com schema parcial)
        cols_cfg = _colset(insp, "tv_app_config")
        cols_tutores = _colset(insp, "tv_tutores")
        cols_votos = _colset(insp, "tv_votos")

        def add_col(table: str, col_sql_sqlite: str, col_sql_pg: str):
            if dialect == "sqlite":
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_sql_sqlite};"))
            else:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_sql_pg};"))

        # tv_app_config
        if "key" not in cols_cfg:
            add_col("tv_app_config", "key TEXT", "key VARCHAR(64)")
        if "value" not in cols_cfg:
            add_col("tv_app_config", "value TEXT", "value VARCHAR(256)")

        # tv_tutores
        if "ativo" not in cols_tutores:
            add_col("tv_tutores", "ativo INTEGER DEFAULT 1", "ativo BOOLEAN DEFAULT TRUE")
        if "created_at" not in cols_tutores:
            add_col("tv_tutores", "created_at TEXT DEFAULT (datetime('now'))", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        # compatibilidade: alguns bancos antigos têm 'criado_em' NOT NULL
        if dialect != "sqlite" and "criado_em" in cols_tutores:
            conn.execute(text("ALTER TABLE tv_tutores ALTER COLUMN criado_em SET DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("UPDATE tv_tutores SET criado_em = COALESCE(criado_em, created_at, CURRENT_TIMESTAMP) WHERE criado_em IS NULL;"))

        # tv_votos
        if "aluno_nome" not in cols_votos:
            add_col("tv_votos", "aluno_nome TEXT", "aluno_nome VARCHAR(160)")
        if "serie" not in cols_votos:
            add_col("tv_votos", "serie TEXT", "serie VARCHAR(40)")
        if "tutor_id" not in cols_votos:
            add_col("tv_votos", "tutor_id INTEGER", "tutor_id INTEGER")
        if "created_at" not in cols_votos:
            add_col("tv_votos", "created_at TEXT DEFAULT (datetime('now'))", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        if dialect != "sqlite" and "criado_em" in cols_votos:
            conn.execute(text("ALTER TABLE tv_votos ALTER COLUMN criado_em SET DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("UPDATE tv_votos SET criado_em = COALESCE(criado_em, created_at, CURRENT_TIMESTAMP) WHERE criado_em IS NULL;"))

        # 3) garante defaults no Postgres (no SQLite é ok)
        if dialect == "postgresql":
            conn.execute(text("ALTER TABLE tv_tutores ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;"))
            conn.execute(text("ALTER TABLE tv_votos ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP;"))



def clamp_capacity(n: int) -> int:
    return max(16, min(18, int(n)))


def get_capacity() -> int:
    cfg = TVConfig.query.filter_by(key="capacity").first()
    try:
        cap = int(cfg.value) if cfg else DEFAULT_CAPACITY
    except Exception:
        cap = DEFAULT_CAPACITY
    return clamp_capacity(cap)


def set_capacity(value: int) -> None:
    value = clamp_capacity(value)
    cfg = TVConfig.query.filter_by(key="capacity").first()
    if not cfg:
        cfg = TVConfig(key="capacity", value=str(value))
        db.session.add(cfg)
    else:
        cfg.value = str(value)
    db.session.commit()


def admin_required(fn):
    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)

    return _wrap


def init_db_and_seed(app: Flask) -> None:
    """Cria tabelas do app e carrega seed (sem mexer nas tabelas antigas)."""
    with app.app_context():
        # 1) garante schema mesmo em bancos "bagunçados" (Render)
        ensure_tv_schema()
        # 2) cria/valida tabelas do ORM
        db.create_all()

        # capacity default
        if not TVConfig.query.filter_by(key="capacity").first():
            db.session.add(TVConfig(key="capacity", value=str(DEFAULT_CAPACITY)))
            db.session.commit()

        # seed tutores: adiciona os que faltarem (sem sobrescrever alterações da gestão)
        existing = {t.nome for t in TVTutor.query.with_entities(TVTutor.nome).all()}
        added = False
        for nome, ativo in TUTORES_SEMENTE:
            if nome not in existing:
                db.session.add(TVTutor(nome=nome, ativo=bool(ativo)))
                added = True
        if added:
            db.session.commit()


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = DEFAULT_SECRET_KEY

    db_url = normalize_database_url(os.environ.get("DATABASE_URL"))
    if not db_url:
        # fallback local
        db_path = os.path.join(os.path.dirname(__file__), "local.sqlite")
        db_url = "sqlite:///" + db_path

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    init_db_and_seed(app)

    # ===== Votação =====
    @app.get("/")
    def index():
        tutores = TVTutor.query.filter_by(ativo=True).order_by(TVTutor.nome.asc()).all()
        return render_template("index.html", tutores=tutores, series=SERIES)

    @app.post("/api/vote")
    def api_vote():
        data = request.get_json(silent=True) or {}
        aluno_nome = (data.get("aluno_nome") or "").strip()
        serie = (data.get("serie") or "").strip()
        tutor_id = data.get("tutor_id")

        if not aluno_nome or not serie or not tutor_id:
            return jsonify({"ok": False, "message": "Preencha nome, série e tutor."}), 400
        if serie not in SERIES:
            return jsonify({"ok": False, "message": "Série inválida."}), 400

        tutor = TVTutor.query.filter_by(id=int(tutor_id), ativo=True).first()
        if not tutor:
            return jsonify({"ok": False, "message": "Tutor inválido ou inativo."}), 400

        try:
            voto = TVVoto(aluno_nome=aluno_nome, serie=serie, tutor_id=tutor.id)
            db.session.add(voto)
            db.session.commit()
            return jsonify({"ok": True, "message": f"Voto registrado para {tutor.nome}!"})
        except SQLAlchemyError as e:
            # Tenta auto-corrigir schema e regravar 1 vez
            db.session.rollback()
            try:
                ensure_tv_schema()
                db.session.add(TVVoto(aluno_nome=aluno_nome, serie=serie, tutor_id=tutor.id))
                db.session.commit()
                return jsonify({"ok": True, "message": f"Voto registrado para {tutor.nome}!"})
            except Exception:
                db.session.rollback()
                return jsonify({"ok": False, "message": "Erro ao registrar voto (banco). Avise a gestão."}), 500

    # fallback (caso JS falhe): POST normal
    @app.post("/vote")
    def vote_form():
        aluno_nome = (request.form.get("aluno_nome") or "").strip()
        serie = (request.form.get("serie") or "").strip()
        tutor_id = (request.form.get("tutor_id") or "").strip()

        if not aluno_nome or not serie or not tutor_id:
            flash("Preencha nome, série e tutor.", "warning")
            return redirect(url_for("index"))
        if serie not in SERIES:
            flash("Série inválida.", "warning")
            return redirect(url_for("index"))

        tutor = TVTutor.query.filter_by(id=int(tutor_id), ativo=True).first()
        if not tutor:
            flash("Tutor inválido ou inativo.", "warning")
            return redirect(url_for("index"))

        try:
            db.session.add(TVVoto(aluno_nome=aluno_nome, serie=serie, tutor_id=tutor.id))
            db.session.commit()
            flash(f"Voto registrado para {tutor.nome}!", "success")
        except SQLAlchemyError:
            db.session.rollback()
            try:
                ensure_tv_schema()
                db.session.add(TVVoto(aluno_nome=aluno_nome, serie=serie, tutor_id=tutor.id))
                db.session.commit()
                flash(f"Voto registrado para {tutor.nome}!", "success")
            except Exception:
                db.session.rollback()
                flash("Erro ao registrar voto (banco). Avise a gestão.", "danger")

        return redirect(url_for("index"))

    # ===== Gestão =====
    @app.get("/admin/login")
    def admin_login():
        return render_template("admin_login.html")

    @app.post("/admin/login")
    def admin_login_post():
        pwd = (request.form.get("password") or "").strip()
        if pwd == DEFAULT_ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        flash("Senha inválida.", "danger")
        return redirect(url_for("admin_login"))

    @app.get("/admin/logout")
    def admin_logout():
        session.clear()
        return redirect(url_for("index"))

    @app.get("/admin")
    @admin_required
    def admin():
        tutores = TVTutor.query.order_by(TVTutor.nome.asc()).all()
        return render_template("admin.html", tutores=tutores, capacity=get_capacity())

    @app.post("/admin/capacity")
    @admin_required
    def admin_capacity():
        cap = request.form.get("capacity", DEFAULT_CAPACITY)
        try:
            set_capacity(int(cap))
            flash(f"Capacidade salva: {get_capacity()}", "success")
        except Exception:
            flash("Não foi possível salvar a capacidade.", "danger")
        return redirect(url_for("admin"))

    @app.post("/admin/tutores/add")
    @admin_required
    def admin_add_tutor():
        nome = (request.form.get("nome") or "").strip()
        if nome and not TVTutor.query.filter_by(nome=nome).first():
            db.session.add(TVTutor(nome=nome, ativo=True))
            db.session.commit()
        return redirect(url_for("admin"))

    @app.post("/admin/tutores/toggle/<int:tutor_id>")
    @admin_required
    def admin_toggle_tutor(tutor_id: int):
        t = TVTutor.query.get_or_404(tutor_id)
        t.ativo = not t.ativo
        db.session.commit()
        return redirect(url_for("admin"))

    @app.post("/admin/tutores/delete/<int:tutor_id>")
    @admin_required
    def admin_delete_tutor(tutor_id: int):
        # não apaga (pra não perder histórico): apenas inativa
        t = TVTutor.query.get_or_404(tutor_id)
        t.ativo = False
        db.session.commit()
        return redirect(url_for("admin"))

    @app.get("/api/admin/overview")
    @admin_required
    def api_admin_overview():
        cap = get_capacity()
        tutores = TVTutor.query.order_by(TVTutor.nome.asc()).all()

        out = {
            "capacity": cap,
            "generated_at": _dt.datetime.utcnow().isoformat(),
            "tutores": [],
        }

        for t in tutores:
            votos = (
                TVVoto.query.filter_by(tutor_id=t.id)
                .order_by(TVVoto.created_at.asc(), TVVoto.id.asc())
                .all()
            )
            selecionados = votos[:cap]
            fila = votos[cap:]

            out["tutores"].append(
                {
                    "id": t.id,
                    "nome": t.nome,
                    "ativo": bool(t.ativo),
                    "total": len(votos),
                    "selecionados": [{"aluno_nome": v.aluno_nome, "serie": v.serie} for v in selecionados],
                    "fila": [{"aluno_nome": v.aluno_nome, "serie": v.serie} for v in fila],
                }
            )

        return jsonify(out)

    return app


app = create_app()

if __name__ == "__main__":
    # Windows: use python app.py (gunicorn não roda no Windows por causa do fcntl)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
