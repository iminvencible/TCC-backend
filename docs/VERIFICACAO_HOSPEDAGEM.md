# Verificação da implantação e alinhamento com o TCC

Verificação realizada em 9 de novembro de 2026 no ambiente de desenvolvimento.

- Suíte Python: autenticação, permissão, importadores existentes e novos fluxos de
  e-mail, senha, limites, notificações geográficas e janela de edição de previsões.
- Suíte JavaScript: mapa com falhas de rede, concorrência de consultas, GPS,
  deduplicação de avisos, preferências de som e suspensão de consultas em abas ocultas.
- Ruff, sintaxe JavaScript e `git diff --check`.
- Migração de banco MySQL 8.4 vazio e `alembic check`, sem divergência de esquema.
- Fluxo real contra MySQL: cadastro, código, login, reset, revogação de sessão,
  administrador, publicação e edição de previsão.
- Backup via `mysqldump`, restauração em outro banco e `CHECK TABLE` com resultado OK.
- Chromium/Playwright: publicar/editar previsão, publicar alerta, mapa público,
  cadastro/confirmação, reset de senha e login móvel; sem erros JavaScript.
  Capturas em larguras de 1440px e 390px e conferência de overflow móvel.
- PowerShell 7: análise de sintaxe e execução do setup, geração de segredos distintos
  e recusa de sobrescrita do arquivo existente. Compose de produção validado.
- Imagem Docker construída e execução de produção com MySQL e usuário sem privilégios.

O transporte SMTP foi testado com substitutos locais, verificando TLS e conteúdo
sem enviar mensagens externas. Ainda dependem do computador de implantação:
login e autorização do Tailscale, entrega real pelo SMTP escolhido, Agendador de
Tarefas/ACL do Windows, reinício do Docker Desktop e acesso pelo celular em dados
móveis. Esses passos estão no [guia Windows](HOSPEDAGEM_WINDOWS.md).

Para repetir as verificações automáticas:

```sh
ruff format --check app migrations tests
ruff check app migrations tests
pytest -q
node --test tests/*.test.cjs
find public -name '*.js' -print0 | xargs -0 -n1 node --check
alembic upgrade head
alembic check
```

Os testes usam um capturador de mensagens e não devem enviar e-mails reais.
