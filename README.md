# Tutoria 2026 — Votação de Tutores (Flask + PostgreSQL)

## O que tem aqui
- Tela linda para o aluno votar (PC e celular).
- Som de confirmação no voto.
- Painel da gestão com senha (ADMIN_PASSWORD) para:
  - ver resultados em tempo real
  - adicionar/remover tutores (desativar)
  - gerar amostragem automática de 16–18 alunos quando um tutor passar de 100 votos

## Rodar no PC (Windows)
1) Crie e ative o venv:
```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2) Instale dependências:
```bash
pip install -r requirements.txt
```

3) Crie um arquivo `.env` (pode copiar de `.env.example`) e coloque a **EXTERNAL DATABASE URL** do Render.

4) Rode:
```bash
python app.py
```
Acesse: http://127.0.0.1:5000

## Deploy no Render
1) Suba esse projeto no GitHub.
2) No Render: New → Web Service → conecte o repo.
3) Em **Environment Variables**:
- `DATABASE_URL` = **INTERNAL DATABASE URL** do Render (a URL interna do banco)
- `ADMIN_PASSWORD` = sua senha (ex.: 1243##)
- `SECRET_KEY` = uma string grande aleatória

4) Start Command já está no `render.yaml`: `gunicorn app:app`

## Rotas
- `/` voto
- `/admin/login` login gestão
- `/admin` painel

## Observações
- Remover tutor = desativar (não apaga votos antigos).
- A amostragem salva no banco e pode ser consultada depois em "Ver lista".


## Nota (Windows / Python 3.14)
Se você estiver usando Python 3.14 e o pip reclamar do `psycopg-binary`, mantenha o `psycopg[binary]==3.2.13` (já está ajustado) ou use Python 3.12.


## Deploy no Render (2 jeitos)

### Jeito A (automático) — Blueprint (recomendado)
1) Suba esse projeto no GitHub (com o arquivo `render.yaml` na raiz).
2) No Render: **Blueprints** → **New Blueprint Instance** → selecione o repositório.
3) O Render cria automaticamente:
   - 1 banco Postgres (tutor2026-db)
   - 1 Web Service (tutor-votacao-2026)
   - e já define `DATABASE_URL` apontando pro banco.

> Observação: o Blueprint já define `ADMIN_PASSWORD=1243##` e um `SECRET_KEY` aleatório.

### Jeito B (usar seu banco já existente)
Se você já criou o Postgres no Render, então no Web Service vá em **Environment** e crie:
- `DATABASE_URL` = **Internal Database URL** do seu Postgres
- `ADMIN_PASSWORD` = `1243##`
- `SECRET_KEY` = uma chave grande aleatória
