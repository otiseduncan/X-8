$ErrorActionPreference = "Stop"

$ComposeFiles = @("-f", "compose.yaml", "-f", "compose.sandbox.yaml", "-f", "compose.openwebui.yaml")

function Get-DotEnvValue {
  param([Parameter(Mandatory=$true)][string]$Name)
  $line = Get-Content .env -ErrorAction Stop | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
  if (-not $line) { return "" }
  return (($line -replace "^$([regex]::Escape($Name))=", "").Trim().Trim('"').Trim("'"))
}

function Get-Hash16 {
  param([Parameter(Mandatory=$true)][string]$Value)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))).Replace("-", "").Substring(0, 16).ToLowerInvariant()
}

$EnvKey = Get-DotEnvValue "OPENWEBUI_API_KEY"
$EnvHash = if ($EnvKey.Length -gt 0) { Get-Hash16 $EnvKey } else { "" }

Write-Host "== X8 OpenWebUI Auth Diagnostic =="
Write-Host "ENV key configured: " ($EnvKey.Length -gt 0)
Write-Host "ENV key length:     " $EnvKey.Length
Write-Host "ENV key jwt-like:   " (($EnvKey.ToCharArray() | Where-Object { $_ -eq '.' }).Count -eq 2)
Write-Host "ENV key hash16:     " $EnvHash

@'
import hashlib
import os

k = (os.getenv("X8_OPEN_WEBUI_API_KEY") or os.getenv("OPENWEBUI_API_KEY") or "").strip().strip('"').strip("'")
print("API container key configured:", bool(k))
print("API container key length:    ", len(k))
print("API container key jwt-like:  ", k.count(".") == 2)
print("API container key hash16:    ", hashlib.sha256(k.encode()).hexdigest()[:16] if k else "")
print("base:", os.getenv("X8_OPEN_WEBUI_BASE_URL") or os.getenv("OPENWEBUI_BASE_URL"))
print("model:", os.getenv("X8_OPEN_WEBUI_MODEL") or os.getenv("OPENWEBUI_MODEL"))
'@ | docker compose @ComposeFiles exec -T x8-api python -

@'
import base64
import hashlib
import json
import os
import time

token = os.environ.get("OW_TOKEN", "").strip().strip('"').strip("'")
print("token_present:", bool(token))
print("token_jwt_like:", token.count(".") == 2)

def decode_segment(segment):
    segment += "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment.encode()).decode()

payload = {}
if token.count(".") == 2:
    try:
        payload = json.loads(decode_segment(token.split(".")[1]))
        print("token_payload_readable:", True)
        print("token_user_id_present:", bool(payload.get("id")))
        print("token_jti_present:", bool(payload.get("jti")))
        print("token_exp_ok:", int(payload.get("exp", 0)) > int(time.time()))
    except Exception as exc:
        print("token_payload_readable:", False)
        print("token_payload_error:", type(exc).__name__, str(exc)[:200])

proc_env = {}
try:
    for raw in open("/proc/1/environ", "rb").read().split(b"\0"):
        if b"=" in raw:
            key, value = raw.split(b"=", 1)
            proc_env[key.decode(errors="replace")] = value
except Exception as exc:
    print("proc1_env_read_ok:", False)
    print("proc1_env_error:", type(exc).__name__, str(exc)[:200])

secret = proc_env.get("WEBUI_SECRET_KEY", b"") or proc_env.get("OPENWEBUI_SECRET_KEY", b"")
print("proc1_webui_secret_present:", bool(secret))
print("proc1_webui_secret_length:", len(secret))
print("proc1_webui_secret_hash16:", hashlib.sha256(secret).hexdigest()[:16] if secret else "")

if token.count(".") == 2 and secret:
    try:
        import jwt
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        print("token_signature_valid_for_proc1_openwebui:", True)
        print("decoded_user_id_matches_payload:", decoded.get("id") == payload.get("id"))
        print("decoded_jti_matches_payload:", decoded.get("jti") == payload.get("jti"))
    except Exception as exc:
        print("token_signature_valid_for_proc1_openwebui:", False)
        print("token_decode_error:", type(exc).__name__, str(exc)[:260])
elif not secret:
    print("token_signature_valid_for_proc1_openwebui:", False)
    print("token_decode_error: WEBUI_SECRET_KEY not visible in OpenWebUI process 1 environment")
'@ | docker exec -i -e "OW_TOKEN=$EnvKey" open-webui python -

Write-Host "== End OpenWebUI Auth Diagnostic =="
