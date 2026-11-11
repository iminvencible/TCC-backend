# Downloads portable official build tools into an ignored project-local directory.
$ErrorActionPreference = 'Stop'
$destination = Join-Path (Split-Path $PSScriptRoot -Parent) 'tmp-android-tools'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$jdk = (Invoke-RestMethod 'https://api.adoptium.net/v3/assets/latest/17/hotspot?architecture=x64&image_type=jdk&os=windows&vendor=eclipse')[0].binary.package
$jdkZip = Join-Path $destination 'jdk.zip'
Invoke-WebRequest $jdk.link -OutFile $jdkZip
if ((Get-FileHash $jdkZip -Algorithm SHA256).Hash -ne $jdk.checksum) { throw 'JDK checksum mismatch' }
Expand-Archive $jdkZip (Join-Path $destination 'jdk') -Force
[xml]$repository = (Invoke-WebRequest 'https://dl.google.com/android/repository/repository2-1.xml').Content
foreach ($target in @('build-tools;35.0.0', 'platforms;android-35')) {
    $package = @($repository.'sdk-repository'.remotePackage | Where-Object { $_.path -eq $target })[-1]
    $archive = @($package.archives.archive | Where-Object { $_.'host-os' -eq 'windows' -or -not $_.'host-os' })[0].complete
    $name = $target.Replace(';', '-')
    $zip = Join-Path $destination ($name + '.zip')
    Invoke-WebRequest ('https://dl.google.com/android/repository/' + $archive.url) -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA1).Hash -ne [string]$archive.checksum) { throw 'Android SDK checksum mismatch' }
    Expand-Archive $zip (Join-Path $destination $name) -Force
    Write-Host "$name ready"
}
Write-Host 'Portable build tools ready. No system PATH changes were made.'
