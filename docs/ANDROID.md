# Aplicativo Android PrevClima

O APK é um cliente Android para as páginas móveis de usuário em
`https://home.tailf3e991.ts.net/mobile/`. A conta, os dados e as regras de acesso
continuam na API. Administradores e meteorologistas usam o site profissional.
O aplicativo requer internet e o servidor Windows em funcionamento. Não fornece
push em segundo plano; avisos são consultados enquanto a página está aberta.

## Instalar

Baixe `/downloads/prevclima.apk` pelo celular Android e abra o arquivo. O Android
pode pedir autorização para instalar aplicativos usando aquele navegador ou
gerenciador de arquivos; o usuário decide essa autorização. Requer Android 8.0
(API 26) ou mais recente. Este arquivo é uma distribuição direta assinada, não uma
publicação na Play Store. O hash SHA-256 fica em `/downloads/prevclima.apk.sha256`.

Identificação: `br.com.prevclima.app`, versão `1.0.0`, versionCode `1`, target API 35.
A localização é opcional e só é solicitada quando o usuário escolhe utilizar GPS.
Também é possível selecionar a cidade manualmente.

## Compilar no Windows

Não precisa instalar Android Studio nem Gradle. O projeto usa Java sem bibliotecas
nativas ou dependências externas. Os compiladores oficiais do Android e o JDK
Temurin ficam na pasta ignorada `tmp-android-tools`, sem alterar o PATH do sistema.
O SDK Android está sujeito à [licença do SDK](https://developer.android.com/studio/terms).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\android\setup-tools.ps1
# Somente na primeira compilação do responsável pela chave:
powershell -NoProfile -ExecutionPolicy Bypass -File .\android\build.ps1 -InitializeSigningKey
# Nas próximas compilações, reutilize a mesma chave:
powershell -NoProfile -ExecutionPolicy Bypass -File .\android\build.ps1
```

`setup-tools.ps1` baixa Temurin 17 da API oficial Adoptium e verifica SHA-256;
baixa build-tools 35.0.0 e plataforma Android 35 do repositório Google e verifica
os hashes fornecidos no catálogo oficial. Também pode passar `-JdkDirectory`,
`-BuildToolsDirectory` e `-AndroidJar` para usar uma instalação existente.

`build.ps1` compila recursos com aapt2, Java com javac, converte classes em DEX com
D8, alinha o APK com zipalign e assina com apksigner. Só copia o APK para
`public/downloads` depois de verificar sua assinatura e alinhamento. Artefatos
intermediários ficam em `android/build/<id>`. APKs e chaves não entram no Git.
O frontend e a API continuam sendo publicados pelo Compose; mudanças nas páginas
móveis aparecem no aplicativo após uma nova navegação/atualização. Uma mudança
de domínio, código nativo ou versão exige recompilar e distribuir um novo APK.

## Chave de atualização

A chave persistente fica em `%LOCALAPPDATA%\PrevClima\android-signing\prevclima-release.p12`.
A senha aleatória fica cifrada com Windows DPAPI em `password.dpapi`, acessível
somente ao mesmo usuário Windows. O diretório permite apenas esse usuário e SYSTEM.
A senha só é passada às ferramentas por variável de ambiente temporária e não é
impressa. Nunca publique os arquivos desse diretório.

Preserve a chave original: o Android só permite atualizar a instalação existente
com um APK assinado pela mesma chave. Faça uma cópia de segurança protegida da chave
e prepare sua recuperação com o responsável pelo Windows: copiar apenas o arquivo
DPAPI para outro computador/usuário não permite recuperar sua senha. Não gere uma
nova chave por cima da atual para resolver um problema de compilação.

## Limites e verificação

O WebView carrega apenas páginas HTTPS da origem configurada em `/mobile/`.
Links HTTPS externos abrem no navegador. Acesso a arquivos/content URIs, conteúdo
HTTP misto, cookies de terceiros e depuração WebView ficam desativados. Erros TLS
não são ignorados. Uma tela nativa de erro oferece nova tentativa quando não há
conexão. A API continua responsável por autenticação e autorização; o APK não
contém segredos de servidor ou credenciais de usuário.

O build valida assinatura APK v2/v3 e alinhamento. `aapt dump badging` valida pacote,
versão, Activity de entrada e permissões. A instalação, teclado, botão Voltar,
reconexão, GPS aceito/negado, cadastro/verificação e login devem ser conferidos em
um Android físico antes de declarar esses fluxos verificados em dispositivo.

Fontes das ferramentas: [Android SDK](https://developer.android.com/studio),
[apksigner](https://developer.android.com/tools/apksigner),
[Adoptium](https://adoptium.net/temurin/releases/).
