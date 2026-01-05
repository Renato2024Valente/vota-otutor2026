import os
import random
import re
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

# -----------------------------
# Config
# -----------------------------
db = SQLAlchemy()

DEFAULT_TUTORES = [
    "ALINE DAL PONTE SABBAG",
    "ALINE PRISCILA GARCIA DA SILVA",
    "ANDREIA DE FATIMA GOMES PIEMONTE",
    "ANTONIO JOSÉ DO SANTOS JUNIOR",
    "CAIO HENRIQUE ESTRELA CARDIA",
    "CLEBER ALBERTO GOMES",
    "CRISTINA BALDINOTI",
    "EDCARLOS DOS SANTOS",
    "EDINEIA APARECIDA DE SOUSA",
    "ELIANE ANDREA DIOMEDES",
    "ELIZA GILIOLLI DOS SANTOS",
    "FELIPE BEIRO DE ALMEIDA",
    "FLAVIO HENRIQUE CHAVES FILHO",
    "GABRIEL RODRIGUES DA SILVA",
    "GISLAINE DIAS CAPUTO",
    "GRAZIELLE CHRISTINE MARANGONI SCARMANHÃ",
    "GRAZIELLE DE OLIVEIRA SANTOS",
    "ITALO BERTONCINI",
    "JANAINA TOGNON",
    "JAQUELINE PADERES SCORSAFAVA GARCIA",
    "JOSELILIAN LOPES MIRALHA",
    "JULIANA DE FATIMA SILVA SEGANTIN",
    "KLEER GONÇALVES DOS SANTOS",
    "LEANDRO HENRIQUE DE SOUZA BEZERRA",
    "LUCILENE ARAUJO ROMANIW RAYMUNDO",
    "MAGDA APARECIDA DE OLIVEIRA PRADO",
    "MARCIO ENRIQUE STANCKEVIZ",
    "MARIA CANDIDA BRANCO DOS SANTOS",
    "MARIA LUIZA MARTINS DE ARAUJO",
    "MARIANA PAIVA RAMOS",
    "MARIANA SAKER DE CASTRO PAIVA",
    "MATHEUS SANTOS DE OLIVEIRA",
    "MILCE FERREIRA DE MOURA",
    "MIRIAM BEIRO DE ALMEIDA",
    "NATHÁLIA VERONESE MARTINS",
    "ORIEL DE OLIVEIRA E SILVA",
    "RAQUEL CRISTINA ROSSIGALLI BOLFI",
    "RENATO DAVID VALENTE",
    "RODRIGO BATISTA",
    "ROSANA APARECIDA ROSSI NOGUEIRA",
    "SAMUEL MACEDO PERICO",
    "SAVIA BETHANIA CAVALCANTI",
    "SILENE BERTASSI",
    "SONIA MARIA NABAS DOS SANTOS",
    "SUELI BATISTETTI VICENTE",
    "SUZANA CARTLA VIANA JANUÁRIO",
    "VERA CLAUDIA FERRES ANSUINO",
]


def utcnow():
    return datetime.now(timezone.utc)


