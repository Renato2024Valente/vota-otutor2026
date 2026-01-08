# Votação de Tutores 2026 (Flask + Postgres Render)

## Rodar local
1) Crie e ative venv:
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
```

2) Instale:
```bash
pip install -r requirements.txt
```

3) Configure `.env` (opcional):
```env
# Externo (para rodar no PC)
DATABASE_URL=postgresql+psycopg://tutor2026_user:SENHA@dpg-xxxx.oregon-postgres.render.com:5432/tutor2026?sslmode=require
ADMIN_PASSWORD=1243##
SECRET_KEY=troque-por-uma-chave-forte
```

4) Rode:
```bash
python app.py
```

## Deploy no Render
No seu Web Service (Environment), adicione:
- `DATABASE_URL` = **INTERNAL DATABASE URL** do Render (ou Connection string), ex:
  `postgresql://tutor2026_user:...@dpg-xxxx/tutor2026`
  (o app converte e aplica `sslmode=require` automaticamente)
- `ADMIN_PASSWORD` = `1243##` (ou outra)
- `SECRET_KEY` = uma string longa

Start command:
- `gunicorn app:app`

## Capacidade (16 a 18)
Na Gestão, você escolhe 16/17/18.
- **Selecionados**: primeiros votos (ordem de chegada) até a capacidade
- **Fora/Espera**: todos os demais

A tela da gestão atualiza automaticamente a cada 3 segundos.
