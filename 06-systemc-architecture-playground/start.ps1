$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop with Linux containers and start it first.' }
docker info --format '{{.OSType}}'
if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop is not running.' }
if ((docker info --format '{{.OSType}}') -ne 'linux') { throw 'Switch Docker Desktop to Linux containers.' }
docker build -t from-lab-to-code-systemc:local .
if ($LASTEXITCODE -ne 0) { throw 'Docker image build failed.' }
Write-Host 'Open http://127.0.0.1:5058 in your browser.'
if (Get-Command py -ErrorAction SilentlyContinue) { py -3 app.py } else { python app.py }
