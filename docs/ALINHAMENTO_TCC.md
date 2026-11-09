# Correspondência com o documento do PrevClima

O projeto mantém as telas do capítulo 4.8, a navegação pública e a central
meteorológica. A implementação conserva FastAPI, HTML/JavaScript e Leaflet/OSM;
não usa Streamlit/Folium nem PostgreSQL, apesar das referências no texto acadêmico.
MySQL atende à persistência relacional; SQLite permanece para desenvolvimento/testes.
As previsões numéricas continuam vindo do Open-Meteo e os avisos oficiais do INMET.

| Documento | Comportamento implementado |
| --- | --- |
| RF01 / cadastro | Cadastro pendente; confirmação de e-mail com código de uso único, validade de 24h e reenvio. |
| RF02, RF03, RF05, RF06 | Meteorologistas gerenciam usuários e pares; administrador criado localmente herda capacidades e é protegido. Desativar preserva histórico. |
| RF04 | Redefinição por código de e-mail válido por 15 minutos; invalida sessões anteriores. |
| RNF01 | Mínimo de seis caracteres, uma letra maiúscula e um símbolo, sem exigir número ou minúscula. |
| RF07–RF11 / UC005–UC007 | Polígono desenhado/editado no mapa, descrição, nível, emissão e validade. Edição/exclusão somente antes de 30 minutos após publicação registrada pelo servidor. |
| UC008 | Novos alertas manuais são Tempestade Severa ou Tornado, com área e proteção predefinida. Conteúdo imutável; revisões auditadas de situação continuam separadas. |
| RF12 | Conteúdo educativo e ilustrações locais disponíveis também sem dados demonstrativos. |
| Manual 5.5 / 5.8 | Avisos dentro da aplicação visível, a cada 30s, conforme posição/cidade e preferências; som após interação com a página. |
| Manual 5.7 / 5.10 | Consultas INMET e importação de histórico existentes preservadas. |

As capturas de aplicação do capítulo 4.8 prevalecem sobre os wireframes móveis
anteriores quando diferem. As novas telas usam a mesma identidade visual. Não se
copiam dados pessoais ou números meteorológicos das capturas para a instalação.

## Contratos novos

- `POST /api/v1/auth/register`: retorna `201` com `status=pending_verification`,
  `email` e `message`; não fornece sessão. Falha de SMTP retorna `503` e mantém o
  cadastro pendente recuperável pelo reenvio.
- `POST /api/v1/auth/resend-verification` e `/forgot-password`: `{email}`.
- `POST /api/v1/auth/verify-email`: `{email, code}`.
- `POST /api/v1/auth/reset-password`: `{email, code, password}`.
- `GET/POST /api/v1/severe-forecasts`, `PATCH/DELETE /{id}`: entidade separada das
  previsões numéricas. Escrita exige perfil profissional. O PATCH recebe todos os
  campos editáveis; `published_at` e `editable_until` são controlados pelo servidor.
- `GET /api/v1/map-data`: campo adicional `severe_forecast_areas`.
- `GET /api/v1/notifications`: alertas ativos e não lidos da área do usuário,
  respeitando a preferência. Sem localização resolvida, retorna lista vazia.

Códigos são armazenados como HMAC SHA-256, nunca em texto. Cada código aceita no
máximo cinco tentativas incorretas. Pedidos de e-mail/código têm limite de dez por
hora por IP e identidade; login tem trinta. Os contadores persistem no banco.
Os clientes web e móvel usam o novo fluxo; integrações antigas precisam deixar de
esperar uma sessão na resposta de cadastro.

## Persistência e implantação

A migração `6da588e98c8b` adiciona `email_challenges`, `auth_rate_limits` e
`severe_forecasts`. Nenhuma tabela existente é removida. A implantação planejada é
nova, sem importar usuários antigos não verificados. Uma instalação existente
precisaria confirmar seus e-mails antes do login; não se marca automaticamente
como verificado um endereço cadastrado publicamente.

A expiração de previsão/alerta não equivale a ausência de risco. Dados indisponíveis
continuam identificados. Notificações sem o aplicativo aberto e uma garantia de
entrega de emergência estão fora deste comportamento.
