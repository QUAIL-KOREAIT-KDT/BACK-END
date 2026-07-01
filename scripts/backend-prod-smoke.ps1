param(
    [string] $BaseUrl = "https://pangpangpangs.com/api",
    [string] $AuthFile = "",
    [switch] $UseDevLogin
)

$ErrorActionPreference = "Stop"

function Invoke-Curl {
    param([string[]] $Arguments)

    $output = & curl.exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "curl failed: $($Arguments -join ' ')"
    }
    return ($output -join "`n")
}

function Assert-Json {
    param([string] $Raw, [string] $Name)

    if (-not $Raw) {
        throw "$Name returned empty response"
    }
    return ($Raw | ConvertFrom-Json)
}

Write-Output ("base_url={0}" -f $BaseUrl)

$rootUrl = $BaseUrl -replace "/api$", ""
$root = Invoke-Curl -Arguments @("-sS", "--connect-timeout", "15", $rootUrl)
$rootJson = Assert-Json -Raw $root -Name "root"
Write-Output ("root ok status={0}" -f $rootJson.status)

$compat = Invoke-Curl -Arguments @("-sS", "--connect-timeout", "15", ($BaseUrl + "/meta/compat"))
$compatJson = Assert-Json -Raw $compat -Name "compat"
Write-Output ("compat ok contract={0}" -f $compatJson.compat_contract)

$token = ""
if ($AuthFile) {
    $auth = Get-Content -Raw -LiteralPath $AuthFile | ConvertFrom-Json
    $token = $auth.access_token
    if (-not $token) {
        throw "AuthFile does not include access_token"
    }
    Write-Output ("auth_file ok token_len={0}" -f $token.Length)
} elseif ($UseDevLogin) {
    $authRaw = Invoke-Curl -Arguments @("-sS", "--connect-timeout", "15", "-X", "POST", ($BaseUrl + "/auth/dev-login"))
    $auth = Assert-Json -Raw $authRaw -Name "dev-login"
    $token = $auth.access_token
    if (-not $token) {
        throw "dev-login did not return access_token"
    }
    Write-Output ("dev_login ok user_id={0} token_len={1}" -f $auth.user_id, $token.Length)
} else {
    Write-Output "auth skipped. pass -AuthFile or -UseDevLogin to check protected endpoints."
    exit 0
}

$checks = @(
    @{ Path = "/users/me"; Name = "users_me" },
    @{ Path = "/users/me-safe"; Name = "users_me_safe" },
    @{ Path = "/home/info"; Name = "home_info" },
    @{ Path = "/dictionary/list"; Name = "dictionary_list" },
    @{ Path = "/search/query?q=G4"; Name = "search_query" },
    @{ Path = "/search/query-safe?q=G4"; Name = "search_query_safe" },
    @{ Path = "/game/ranking"; Name = "game_ranking" },
    @{ Path = "/my_page/diagnosis-history"; Name = "diagnosis_history" }
)

foreach ($check in $checks) {
    $raw = Invoke-Curl -Arguments @(
        "-sS",
        "--connect-timeout",
        "20",
        "-H",
        ("Authorization: Bearer " + $token),
        ($BaseUrl + $check.Path)
    )
    $json = Assert-Json -Raw $raw -Name $check.Name
    if ($json -is [array]) {
        Write-Output ("{0} ok array_count={1}" -f $check.Name, $json.Count)
    } else {
        $keys = ($json.PSObject.Properties.Name -join ",")
        Write-Output ("{0} ok keys={1}" -f $check.Name, $keys)
    }
}

Write-Output "backend_prod_smoke_ok"
