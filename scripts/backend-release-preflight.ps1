param(
    [string] $RemoteHost = "",
    [string] $RemoteUser = "ubuntu",
    [string] $KeyPath = "",
    [string] $RemoteRepo = "/home/ubuntu/BACK-END"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string] $Message)
    Write-Output ""
    Write-Output ("== " + $Message)
}

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Step "Git working tree"
git -c safe.directory=$repoRoot -C $repoRoot status --short

Write-Step "Python syntax check"
$pythonCheck = @"
import ast
import pathlib
import sys

root = pathlib.Path(r'''$repoRoot''') / "app"
bad = []
for path in root.rglob("*.py"):
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except Exception as exc:
        bad.append((str(path), str(exc)))

if bad:
    for path, error in bad:
        print(f"SYNTAX_ERROR {path}: {error}")
    sys.exit(1)

print("python_ast_ok")
"@
$encodedPythonCheck = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonCheck))
python -c "import base64; exec(base64.b64decode('$encodedPythonCheck').decode('utf-8'))"
if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed."
}

Write-Step "Secret handling checks"
$dockerfile = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "Dockerfile")
if ($dockerfile -match "COPY\s+\.env" -or $dockerfile -match "COPY\s+firebase-admin-key\.json") {
    throw "Dockerfile still copies secret files into the image."
}
Write-Output "dockerfile_secret_copy_ok"

$compose = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "docker-compose.yml")
if ($compose -notmatch "firebase-admin-key\.json:/app/firebase-admin-key\.json:ro") {
    throw "docker-compose.yml does not mount firebase-admin-key.json read-only."
}
Write-Output "compose_firebase_mount_ok"

Write-Step "Compatibility flag defaults"
$config = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "app/core/config.py")
$requiredConfig = @(
    "ALLOW_DEV_LOGIN: bool = False",
    "ENABLE_STRICT_RAG: bool = False",
    "ENABLE_SCHEDULER: bool = True",
    "FETCH_WEATHER_ON_STARTUP: bool = True"
)
foreach ($item in $requiredConfig) {
    if ($config -notlike ("*" + $item + "*")) {
        throw "Missing expected config default: $item"
    }
    Write-Output ("ok " + $item)
}

if ($RemoteHost -and $KeyPath) {
    Write-Step "Remote production shape"
    $sshTarget = "$RemoteUser@$RemoteHost"
    $knownHostsPath = Join-Path (Split-Path -Parent $KeyPath) "known_hosts"
    ssh -i $KeyPath -o "UserKnownHostsFile=$knownHostsPath" $sshTarget "cd $RemoteRepo && echo REMOTE_HEAD && git rev-parse --short HEAD && echo REMOTE_STATUS && git status --short && echo ENV_KEYS && cut -d= -f1 .env.compose .env 2>/dev/null | sed '/^$/d' | sort -u && echo DOCKER && sudo -n docker ps --format '{{.Names}} {{.Status}}'"
    if ($LASTEXITCODE -ne 0) {
        throw "Remote production shape check failed."
    }
}

Write-Step "Preflight complete"
Write-Output "backend_release_preflight_ok"
