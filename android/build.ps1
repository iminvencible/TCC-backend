[CmdletBinding()]
param(
    [string]$JdkDirectory,
    [string]$BuildToolsDirectory,
    [string]$AndroidJar,
    [switch]$InitializeSigningKey
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$project = Split-Path $PSScriptRoot -Parent
$toolRoot = Join-Path $project 'tmp-android-tools'
if (-not $JdkDirectory) { $JdkDirectory = (Get-ChildItem (Join-Path $toolRoot 'jdk') -Directory | Select-Object -First 1).FullName }
if (-not $BuildToolsDirectory) { $BuildToolsDirectory = Join-Path $toolRoot 'build-tools-35.0.0\android-15' }
if (-not $AndroidJar) { $AndroidJar = Join-Path $toolRoot 'platforms-android-35\android-35\android.jar' }
foreach ($required in @((Join-Path $JdkDirectory 'bin\javac.exe'), (Join-Path $BuildToolsDirectory 'aapt2.exe'), $AndroidJar)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing build tool: $required. See docs/ANDROID.md." }
}
function Invoke-Native {
    param([string]$Executable, [string[]]$NativeArgs)
    & $Executable @NativeArgs
    if ($LASTEXITCODE -ne 0) { throw "Build step failed: $Executable ($LASTEXITCODE)" }
}
$build = Join-Path $PSScriptRoot ('build\' + [Guid]::NewGuid().ToString('N'))
$classes = Join-Path $build 'classes'
$dex = Join-Path $build 'dex'
New-Item -ItemType Directory -Force -Path $build,$classes,$dex | Out-Null
$oldJavaHome = $env:JAVA_HOME
$oldPath = $env:PATH
$env:JAVA_HOME = $JdkDirectory
$env:PATH = (Join-Path $JdkDirectory 'bin') + ';' + $env:PATH
$signingDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'PrevClima\android-signing'
$keystore = Join-Path $signingDirectory 'prevclima-release.p12'
$protectedPassword = Join-Path $signingDirectory 'password.dpapi'
try {
    if (-not (Test-Path -LiteralPath $keystore)) {
        if (-not $InitializeSigningKey) { throw 'Signing key missing. Use -InitializeSigningKey once on the release owner PC.' }
        if (Test-Path -LiteralPath $protectedPassword) { throw 'Password exists without key. Recover the original signing key before continuing.' }
        New-Item -ItemType Directory -Force -Path $signingDirectory | Out-Null
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls $signingDirectory /inheritance:r /grant:r "${identity}:(OI)(CI)(F)" '*S-1-5-18:(OI)(CI)(F)' | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict signing directory permissions.' }
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        $env:PREVCLIMA_SIGN_PASSWORD = [Convert]::ToBase64String($bytes)
        $secure = ConvertTo-SecureString $env:PREVCLIMA_SIGN_PASSWORD -AsPlainText -Force
        $secure | ConvertFrom-SecureString | Set-Content -LiteralPath $protectedPassword -Encoding ASCII
        Invoke-Native (Join-Path $JdkDirectory 'bin\keytool.exe') @('-genkeypair','-keystore',$keystore,'-storetype','PKCS12','-storepass:env','PREVCLIMA_SIGN_PASSWORD','-keypass:env','PREVCLIMA_SIGN_PASSWORD','-alias','prevclima','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=PrevClima, OU=Mobile, O=PrevClima, C=BR')
    } else {
        if ($InitializeSigningKey) { Write-Host 'Existing signing key preserved.' }
        $secure = (Get-Content -LiteralPath $protectedPassword -Raw).Trim() | ConvertTo-SecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try { $env:PREVCLIMA_SIGN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
    $resources = Join-Path $build 'resources.zip'
    $unsigned = Join-Path $build 'unsigned.apk'
    $aligned = Join-Path $build 'aligned.apk'
    $signed = Join-Path $build 'prevclima.apk'
    Invoke-Native (Join-Path $BuildToolsDirectory 'aapt2.exe') @('compile','--dir',(Join-Path $PSScriptRoot 'res'),'-o',$resources)
    Invoke-Native (Join-Path $BuildToolsDirectory 'aapt2.exe') @('link','-o',$unsigned,'--manifest',(Join-Path $PSScriptRoot 'AndroidManifest.xml'),'-I',$AndroidJar,'--min-sdk-version','26','--target-sdk-version','35',$resources)
    $sources = @(Get-ChildItem (Join-Path $PSScriptRoot 'src') -Recurse -Filter '*.java' | ForEach-Object { $_.FullName })
    Invoke-Native (Join-Path $JdkDirectory 'bin\javac.exe') (@('-encoding','UTF-8','-source','8','-target','8','-bootclasspath',$AndroidJar,'-d',$classes) + $sources)
    $jar = Join-Path $build 'classes.jar'
    Invoke-Native (Join-Path $JdkDirectory 'bin\jar.exe') @('cf',$jar,'-C',$classes,'.')
    Invoke-Native (Join-Path $JdkDirectory 'bin\java.exe') @('-cp',(Join-Path $BuildToolsDirectory 'lib\d8.jar'),'com.android.tools.r8.D8','--release','--min-api','26','--lib',$AndroidJar,'--output',$dex,$jar)
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::Open($unsigned,[IO.Compression.ZipArchiveMode]::Update)
    try {
        foreach ($file in Get-ChildItem -LiteralPath $dex -Filter '*.dex') {
            $null = [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive,$file.FullName,$file.Name,[IO.Compression.CompressionLevel]::Optimal)
        }
    } finally { $archive.Dispose() }
    Invoke-Native (Join-Path $BuildToolsDirectory 'zipalign.exe') @('-f','-P','16','4',$unsigned,$aligned)
    $signer = Join-Path $BuildToolsDirectory 'lib\apksigner.jar'
    Invoke-Native (Join-Path $JdkDirectory 'bin\java.exe') @('-jar',$signer,'sign','--ks',$keystore,'--ks-key-alias','prevclima','--ks-pass','env:PREVCLIMA_SIGN_PASSWORD','--key-pass','env:PREVCLIMA_SIGN_PASSWORD','--out',$signed,$aligned)
    Invoke-Native (Join-Path $JdkDirectory 'bin\java.exe') @('-jar',$signer,'verify','--verbose','--print-certs',$signed)
    Invoke-Native (Join-Path $BuildToolsDirectory 'zipalign.exe') @('-c','-P','16','4',$signed)
    $downloads = Join-Path $project 'public\downloads'
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
    Copy-Item -LiteralPath $signed -Destination (Join-Path $downloads 'prevclima.apk') -Force
    $hash = (Get-FileHash -LiteralPath $signed -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText((Join-Path $downloads 'prevclima.apk.sha256'), "$hash  prevclima.apk`n")
    Write-Host "APK built: $downloads\prevclima.apk"
    Write-Host "SHA256: $hash"
} finally {
    Remove-Item Env:\PREVCLIMA_SIGN_PASSWORD -ErrorAction SilentlyContinue
    $env:JAVA_HOME = $oldJavaHome
    $env:PATH = $oldPath
}
