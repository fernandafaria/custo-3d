"""Cria app custo-3d no DO App Platform com a DEEPSEEK_API_KEY."""
import os, yaml, json, urllib.request, urllib.error, subprocess, sys

# 1. Ler a API key do .env do Hermes
env_path = os.path.expanduser("~/.hermes/.env")
deepseek_key = None
with open(env_path) as f:
    for line in f:
        if line.startswith("DEEPSEEK_API_KEY="):
            deepseek_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break

if not deepseek_key:
    print("ERRO: DEEPSEEK_API_KEY não encontrada")
    sys.exit(1)

print(f"Key encontrada, tamanho: {len(deepseek_key)} chars")

# 2. Ler spec YAML e injetar key
spec_path = os.path.expanduser("~/custo-3d/app.yaml")
with open(spec_path) as f:
    spec = yaml.safe_load(f)

# Substituir placeholder
for env_var in spec["services"][0].get("envs", []):
    if env_var["key"] == "DEEPSEEK_API_KEY":
        env_var["value"] = deepseek_key
        break

# 3. DO token
do_token = None
with open(env_path) as f:
    for line in f:
        if line.startswith("DO_TOKEN="):
            do_token = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break

if not do_token:
    print("ERRO: DO_TOKEN não encontrado")
    sys.exit(1)

# 4. Criar app via API
payload = json.dumps({"spec": spec}).encode()
req = urllib.request.Request(
    "https://api.digitalocean.com/v2/apps",
    data=payload,
    headers={
        "Authorization": "Bearer " + do_token,
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        app_id = result["app"]["id"]
        ingress = result["app"].get("default_ingress", "pendente")
        print(f"APP CRIADO: {app_id}")
        print(f"Ingress: {ingress}")
        print(f"URL: https://{ingress}")
        print(f"\nDeploy iniciado. Monitore com:")
        print(f"  doctl apps list")
        print(f"  doctl apps get {app_id}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"ERRO HTTP {e.code}: {body}")
    sys.exit(1)
