[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet('setup','start','stop','status','backup','verify-restore','restore','update','schedule','unschedule','admin')]
    [string]$Action = 'status',
    [string]$BackupFile,
    [switch]$ConfirmRestore
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectDirectory = $PSScriptRoot
$SettingsFile = Join-Path $ProjectDirectory '.env.production'
$BackupDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'PrevClima\backups'
$ComposeArgs = @('compose', '--env-file', $SettingsFile, '-f', (Join-Path $ProjectDirectory 'compose.production.yaml'))

# Support standard per-user Docker installs and freshly installed Tailscale even
# when the current Windows session has not refreshed PATH yet.
foreach ($tool in @(
    @{ Name = 'docker'; Paths = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin'),
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin')
    ) },
    @{ Name = 'tailscale'; Paths = @((Join-Path $env:ProgramFiles 'Tailscale')) }
)) {
    if (-not (Get-Command $tool.Name -ErrorAction SilentlyContinue)) {
        foreach ($directory in $tool.Paths) {
            if (Test-Path -LiteralPath (Join-Path $directory ($tool.Name + '.exe'))) {
                $env:PATH = $directory + ';' + $env:PATH
                break
            }
        }
    }
}

function Invoke-Compose {
    # Keep native flags such as -d away from PowerShell common-parameter binding.
    & docker @ComposeArgs @args
    if ($LASTEXITCODE -ne 0) { throw "Docker falhou ($LASTEXITCODE). Consulte: .\prevclima.ps1 status" }
}
function New-Secret {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
function Read-Settings {
    $settings = @{}
    foreach ($line in Get-Content -LiteralPath $SettingsFile) {
        if ($line -match '^([A-Z_]+)=(.*)$') { $settings[$Matches[1]] = $Matches[2].Trim().Trim('"').Trim("'") }
    }
    return $settings
}
function Assert-Tools {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Instale e abra o Docker Desktop.' }
    & docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Abra o Docker Desktop e aguarde o mecanismo iniciar.' }
}
function Wait-Ready {
    param([int]$Port)
    for ($attempt=0; $attempt -lt 90; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/ready" -TimeoutSec 3
            if ($health.status -eq 'pronto') { return }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw 'A API nao ficou pronta. Execute .\prevclima.ps1 status.'
}
function Backup-Database {
    New-Item -ItemType Directory -Force -Path $BackupDirectory | Out-Null
    $name = 'prevclima-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.sql'
    $target = Join-Path $BackupDirectory $name
    # Redirection happens inside Linux; PowerShell never re-encodes the SQL or sees passwords.
    Invoke-Compose exec -T db sh -c 'umask 077; MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --no-tablespaces --set-gtid-purged=OFF prevclima > /tmp/prevclima-backup.sql'
    Invoke-Compose cp db:/tmp/prevclima-backup.sql $target
    Invoke-Compose exec -T db rm /tmp/prevclima-backup.sql
    if ((Get-Item -LiteralPath $target).Length -eq 0) { throw 'Backup vazio; nao use este arquivo.' }
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    [IO.File]::WriteAllText("$target.sha256", $hash)
    Get-ChildItem -LiteralPath $BackupDirectory -Filter 'prevclima-*.sql' |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName; Remove-Item -LiteralPath ($_.FullName + '.sha256') -ErrorAction SilentlyContinue }
    Write-Host "Backup salvo: $target"
    return $target
}
function Copy-VerifiedBackup {
    param([string]$Path)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { throw 'Informe -BackupFile com um backup existente.' }
    $expected = (Get-Content -LiteralPath "$Path.sha256" -Raw).Trim()
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $expected) { throw 'Checksum do backup invalido.' }
    Invoke-Compose cp $Path db:/tmp/prevclima-restore.sql
}