def normalize_database_url(url: str) -> str:
    """
    - Converte postgresql:// -> postgresql+psycopg:// (SQLAlchemy)
    - Garante sslmode=require quando for URL do Render (seguro usar sempre)
    """
    if not url:
        return url
    url = url.strip()

    # SQLAlchemy driver
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    # adiciona sslmode=require se não existir
    if "sslmode=" not in url:
        if "?" in url:
            url = url + "&sslmode=require"
        else:
            url = url + "?sslmode=require"
    return url


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    admin_password = os.environ.get("ADMIN_PASSWORD", "1243##")
    app.config["ADMIN_PASSWORD"] = admin_password

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL não foi definido. Configure no Render (Environment) ou em .env local."
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = normalize_database_url(db_url)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_tutores()

    # -----------------------------
    # Helpers
    # -----------------------------
    def require_admin():
        return bool(session.get("admin_ok"))

    def is_valid_name(s: str) -> bool:
        if not s:
            return False
        s = s.strip()
        if len(s) < 3 or len(s) > 80:
            return False
        # permite letras, acentos, espaços e pontuação básica
        return bool(re.fullmatch(r"[A-Za-zÀ-ÿ0-9 .,'\-]{3,80}", s))

    def is_valid_serie(s: str) -> bool:
        if not s:
            return False
        s = s.strip()
        return 1 <= len(s) <= 20

    # -----------------------------
    # Pages
    # -----------------------------
    @app.get("/")
    def page_vote():
        return render_template("index.html")

    @app.get("/admin")
    def page_admin():
        if not require_admin():
            return redirect(url_for("page_admin_login"))
        return render_template("admin.html")

    @app.get("/admin/login")
    def page_admin_login():
        if require_admin():
            return redirect(url_for("page_admin"))
        return render_template("admin_login.html")

    @app.get("/admin/logout")
    def admin_logout():
        session.pop("admin_ok", None)
        return redirect(url_for("page_admin_login"))

    # -----------------------------
    # Public API
    # -----------------------------
    @app.get("/api/tutores")
    def api_tutores():
        tutores = Tutor.query.filter_by(ativo=True).order_by(Tutor.nome.asc()).all()
        return jsonify([{"id": t.id, "nome": t.nome} for t in tutores])

    @app.post("/api/votar")
    def api_votar():
        data = request.get_json(force=True, silent=True) or {}
        aluno = (data.get("aluno") or "").strip()
        serie = (data.get("serie") or "").strip()
        tutor_id = data.get("tutor_id")

        if not is_valid_name(aluno):
            return jsonify({"ok": False, "error": "Nome inválido. Digite seu nome completo."}), 400
        if not is_valid_serie(serie):
            return jsonify({"ok": False, "error": "Série inválida."}), 400
        try:
            tutor_id = int(tutor_id)
        except Exception:
            return jsonify({"ok": False, "error": "Selecione um tutor(a)."}), 400

        tutor = Tutor.query.filter_by(id=tutor_id, ativo=True).first()
        if not tutor:
            return jsonify({"ok": False, "error": "Tutor(a) não encontrado(a)."}), 404

        # registro do voto
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "")[:80]
        ua = (request.headers.get("User-Agent") or "")[:200]

        voto = Voto(aluno=aluno, serie=serie, tutor_id=tutor.id, ip=ip, user_agent=ua)
        db.session.add(voto)
        db.session.commit()

        return jsonify({"ok": True, "message": "Voto confirmado com sucesso!", "tutor": tutor.nome})

    @app.get("/api/resultados")
    def api_resultados():
        """
        Retorna:
        - contagem por tutor
        - total de votos
        - para cada tutor acima de 100 votos, se existe amostragem e quantos selecionados
        """
        # SQL simples para performance
        rows = db.session.execute(
            db.text("""
                SELECT t.id, t.nome, COUNT(v.id) AS votos
                FROM tutores t
                LEFT JOIN votos v ON v.tutor_id = t.id
                WHERE t.ativo = true
                GROUP BY t.id, t.nome
                ORDER BY votos DESC, t.nome ASC
            """)
        ).all()

        total = sum(int(r.votos) for r in rows)

        # amostragem mais recente por tutor
        amostras = db.session.execute(
            db.text("""
                SELECT a.tutor_id, a.id AS amostragem_id, a.quantidade, a.criado_em
                FROM amostragens a
                JOIN (
                    SELECT tutor_id, MAX(id) AS max_id
                    FROM amostragens
                    GROUP BY tutor_id
                ) x ON x.tutor_id = a.tutor_id AND x.max_id = a.id
            """)
        ).all()
        am_map = {int(a.tutor_id): {"amostragem_id": int(a.amostragem_id), "quantidade": int(a.quantidade), "criado_em": a.criado_em.isoformat()} for a in amostras}

        out = []
        for r in rows:
            tid = int(r.id)
            votos = int(r.votos)
            item = {"id": tid, "nome": r.nome, "votos": votos}
            if votos > 100:
                item["precisa_amostragem"] = True
                item["amostragem"] = am_map.get(tid)
            else:
                item["precisa_amostragem"] = False
                item["amostragem"] = None
            out.append(item)

        return jsonify({"total": total, "tutores": out})

    # -----------------------------
    # Admin API
    # -----------------------------
    @app.post("/api/admin/login")
    def api_admin_login():
        data = request.get_json(force=True, silent=True) or {}
        senha = (data.get("senha") or "")
        if senha == app.config["ADMIN_PASSWORD"]:
            session["admin_ok"] = True
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "Senha incorreta."}), 401

    @app.get("/api/admin/me")
    def api_admin_me():
        return jsonify({"ok": bool(session.get("admin_ok"))})

    @app.post("/api/admin/tutores")
    def api_admin_add_tutor():
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado."}), 401
        data = request.get_json(force=True, silent=True) or {}
        nome = (data.get("nome") or "").strip().upper()
        if not nome or len(nome) < 3:
            return jsonify({"ok": False, "error": "Nome inválido."}), 400

        existente = Tutor.query.filter(db.func.upper(Tutor.nome) == nome).first()
        if existente:
            existente.ativo = True
            existente.nome = nome
            db.session.commit()
            return jsonify({"ok": True, "message": "Tutor reativado/atualizado.", "id": existente.id})

        t = Tutor(nome=nome, ativo=True)
        db.session.add(t)
        db.session.commit()
        return jsonify({"ok": True, "message": "Tutor adicionado.", "id": t.id})

    @app.delete("/api/admin/tutores/<int:tutor_id>")
    def api_admin_remove_tutor(tutor_id: int):
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado."}), 401
        t = Tutor.query.get(tutor_id)
        if not t:
            return jsonify({"ok": False, "error": "Tutor não encontrado."}), 404
        t.ativo = False
        db.session.commit()
        return jsonify({"ok": True, "message": "Tutor removido (desativado)."})


    @app.post("/api/admin/amostragem/<int:tutor_id>")
    def api_admin_gerar_amostragem(tutor_id: int):
        """
        Para tutores com mais de 100 votos, gera uma amostragem aleatória de 16 a 18 alunos.
        Guarda no banco (amostragem + itens) e retorna a lista selecionada.
        """
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado."}), 401

        tutor = Tutor.query.filter_by(id=tutor_id, ativo=True).first()
        if not tutor:
            return jsonify({"ok": False, "error": "Tutor não encontrado."}), 404

        votos = Voto.query.filter_by(tutor_id=tutor_id).order_by(Voto.criado_em.asc()).all()
        qtd_votos = len(votos)
        if qtd_votos == 0:
            return jsonify({"ok": False, "error": "Esse tutor ainda não recebeu votos."}), 400

        if qtd_votos <= 100:
            # abaixo do limite: retorna a lista completa
            return jsonify({
                "ok": True,
                "message": "Tutor com até 100 votos: lista completa (sem amostragem).",
                "tutor": tutor.nome,
                "amostragem": None,
                "selecionados": [{"aluno": v.aluno, "serie": v.serie, "data": v.criado_em.isoformat()} for v in votos],
            })

        n = random.randint(16, 18)
        n = min(n, qtd_votos)
        seed = int(utcnow().timestamp())
        rng = random.Random(seed)
        selecionados = rng.sample(votos, k=n)

        # salva
        a = Amostragem(tutor_id=tutor_id, quantidade=n, seed=seed)
        db.session.add(a)
        db.session.flush()  # pega a.id

        for v in selecionados:
            db.session.add(AmostraItem(amostragem_id=a.id, voto_id=v.id))

        db.session.commit()

        return jsonify({
            "ok": True,
            "message": "Amostragem gerada com sucesso.",
            "tutor": tutor.nome,
            "amostragem": {"id": a.id, "quantidade": n, "seed": seed, "criado_em": a.criado_em.isoformat()},
            "selecionados": [{"aluno": v.aluno, "serie": v.serie, "data": v.criado_em.isoformat()} for v in selecionados],
        })

    @app.get("/api/admin/amostragem/<int:tutor_id>/ultima")
    def api_admin_ver_ultima_amostragem(tutor_id: int):
        if not require_admin():
            return jsonify({"ok": False, "error": "Não autorizado."}), 401
        tutor = Tutor.query.get(tutor_id)
        if not tutor:
            return jsonify({"ok": False, "error": "Tutor não encontrado."}), 404

        a = Amostragem.query.filter_by(tutor_id=tutor_id).order_by(Amostragem.id.desc()).first()
        if not a:
            return jsonify({"ok": True, "message": "Ainda não existe amostragem para esse tutor.", "amostragem": None, "selecionados": []})

        itens = (
            db.session.query(Voto.aluno, Voto.serie, Voto.criado_em)
            .join(AmostraItem, AmostraItem.voto_id == Voto.id)
            .filter(AmostraItem.amostragem_id == a.id)
            .order_by(Voto.aluno.asc())
            .all()
        )
        return jsonify({
            "ok": True,
            "tutor": tutor.nome,
            "amostragem": {"id": a.id, "quantidade": a.quantidade, "seed": a.seed, "criado_em": a.criado_em.isoformat()},
            "selecionados": [{"aluno": i.aluno, "serie": i.serie, "data": i.criado_em.isoformat()} for i in itens],
        })

    return app


