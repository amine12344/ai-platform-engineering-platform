#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$HostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$Hostnames = @(
    "platform.supportops.local",
    "s3.supportops.local",
    "mlflow.supportops.local"
)

$Lines = @(Get-Content -LiteralPath $HostsPath)

foreach ($Hostname in $Hostnames) {
    $EscapedHostname = [Regex]::Escape($Hostname)
    $Lines = @(
        $Lines | Where-Object {
            $_ -notmatch "^\s*\S+\s+.*\b$EscapedHostname\b"
        }
    )
}

$Lines += ""
$Lines += "# SupportOps local ingress"

foreach ($Hostname in $Hostnames) {
    $Lines += "127.0.0.1 $Hostname"
}

Set-Content -LiteralPath $HostsPath -Value $Lines -Encoding ascii
Clear-DnsClientCache

Write-Host "Configured SupportOps hostnames in $HostsPath"
