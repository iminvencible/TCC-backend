[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectDirectory = $PSScriptRoot
$PreferredPorts = 18080..18090

function Test-PortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Loopback,
            $Port
        )
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

function Get-FreeEphemeralPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    try {
        $listener.Start()
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker nao foi encontrado. Instale e inicie o Docker Desktop antes de continuar."
}

& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "O comando 'docker compose' nao esta disponivel."
}

$SelectedPort = $PreferredPorts | Where-Object { Test-PortAvailable -Port $_ } | Select-Object -First 1
if ($null -eq $SelectedPort) {
    $SelectedPort = Get-FreeEphemeralPort
}

$env:PREVCLIMA_PORT = [string]$SelectedPort
$BaseUrl = "http://127.0.0.1:$SelectedPort"
$HealthUrl = "$BaseUrl/api/health"

Push-Location $ProjectDirectory
try {
    Write-Host "Iniciando o PrevClima na porta $SelectedPort..."
    & docker compose up --build --detach
    if ($LASTEXITCODE -ne 0) {
        throw "O Docker Compose nao conseguiu iniciar o PrevClima."
    }

    $Healthy = $false
    for ($Attempt = 1; $Attempt -le 60; $Attempt++) {
        try {
            $Response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 3
            if ($Response.status -eq "ok") {
                $Healthy = $true
                break
            }
        }
        catch {
            # A API pode ainda estar executando as migracoes e aguardando o MySQL.
        }
        Start-Sleep -Seconds 2
    }

    if (-not $Healthy) {
        & docker compose ps
        throw "A API nao ficou pronta em 120 segundos. Consulte: docker compose logs api"
    }

    Write-Host "PrevClima pronto em $BaseUrl" -ForegroundColor Green
    Write-Host "Documentacao da API: $BaseUrl/docs"
    Start-Process $BaseUrl
}
finally {
    Pop-Location
}