# -----------------------------
# Models
# -----------------------------
class Tutor(db.Model):
    __tablename__ = "tutores"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), unique=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    criado_em = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class Voto(db.Model):
    __tablename__ = "votos"
    id = db.Column(db.Integer, primary_key=True)
    aluno = db.Column(db.String(80), nullable=False)
    serie = db.Column(db.String(20), nullable=False)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutores.id"), nullable=False)
    criado_em = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    ip = db.Column(db.String(80))
    user_agent = db.Column(db.String(200))


class Amostragem(db.Model):
    __tablename__ = "amostragens"
    id = db.Column(db.Integer, primary_key=True)
    tutor_id = db.Column(db.Integer, db.ForeignKey("tutores.id"), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    seed = db.Column(db.BigInteger, nullable=False)
    criado_em = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class AmostraItem(db.Model):
    __tablename__ = "amostragem_itens"
    id = db.Column(db.Integer, primary_key=True)
    amostragem_id = db.Column(db.Integer, db.ForeignKey("amostragens.id"), nullable=False)
    voto_id = db.Column(db.Integer, db.ForeignKey("votos.id"), nullable=False)


def seed_tutores():
    # Se a tabela estiver vazia, insere a lista padrão
    if Tutor.query.count() == 0:
        for nome in DEFAULT_TUTORES:
            db.session.add(Tutor(nome=nome.strip().upper(), ativo=True))
        db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
