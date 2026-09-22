# PrevClima

Aplicação web, PWA móvel para navegadores compatíveis e API FastAPI para a plataforma de
avisos meteorológicos do TCC. O projeto usa MySQL no Docker e SQLite como opção
leve de desenvolvimento.

## Recursos concluídos

- Site responsivo em português do Brasil, inspirado no protótipo do Figma.
- Cadastro público sempre com a função `USER`, definida pelo servidor.
- Entrada no site para usuário, meteorologista e administrador.
- Aplicativo móvel instalável em `/mobile/`, exclusivo para contas `USER`; a
  restrição também é validada pela API em `/api/v1/auth/login-mobile`.
- Sessão por cookie `HttpOnly`, proteção CSRF, senha Argon2 e revogação de sessão.
- Perfil, preferências, localização, previsão, avisos, mapa, conteúdo educativo e
  relatos conectados ao banco.
- Meteorologista: emissão direta de avisos, revisão de relatos, sincronização de
  avisos oficiais do INMET e marcação de aviso como alarme falso ou pendente de
  correção, com histórico de auditoria.
- Administrador: criação apenas de contas de meteorologista, alteração de função e
  desativação segura de contas. A desativação preserva o histórico e revoga as
  sessões existentes.
- Origem identificada em cada aviso: `DEMO`, `MANUAL` ou `INMET`.

## Iniciar no Windows 11 com Docker

Requisitos: Git e Docker Desktop em execução.

```powershell
git clone https://github.com/iminvencible/TCC-backend.git
cd TCC-backend
Copy-Item .env.example .env
powershell -ExecutionPolicy Bypass -File .\iniciar-prevclima.ps1
```

O inicializador procura uma porta livre entre `18080` e `18090`. Se todas estiverem
ocupadas, solicita ao Windows uma porta livre, inicia os contêineres, aguarda
`/api/health` e abre o navegador. A escolha não remove volumes nem dados.

Para iniciar manualmente:

```powershell
docker compose up --build
Start-Process "http://127.0.0.1:18080"
```

Altere `PREVCLIMA_PORT` no arquivo `.env` se quiser escolher outra porta. O MySQL
não publica porta no computador: ele usa apenas a rede interna do Docker, portanto
uma porta local `3306` ou `3006` ocupada não interfere no projeto.

Endereços com a porta escolhida:

- Site: `http://127.0.0.1:PORTA/`
- Aplicativo móvel: `http://127.0.0.1:PORTA/mobile/`
- Documentação da API: `http://127.0.0.1:PORTA/docs`
- Estado da aplicação: `http://127.0.0.1:PORTA/api/health`

## Contas locais de teste

As contas são inseridas somente quando `SEED_DEMO_DATA=true`. Elas também estão no
arquivo `CONTAS_DE_TESTE.txt`.

| Perfil | E-mail | Senha local | Onde entra |
| --- | --- | --- | --- |
| Administrador | `admin@exemplo.com` | `Admin123!` | Somente site |
| Meteorologista | `meteorologista@exemplo.com` | `Meteo123!` | Somente site |
| Usuário | `usuario@exemplo.com` | `Usuario123!` | Site e aplicativo móvel |

Troque as senhas e `JWT_SECRET` antes de qualquer uso fora da demonstração local.
O modo de produção recusa dados e credenciais de demonstração.

## Integração com o INMET

O projeto consulta sob demanda o RSS oficial de avisos:

`https://apiprevmet3.inmet.gov.br/avisos/rss`

A integração valida domínio e HTTPS, limita transferência e tempo de resposta, faz
importação idempotente e mantém disponíveis os avisos já armazenados quando o INMET
está indisponível. Avisos sem um polígono parseável e com coordenadas dentro dos
limites não recebem área inventada e são ignorados na importação espacial.

Não foi encontrada documentação formal ou contrato para uma API JSON de previsão
nas páginas oficiais do INMET consultadas. Por isso, a aplicação não depende de uma rota não documentada: previsões continuam
no banco local e dados de demonstração permanecem claramente identificados.

Variáveis disponíveis:

| Variável | Finalidade |
| --- | --- |
| `INMET_ENABLED` | Habilita a sincronização manual |
| `INMET_WARNING_RSS_URL` | Endereço oficial do RSS |
| `INMET_TIMEOUT_SECONDS` | Limite de espera da consulta |
| `INMET_MAX_RESPONSE_BYTES` | Tamanho máximo aceito |

Também é possível sincronizar pela linha de comando:

```bash
python -m app.sync_inmet
```

## Banco de dados

- `migrations/` é a fonte executável e versionada do esquema.
- A revisão `9d62a8f410be` migra `OWNER` para `ADMIN`, adiciona origem e situação dos
  avisos, histórico de revisão e eventos de auditoria.
- `banco tcc.sql` e `database/schema.mysql.sql` documentam a estrutura MySQL.
- `database/demo_seed.sql` contém dados meteorológicos demonstrativos sem senhas.
- `python -m app.seed` cria funções, contas locais com hash e dados de demonstração
  de forma repetível.

Para desenvolvimento sem Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

## Verificação

```bash
ruff format --check app migrations tests
ruff check app migrations tests
pytest -q
find public -name '*.js' -print0 | xargs -0 -n1 node --check
```

As migrações também são verificadas em um banco novo. O fluxo automatizado do
GitHub executa os testes gerais e uma migração real em MySQL.
