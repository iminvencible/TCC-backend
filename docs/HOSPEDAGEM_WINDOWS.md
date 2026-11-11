# Publicar o PrevClima no seu PC Windows

Este modo mantém site, API, MySQL e sincronizadores no seu PC e fornece um endereço
HTTPS público pelo Tailscale Funnel. Visitantes não precisam instalar Tailscale.
GitHub armazena o código; GitHub Pages não executa este backend Python.

## 1. Preparar o computador

Instale Git, Docker Desktop (contêineres Linux/WSL 2) e Tailscale pelos sites oficiais.
Abra o Docker Desktop e entre na sua conta Tailscale. O plano pessoal gratuito é
adequado ao projeto acadêmico, sujeito às condições do provedor. Funnel está em beta
e tem limites de banda: https://tailscale.com/kb/1223/funnel.

No PowerShell, dentro da pasta do repositório:

```powershell
powershell -ExecutionPolicy Bypass -File .\prevclima.ps1 setup
```

O comando cria `.env.production` com três segredos aleatórios diferentes e restringe
suas permissões no Windows. Não envie esse arquivo a ninguém nem o inclua no Git.
Se ele já existir, o comando para sem sobrescrever. A instalação pública usa um
volume novo (`prevclima-public_mysql_public_data`), separado da demonstração local.

## 2. Configurar endereço e e-mail

Descubra o endereço do dispositivo:

```powershell
(tailscale status --json | ConvertFrom-Json).Self.DNSName.TrimEnd('.')
notepad .env.production
```

Defina `PUBLIC_BASE_URL` e `CORS_ORIGINS` como `https://` seguido desse nome, sem
caminho ou barra final. Exemplo: `https://meu-pc.minha-rede.ts.net`.
Mantenha o nome do computador e da rede para preservar o endereço.

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`,
`SMTP_PASSWORD` e `SMTP_FROM` para uma caixa de e-mail real. Use `starttls` na porta
587 ou `ssl` na porta 465, conforme seu provedor. No Gmail com verificação em duas
etapas, use uma **senha de app**, se disponível para sua conta; a senha normal da
conta não é aceita por esse fluxo. Provedores que exigem exclusivamente OAuth
precisam de um relay SMTP compatível. A caixa e os limites de envio são seus.

Valores com `$` devem ficar entre aspas simples no `.env.production`, para evitar
interpolação pelo Compose. Exemplo: `SMTP_PASSWORD='valor-local'`. Não altere os
segredos de banco de uma instalação já inicializada: trocar apenas o arquivo não
altera a senha dentro do MySQL. `PREVCLIMA_PORT=18080` é a porta local fixa.

Se quiser medições automáticas, configure `INMET_STATION_CODES` com a lista JSON de
estações monitoradas, por exemplo `["A701"]`. Lista vazia mantém as consultas manuais
disponíveis, mas não consulta observações periodicamente. Os avisos INMET continuam
sendo sincronizados independentemente dessa lista.

## 3. Iniciar e criar o dono

Em PowerShell **como administrador**, na mesma pasta:

```powershell
powershell -ExecutionPolicy Bypass -File .\prevclima.ps1 start
powershell -ExecutionPolicy Bypass -File .\prevclima.ps1 admin
```

Na primeira execução, Tailscale pode mostrar um link para habilitar HTTPS/Funnel.
Abra-o, autorize e execute `start` novamente. O inicializador confirma que o nome
público corresponde ao dispositivo, espera `/api/ready`, ativa o modo unattended e
encaminha `tailscale funnel --bg http://127.0.0.1:18080`.

O comando `admin` pede nome, e-mail e senha no terminal. Entre pela aba
**Meteorologista** no endereço HTTPS. Não há senhas padrão ou dados fictícios na
instalação pública. A conta criada localmente é confiável e já está confirmada;
usuários do cadastro público precisam confirmar o e-mail.

Use o endereço **HTTPS**, inclusive no próprio PC: cookies de produção são seguros
e não funcionam para login pelo endereço HTTP local. Não exponha a porta MySQL e
não configure encaminhamento no roteador.

## 4. Operação diária

