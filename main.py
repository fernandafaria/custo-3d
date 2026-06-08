"""
main.py — API de Precificação 3D (FastAPI)
Endpoints: calculadora REST + agente com DeepSeek
"""
import os
import json
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from calculator import calcular, FILAMENTOS, CONFIG_PADRAO

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
PORT = int(os.getenv("PORT", "8080"))

STATIC_DIR = Path(__file__).parent / "static"

# ── Models ──────────────────────────────────────────────

class CalculateRequest(BaseModel):
    peso_gramas: float
    horas_impressao: float
    preco_filamento_kg: float = 70
    horas_humanas: float = 0.5
    custo_acabamento: float = 0
    qtd: int = 1
    margem_pct: int | None = None
    tarifa_kwh: float | None = None
    potencia_watts: float | None = None

class ChatRequest(BaseModel):
    mensagem: str

# ── Healthcheck-first ──────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — nada pesado, healthcheck já responde
    yield
    # Shutdown
    pass

app = FastAPI(title="Custo 3D", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── API Routes ──────────────────────────────────────────

@app.post("/api/calculate")
async def api_calculate(req: CalculateRequest):
    """Calcula custo e preço de venda."""
    config = {}
    if req.margem_pct is not None:
        config["margem_pct"] = req.margem_pct
    if req.tarifa_kwh is not None:
        config["tarifa_kwh"] = req.tarifa_kwh
    if req.potencia_watts is not None:
        config["potencia_watts"] = req.potencia_watts

    result = calcular(
        peso_gramas=req.peso_gramas,
        horas_impressao=req.horas_impressao,
        preco_filamento_kg=req.preco_filamento_kg,
        horas_humanas=req.horas_humanas,
        custo_acabamento=req.custo_acabamento,
        qtd=req.qtd,
        config=config if config else None,
    )
    return result


@app.get("/api/filamentos")
async def api_filamentos():
    """Lista filamentos disponíveis com preços padrão."""
    return FILAMENTOS


@app.get("/api/config")
async def api_config():
    """Retorna configurações padrão."""
    return CONFIG_PADRAO


# ── Agente (DeepSeek) ───────────────────────────────────

SYSTEM_PROMPT = """Você é um especialista em precificação de impressão 3D no Brasil.
Seu trabalho: interpretar perguntas sobre custo de impressão 3D e calcular o preço.

Regras:
1. Extraia os parâmetros da mensagem do usuário: peso (gramas), tempo de impressão (horas), material (PLA, PETG, ABS, Silk), quantidade, tempo de mão de obra.
2. Se o usuário mencionar um material, use o preço aproximado:
   - PLA: R$90/kg
   - PLA Premium: R$125/kg
   - PETG Low Cost: R$70/kg
   - PETG Standard: R$110/kg
   - ABS: R$90/kg
   - PLA Silk: R$140/kg
3. Se o usuário não especificar peso ou tempo, peça educadamente.
4. Calcule usando a fórmula:
   - Filamento: (peso_g/1000) × preço_kg × qtd
   - Energia: (140W/1000) × horas × R$0,90/kWh × qtd
   - Máquina (deprec + manut): R$1,25/hora × horas × qtd
   - Mão de obra: horas_humanas × R$40/h
   - Buffer de falha: 10% sobre o subtotal
   - Custo total = soma + buffer
   - Preço sugerido = custo unitário × (1 + margem)
   - Margem padrão: 50%

5. Responda em português, de forma clara e direta.
6. Mostre a composição do custo (filamento, energia, máquina, mão de obra).
7. Sempre termine com o PREÇO SUGERIDO em destaque.

Exemplo:
Usuário: "quanto custa imprimir uma peça de 150g em PETG, 6 horas?"
Resposta:
📊 **Cálculo para peça de 150g em PETG Low Cost (R$70/kg), 6h de impressão:**

| Componente | Valor |
|-----------|-------|
| Filamento (150g × R$0,07/g) | R$ 10,50 |
| Energia (0,14kW × 6h × R$0,90) | R$ 0,76 |
| Máquina (6h × R$1,25/h) | R$ 7,50 |
| Mão de obra (0,5h × R$40/h) | R$ 20,00 |
| Buffer falha (10%) | R$ 3,88 |
| **Custo total** | **R$ 42,64** |

💰 **Preço sugerido (margem 50%): R$ 63,96 → R$ 64,00**
💚 Lucro por peça: R$ 21,36

Se for produção em série (10+ unidades), a mão de obra é diluída e o custo cai ~R$18/peça."""


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """Agente de precificação 3D via DeepSeek."""
    if not DEEPSEEK_KEY:
        # Fallback: tenta interpretar com regex básico
        return fallback_chat(req.mensagem)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                DEEPSEEK_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": req.mensagem},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800,
                },
            )
            if resp.status_code != 200:
                return fallback_chat(req.mensagem)

            data = resp.json()
            reply = data["choices"][0]["message"]["content"]
            return {"resposta": reply, "modo": "ia"}

        except Exception as e:
            return {"resposta": f"Erro ao consultar IA: {e}. Tente novamente.", "modo": "erro"}