Push-Location $ProjectDirectory
try {
    if ($Action -eq 'setup') {
        if (Test-Path -LiteralPath $SettingsFile) { throw '.env.production ja existe; edite-o sem substituir seus segredos.' }
        $template = Get-Content (Join-Path $ProjectDirectory '.env.production.example') -Raw
        foreach ($key in @('MYSQL_PASSWORD','MYSQL_ROOT_PASSWORD','JWT_SECRET')) {
            $template = $template.Replace("$key=GENERATED_BY_SETUP", "$key=$(New-Secret)")
        }
        [IO.File]::WriteAllText($SettingsFile, $template, (New-Object Text.UTF8Encoding($false)))
        if ($env:OS -eq 'Windows_NT') {
            $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
            & icacls $SettingsFile /inheritance:r /grant:r "${identity}:(F)" '*S-1-5-18:(F)' | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel restringir as permissoes do arquivo de segredos.' }
        }
        Write-Host 'Segredos criados. Configure PUBLIC_BASE_URL, CORS_ORIGINS e SMTP em .env.production antes de iniciar.'
        return
    }
    if (-not (Test-Path -LiteralPath $SettingsFile)) { throw 'Execute primeiro .\prevclima.ps1 setup.' }
    $settings = Read-Settings
    $port = [int]$settings.PREVCLIMA_PORT
    if ($port -lt 1024 -or $port -gt 65535) { throw 'PREVCLIMA_PORT deve estar entre 1024 e 65535.' }
    Assert-Tools
    switch ($Action) {
        'start' {
            if (-not (Get-Command tailscale -ErrorAction SilentlyContinue)) { throw 'Instale o Tailscale e entre na sua conta.' }
            $url = [Uri]$settings.PUBLIC_BASE_URL
            if ($url.Scheme -ne 'https' -or -not $url.Host.EndsWith('.ts.net') -or $url.AbsolutePath -ne '/' -or $url.Query -or $url.Fragment) { throw 'Defina PUBLIC_BASE_URL como a origem HTTPS ts.net do seu computador.' }
            if ($settings.CORS_ORIGINS.TrimEnd('/') -ne $settings.PUBLIC_BASE_URL.TrimEnd('/')) { throw 'CORS_ORIGINS deve corresponder a PUBLIC_BASE_URL.' }
            if ($settings.SMTP_PASSWORD -eq 'CONFIGURE_LOCALLY') { throw 'Configure o envio SMTP antes de iniciar.' }
            $tsRaw = & tailscale status --json
            if ($LASTEXITCODE -ne 0) { throw 'Entre no Tailscale e verifique sua conexao.' }
            $ts = $tsRaw | ConvertFrom-Json
            if ($ts.Self.DNSName.TrimEnd('.') -ne $url.Host) { throw 'PUBLIC_BASE_URL nao corresponde ao nome DNS deste dispositivo Tailscale.' }
            $running = @(& docker @ComposeArgs ps --status running -q api)
            if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel consultar os conteineres.' }
            if (-not $running.Count) {
                $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
                try { $listener.Start() } catch { throw "A porta $port esta ocupada. Libere-a ou altere PREVCLIMA_PORT; o tunel usa esta mesma porta." } finally { $listener.Stop() }
            }
            Invoke-Compose up -d --build
            Wait-Ready $port
            & tailscale set --unattended=true
            if ($LASTEXITCODE -ne 0) { throw 'Execute o comando de inicio em PowerShell como administrador para configurar o Tailscale.' }
            & tailscale funnel --bg "http://127.0.0.1:$port"
            if ($LASTEXITCODE -ne 0) { throw 'Autorize Funnel/HTTPS no Tailscale usando o link mostrado e tente novamente.' }
            Write-Host "PrevClima disponivel em $($settings.PUBLIC_BASE_URL)"
        }
        'stop' {
            & tailscale funnel --https=443 off
            if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel desligar o Funnel; confira tailscale funnel status.' }
            Invoke-Compose stop
        }
        'status' { Invoke-Compose ps; Invoke-Compose logs --tail 20 api inmet-worker station-worker; & tailscale funnel status }
        'admin' { Invoke-Compose exec api python -m app.create_admin }
        'backup' { $null = Backup-Database }
        'verify-restore' {
            if (-not $BackupFile) { $BackupFile = Backup-Database }
            Copy-VerifiedBackup $BackupFile
            $checkDatabase = 'prevclima_check_' + [Guid]::NewGuid().ToString('N')
            try {
                Invoke-Compose exec -T db sh -c "MYSQL_PWD=`"`$MYSQL_ROOT_PASSWORD`" mysql -uroot -e 'CREATE DATABASE $checkDatabase CHARACTER SET utf8mb4'"
                Invoke-Compose exec -T db sh -c "MYSQL_PWD=`"`$MYSQL_ROOT_PASSWORD`" mysql -uroot $checkDatabase < /tmp/prevclima-restore.sql"
                Invoke-Compose exec -T db sh -c "MYSQL_PWD=`"`$MYSQL_ROOT_PASSWORD`" mysql -uroot $checkDatabase -e 'SELECT version_num FROM alembic_version; SELECT COUNT(*) AS contas FROM users; CHECK TABLE users, weather_alerts, severe_forecasts, email_challenges;'"
                Write-Host 'Backup restaurado e consultado em banco separado.'
            } finally {
                Invoke-Compose exec -T db sh -c "MYSQL_PWD=`"`$MYSQL_ROOT_PASSWORD`" mysql -uroot -e 'DROP DATABASE IF EXISTS $checkDatabase'"
                Invoke-Compose exec -T db rm -f /tmp/prevclima-restore.sql
            }
        }
        'restore' {
            if (-not $ConfirmRestore) { throw 'Esta acao substitui dados. Revise o backup e use -ConfirmRestore para executar.' }
            Copy-VerifiedBackup $BackupFile
            Invoke-Compose stop api inmet-worker station-worker
            $null = Backup-Database
            try {
                Invoke-Compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot -e "DROP DATABASE prevclima; CREATE DATABASE prevclima CHARACTER SET utf8mb4;"'
                Invoke-Compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot prevclima < /tmp/prevclima-restore.sql'
                Invoke-Compose up -d
                Wait-Ready $port
            } finally { Invoke-Compose exec -T db rm -f /tmp/prevclima-restore.sql }
        }
        'update' {
            if (@(git status --porcelain).Count) { throw 'Ha alteracoes locais. Revise-as antes de atualizar.' }
            $null = Backup-Database
            & git pull --ff-only
            if ($LASTEXITCODE -ne 0) { throw 'Atualizacao Git interrompida; nenhum historico foi reescrito.' }
            Invoke-Compose up -d --build
            Wait-Ready $port
        }
        'schedule' {
            $scriptPath = Join-Path $ProjectDirectory 'prevclima.ps1'
            $taskAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" backup"
            $trigger = New-ScheduledTaskTrigger -Daily -At '20:00'
            $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
            Register-ScheduledTask -TaskName 'PrevClima Daily Backup' -Action $taskAction -Trigger $trigger -Settings $taskSettings -Description 'Backup diario do PrevClima (Docker Desktop deve estar em execucao)' -Force | Out-Null
            Write-Host 'Backup diario agendado para 20:00 na sessao deste usuario.'
        }
        'unschedule' { Unregister-ScheduledTask -TaskName 'PrevClima Daily Backup' -Confirm:$false }
    }
} finally { Pop-Location }