```powershell
.\prevclima.ps1 status
.\prevclima.ps1 backup
.\prevclima.ps1 verify-restore
.\prevclima.ps1 schedule
.\prevclima.ps1 update
.\prevclima.ps1 stop
```

- `status`: estado dos contêineres, últimas mensagens e configuração do Funnel.
- `backup`: dump consistente e SHA-256 em `%LOCALAPPDATA%\PrevClima\backups`.
  Mantém sete dias; o diretório está fora do Git. Os arquivos contêm dados pessoais:
  proteja seu perfil Windows e mantenha uma cópia em outro dispositivo.
- `verify-restore`: cria um backup, restaura em banco separado, consulta esquema e
  tabelas e remove apenas esse banco temporário. Também aceita `-BackupFile`.
- `schedule`: agenda backup diário às 20h na sessão Windows atual. Docker precisa
  estar em execução; uma execução perdida é tentada quando possível. Veja o
  resultado da tarefa “PrevClima Daily Backup” no Agendador do Windows.
- `unschedule`: remove essa tarefa de backup.
- `update`: exige Git limpo, faz backup, executa `git pull --ff-only`, reconstrói e
  espera a API. Não apaga volumes ou reescreve histórico.
- `stop`: desativa o Funnel e para os serviços, preservando os dados.

Ative “Start Docker Desktop when you sign in” nas configurações do Docker.
Tailscale retoma o Funnel em segundo plano após reiniciar, mas o site só estará
pronto quando Docker e os contêineres estiverem em execução. Faça login no Windows
após um reboot. Evite suspensão automática enquanto estiver hospedando. A expiração
da chave do dispositivo Tailscale também requer renovação; acompanhe-a no painel.

Para restaurar uma cópia escolhida, primeiro valide-a:

```powershell
.\prevclima.ps1 verify-restore -BackupFile 'C:\caminho\prevclima-DATA.sql'
.\prevclima.ps1 restore -BackupFile 'C:\caminho\prevclima-DATA.sql' -ConfirmRestore
```

`restore` substitui dados, para os serviços de aplicação e faz um backup antes.
Mantenha o arquivo `.sha256` junto ao `.sql`. Em caso de falha, preserve os arquivos,
consulte `status` e corrija antes de iniciar novamente. Migrações novas podem exigir
restaurar também a versão correspondente do código; não faça downgrade de esquema
com dados reais sem revisar a migração.

## 5. Conferência no seu PC

Abra o link em um celular **usando dados móveis**. Confirme:

1. Login profissional no site e cadastro de usuário em `/mobile/`; entrega real dos códigos por e-mail.
2. Verificação, redefinição de senha e entrada com a nova senha.
3. Publicação de previsão/alerta com polígono e exibição no mapa público.
4. Notificação dentro de uma página aberta para uma conta localizada na área.
5. Consulta INMET, persistência após reiniciar e restauração de backup.

O som depende de uma interação prévia com a página, conforme as regras do navegador.
As notificações são consultadas a cada 30 segundos com a página visível; não há
push quando o aplicativo está fechado. Alertas sem área conhecida permanecem na
lista pública, mas não geram uma notificação geográfica inventada.

Para problemas: porta ocupada exige liberar a porta ou alterar `PREVCLIMA_PORT` e
reiniciar; falha SMTP permite reenviar o código em `/conta.html#verify`; falta de
INMET preserva dados salvos ainda vigentes e mostra o estado da fonte. Confira o
spam e as cotas do e-mail. As tentativas de autenticação são limitadas no banco;
atrás do Funnel, parte do limite por IP pode ser compartilhada entre visitantes.

## Aplicativo Android e portal profissional

O portal `/` é exclusivo para administradores e meteorologistas. Usuários comuns
acessam `/mobile/` ou o APK em `/download.html`. As permissões são validadas pela
API e pelas rotas HTML. Sessões web antigas de usuários comuns exigem nova entrada
pelo aplicativo. A conta e os dados existentes são preservados.

Para gerar o APK assinado antes de reconstruir os contêineres, siga
[ANDROID.md](ANDROID.md). O arquivo `public/downloads/prevclima.apk` é um artefato
local ignorado pelo Git, mas incluído na imagem Docker para download. Uma nova
clonagem deve compilar o APK antes de disponibilizar o botão de download.
