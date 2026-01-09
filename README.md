# Votação de Tutores 2026 (Bicudo)

## Rodar local
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

> Observação: **gunicorn não roda no Windows** (erro `fcntl`). No PC use `python app.py`.

Se quiser usar Postgres do Render no PC, crie um `.env`:
```
DATABASE_URL=postgresql://...oregon-postgres.render.com:5432/... ?sslmode=require
ADMIN_PASSWORD=1243##
SECRET_KEY=...
```

## Deploy no Render
- Start command: `gunicorn app:app`
- Environment:
  - `DATABASE_URL` (use a INTERNAL DATABASE URL no Render)
  - `SECRET_KEY`
  - `ADMIN_PASSWORD`

## Gestão
- Acesse `/admin`
- Senha: `ADMIN_PASSWORD` (padrão: 1243##)
- Capacidade da amostra: 16 a 18
- Atualização automática de 3 em 3 segundos (Selecionados e Lista de espera)

## Tabelas no banco
Este projeto cria tabelas com prefixo **tv_** para não conflitar com outras aplicações:
- `tv_tutores`
- `tv_votos`
- `tv_app_config`
