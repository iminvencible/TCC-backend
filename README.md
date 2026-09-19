# PrevClima

Backend FastAPI, banco MySQL e prototipo conectado para a plataforma de alertas
meteorologicos do TCC.

## O que esta conectado

- Cadastro de usuario com senha Argon2 e funcao `USER` definida pelo servidor.
- Login/logout por cookie `HttpOnly`, protecao CSRF e controle de sessao.
- Perfil, cidade/UF e preferencias persistidos no banco.
- Consentimento de geolocalizacao com gravacao das coordenadas no perfil.
- Tela inicial alimentada por previsao e contagem de alertas do banco.
- Lista de alertas ativos e marcacao de leitura por usuario.
- Mapa interativo com camadas independentes de previsao e alertas georreferenciados.
- Conteudo educativo publicado no banco, com links para fontes oficiais.
- Envio, historico e revisao profissional de relatos meteorologicos.
- Acesso profissional sem cadastro publico de administrador.
- Criacao e promocao de contas profissionais por endpoints exclusivos do proprietario.

As paginas conectadas sao inicio, alertas, mapa, perfil, permissao de localizacao,
informacoes educativas e envio de relatos. A API interativa fica em
`http://localhost:8000/docs`.

## Executar com Docker

Requer Docker com Compose:

```bash
cp .env.example .env
docker compose up --build
```

Abra `http://localhost:8000`. O Compose aguarda o MySQL, executa a migracao e insere
os dados de demonstracao. Troque todas as senhas e o `JWT_SECRET` do `.env` antes de
usar fora do ambiente local.

Contas de desenvolvimento definidas em `.env.example`:

| Perfil | E-mail | Senha local |
| --- | --- | --- |
| Proprietario | `owner@example.com` | `Owner123!` |
| Meteorologista | `meteorologista@example.com` | `Meteo123!` |
| Usuario | `usuario@example.com` | `Usuario123!` |

Essas contas so sao inseridas quando `SEED_DEMO_DATA=true`; a aplicacao recusa esse
modo quando `APP_ENV=production`.

## Executar sem Docker

O modo local usa SQLite por padrao para desenvolvimento rapido:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
SEED_DEMO_DATA=true \
SEED_USER_EMAIL=usuario@example.com \
SEED_USER_PASSWORD='Usuario123!' \
python -m app.seed
uvicorn app.main:app --reload
```

Para MySQL, configure `DATABASE_URL` no formato
`mysql+pymysql://usuario:senha@host:3306/prevclima?charset=utf8mb4`.
Caracteres reservados na senha precisam estar codificados para URL.

## Banco de dados

- `migrations/` e a fonte executavel e versionada do schema.
- `banco tcc.sql` e uma exportacao MySQL legivel da migracao inicial.
- `database/demo_seed.sql` contem inserts demonstrativos opcionais, sem usuarios ou
  senhas.
- `python -m app.seed` cria funcoes, contas locais com hash e dados de clima de forma
  repetivel.

Os dados meteorologicos incluidos sao claramente marcados como demonstracao. Ainda
nao existe integracao em tempo real com radar, CEMADEN ou outro provedor oficial.
O mapa usa Leaflet pelo CDN oficial unpkg e blocos cartograficos do OpenStreetMap; por isso,
o mapa-base precisa de acesso a internet no navegador. Os alertas e as geometrias
continuam vindo da API local.

Alertas emitidos nao possuem rotas de alteracao ou exclusao. Essa imutabilidade fica na
camada da aplicacao para que as migracoes funcionem com usuarios MySQL de privilegios
minimos, sem exigir permissao administrativa para criar triggers.

## Verificacao

```bash
ruff format --check app migrations tests
ruff check app migrations tests
pytest -q
find public/assets/js -name '*.js' -print0 | xargs -0 -n1 node --check
```

Os testes cobrem cadastro/login, normalizacao de e-mail, hash de senha, protecao
contra elevacao de funcao, CSRF, perfil, previsao, alertas, geometrias do mapa,
conteudo educativo, relatos, paginas publicas e leitura idempotente.
