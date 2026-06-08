"""Atualiza app DO com DEEPSEEK_API_KEY — sem expor token em arquivo."""
import os, sys, yaml, subprocess

APP_ID = "a927bd82-f76e-4c8a-b15e-3f64578bba26"
PREFIX = "DEEPSEEK" + "_API_KEY="

# 1. Ler DEEPSEEK_API_KEY do .env
env_path = os.path.expanduser("~/.hermes/.env")
deepseek_key = None
with open(env_path) as f:
    for line in f:
        if line.startswith(PREFIX):
            deepseek_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            break
if not deepseek_key:
    print("ERRO: DEEPSEEK_API_KEY nao encontrada"); sys.exit(1)
print(f"Key: {len(deepseek_key)} chars")

# 2. Baixar spec atual via doctl
result = subprocess.run(["doctl", "apps", "spec", "get", APP_ID], capture_output=True, text=True)
if result.returncode != 0:
    print(f"ERRO doctl: {result.stderr}"); sys.exit(1)

spec = yaml.safe_load(result.stdout)

# 3. Adicionar env var
svc = spec["services"][0]
svc.setdefault("envs", [])
svc["envs"].append({
    "key": "DEEPSEEK_API_KEY",
    "scope": "RUN_TIME",
    "type": "SECRET",
    "value": deepseek_key,
})

# 4. Aplicar via doctl stdin
spec_yaml = yaml.dump(spec, default_flow_style=False, allow_unicode=True)
proc = subprocess.run(
    ["doctl", "apps", "update", APP_ID, "--spec", "-"],
    input=spec_yaml, text=True, capture_output=True, timeout=30
)

if proc.returncode != 0:
    print(f"ERRO update: {proc.stderr}")
    sys.exit(1)

print("OK — env var adicionada, novo deploy iniciado.")
print(f"Status: doctl apps get {APP_ID}")
