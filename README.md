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
- Previsão atual e diária obtida do Open-Meteo, com geocodificação de cidades,
  cache de 15 minutos e fallback para o último dado salvo.
- Mapa com previsões pontuais do Open-Meteo separadas dos polígonos de avisos;
  busca por cidade pública e GPS apenas para contas autenticadas. Se a biblioteca
  do mapa ou os mosaicos não carregarem, os dados disponíveis aparecem em texto.
- Meteorologista: emissão direta de avisos, revisão de relatos, sincronização manual de
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

## Open-Meteo e INMET

O Open-Meteo fornece as condições atuais, temperaturas mínima e máxima, umidade,
vento e chance de chuva. A consulta é feita automaticamente quando a tela inicial
ou `/api/v1/forecasts/current` solicita uma localidade sem cache recente. Não é
necessária chave de API.

O resultado é armazenado no banco por 15 minutos. Se o serviço ficar temporariamente
indisponível, o PrevClima pode exibir por até 24 horas o último resultado salvo,
identificado na interface como tal. A fonte e o link de atribuição permanecem
visíveis no site e no aplicativo móvel.

Variáveis do Open-Meteo:

| Variável | Finalidade |
| --- | --- |
| `OPEN_METEO_ENABLED` | Habilita a previsão automática |
| `OPEN_METEO_API_URL` | Endpoint de previsão |
| `OPEN_METEO_GEOCODING_URL` | Conversão de cidade/UF em coordenadas |
| `OPEN_METEO_TIMEOUT_SECONDS` | Limite de espera |
| `OPEN_METEO_MAX_RESPONSE_BYTES` | Tamanho máximo aceito |
| `OPEN_METEO_CACHE_MINUTES` | Validade do cache recente |
| `OPEN_METEO_STALE_HOURS` | Janela máxima do fallback salvo |

O INMET continua sendo a fonte oficial dos avisos meteorológicos brasileiros. Um
processo separado (`inmet-worker`) consulta o RSS oficial assim que a API estiver
pronta e repete a consulta a cada 60 minutos, por padrão:

`https://apiprevmet3.inmet.gov.br/avisos/rss`

A integração valida domínio e HTTPS, limita transferência e tempo de resposta, faz
importação idempotente e mantém disponíveis os avisos já armazenados quando o INMET
está indisponível. Os avisos expiram pelo prazo indicado pela fonte; dados salvos não
significam que um aviso expirado seja exibido como ativo. Avisos sem polígono
parseável são preservados como informação textual e não recebem área inventada.

Não foi encontrada documentação formal ou contrato para uma API JSON de previsão
nas páginas oficiais do INMET consultadas. Por isso, o projeto usa apenas o feed
oficial de avisos do INMET e obtém a previsão pelo Open-Meteo, sem depender de uma
rota não documentada.

Variáveis disponíveis:

| Variável | Finalidade |
| --- | --- |
| `INMET_ENABLED` | Habilita sincronização automática e manual (`true` por padrão no Compose) |
| `INMET_WARNING_RSS_URL` | Endereço oficial do RSS |
| `INMET_TIMEOUT_SECONDS` | Limite de espera da consulta |
| `INMET_MAX_RESPONSE_BYTES` | Tamanho máximo aceito |
| `INMET_SYNC_INTERVAL_MINUTES` | Intervalo em minutos entre tentativas (10–1440; padrão 60) |

O painel do meteorologista continua oferecendo sincronização sob demanda. A linha de
comando também executa uma única tentativa:

```bash
python -m app.sync_inmet
```

Para verificar o processo automático no Docker: `docker compose logs -f inmet-worker`.
O RSS pode conter avisos sem polígono CAP. Nesses casos, a página do mapa mostra
o aviso em texto, sem gerar uma área fictícia. Se não houver áreas compatíveis e
vigentes, o mapa não terá polígonos do INMET para mostrar.
O endereço do RSS consta no portal do INMET, mas a compatibilidade com o formato
atual dos itens e a presença de polígonos não foram verificadas em uma consulta
real neste ambiente. Antes de uma apresentação com dados ao vivo, acompanhe
`docker compose logs inmet-worker` e compare os avisos importados com o portal
oficial. Não trate ausência de avisos no mapa como ausência de risco.

## Banco de dados

- `migrations/` é a fonte executável e versionada do esquema.
- A revisão `9d62a8f410be` migra `OWNER` para `ADMIN`, adiciona origem e situação dos
  avisos, histórico de revisão e eventos de auditoria.
- A revisão `4a8c1e7d2b90` adiciona o link de atribuição da fonte às previsões.
- A revisão `5f0e7c29b4a1` guarda coordenadas das previsões e permite avisos
  oficiais do INMET sem geometria, preservando-os como informação textual.
- `banco tcc.sql` e `database/schema.mysql.sql` documentam a estrutura MySQL.
- `database/demo_seed.sql` contém dados meteorológicos demonstrativos sem senhas.
- `python -m app.seed` cria funções, contas locais com hash e dados de demonstração
  de forma repetível.

Para desenvolvimento sem Docker:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export OPEN_METEO_ENABLED=true INMET_ENABLED=true
alembic upgrade head
uvicorn app.main:app --reload
```

Em outro terminal, no mesmo diretório e com o ambiente ativado, execute
`python -m app.sync_inmet --loop` para sincronizar o INMET também na instalação
sem Docker. No PowerShell, use `py -m venv .venv` e
`.\.venv\Scripts\Activate.ps1` no lugar das duas primeiras linhas; instale as
dependências e defina `$env:OPEN_METEO_ENABLED = "true"` e
`$env:INMET_ENABLED = "true"` antes de iniciar os processos.

## Verificação

```bash
ruff format --check app migrations tests
ruff check app migrations tests
pytest -q
find public -name '*.js' -print0 | xargs -0 -n1 node --check
```

As migrações também são verificadas em um banco novo. O fluxo automatizado do
GitHub executa os testes gerais e uma migração real em MySQL.