# Fallback sem IA — regex simples
import re

def fallback_chat(mensagem: str) -> dict:
    """Interpretação simples por regex quando DeepSeek não está disponível."""
    msg = mensagem.lower()

    peso = None
    horas = None
    qtd = 1
    preco_kg = 70  # default PETG LC
    horas_humanas = 0.5

    # Peso
    m = re.search(r"(\d+)\s*(g|gramas|gr)", msg)
    if m:
        peso = float(m.group(1))

    # Tempo
    m = re.search(r"(\d+[\.,]?\d*)\s*(h|horas|hrs)", msg)
    if m:
        horas = float(m.group(1).replace(",", "."))

    # Quantidade
    m = re.search(r"(\d+)\s*(unidades|peças|un|pecas)", msg)
    if m:
        qtd = int(m.group(1))

    # Material
    for key, info in FILAMENTOS.items():
        if key.replace("_", " ") in msg or info["nome"].lower() in msg:
            preco_kg = info["preco_kg"]
            break
    if "pla" in msg and "premium" in msg:
        preco_kg = FILAMENTOS["pla_premium"]["preco_kg"]
    elif "pla" in msg:
        preco_kg = FILAMENTOS["pla"]["preco_kg"]
    elif "abs" in msg:
        preco_kg = FILAMENTOS["abs"]["preco_kg"]
    elif "silk" in msg:
        preco_kg = FILAMENTOS["silk"]["preco_kg"]
    elif "petg" in msg and "low" in msg:
        preco_kg = FILAMENTOS["petg_lc"]["preco_kg"]

    if peso is None or horas is None:
        return {
            "resposta": (
                "Preciso de mais informações! Me diga:\n"
                "• Peso da peça (ex: 150g)\n"
                "• Tempo de impressão (ex: 6 horas)\n"
                "• Material (opcional — ex: PETG, PLA)\n"
                "• Quantidade (opcional — ex: 10 peças)"
            ),
            "modo": "fallback",
        }

    result = calcular(
        peso_gramas=peso,
        horas_impressao=horas,
        preco_filamento_kg=preco_kg,
        horas_humanas=horas_humanas,
        qtd=qtd,
    )

    c = result["composicao"]
    resposta = (
        f"📊 **Cálculo para {peso}g, {horas}h, {qtd} peça(s)**\n\n"
        f"| Componente | Valor |\n"
        f"|-----------|-------|\n"
        f"| Filamento | R$ {c['filamento']:.2f} |\n"
        f"| Energia | R$ {c['energia']:.2f} |\n"
        f"| Máquina | R$ {c['maquina']:.2f} |\n"
        f"| Mão de obra | R$ {c['mao_de_obra']:.2f} |\n"
        f"| Buffer falha | R$ {c['buffer_falha']:.2f} |\n"
        f"| **Custo total** | **R$ {result['custo_total_lote']:.2f}** |\n\n"
        f"💰 **Preço sugerido (margem {result['parametros']['margem_pct']}%): R$ {result['preco_sugerido']:.2f}**\n"
        f"💚 Lucro por peça: R$ {result['lucro_unitario']:.2f}"
    )
    return {"resposta": resposta, "modo": "fallback", "calculo": result}


# ── Static files (after all routes) ─────────────────────

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# Mount static after routes so / goes to index
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
