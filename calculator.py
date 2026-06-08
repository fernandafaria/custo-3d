"""
calculadora.py — lógica pura de precificação de impressão 3D.
Sem dependências externas, testável isoladamente.
"""

FILAMENTOS = {
    "pla": {"nome": "PLA Standard", "preco_kg": 90},
    "pla_premium": {"nome": "PLA Premium (Voolt)", "preco_kg": 125},
    "petg_lc": {"nome": "PETG Low Cost", "preco_kg": 70},
    "petg": {"nome": "PETG Standard", "preco_kg": 110},
    "abs": {"nome": "ABS", "preco_kg": 90},
    "silk": {"nome": "PLA Silk / Especial", "preco_kg": 140},
}

CONFIG_PADRAO = {
    "tarifa_kwh": 0.90,        # R$/kWh — SP
    "potencia_watts": 140,     # consumo médio real
    "valor_impressora": 5000,  # R$
    "vida_util_horas": 6000,   # horas
    "manutencao_hora": 0.25,   # R$/hora
    "valor_hora_mo": 40,       # R$/hora
    "margem_pct": 50,          # %
    "buffer_falha_pct": 10,    # %
}


def custo_filamento(peso_gramas: float, preco_kg: float, qtd: int = 1) -> float:
    """Custo do filamento para o lote."""
    return (peso_gramas / 1000) * preco_kg * qtd


def custo_energia(potencia_watts: float, horas: float, tarifa_kwh: float, qtd: int = 1) -> float:
    """Custo de energia elétrica para o lote."""
    return (potencia_watts / 1000) * horas * tarifa_kwh * qtd


def custo_maquina(horas: float, valor_impressora: float, vida_util: float, manutencao_hora: float, qtd: int = 1) -> float:
    """Custo de depreciação + manutenção para o lote."""
    depreciacao_hora = valor_impressora / vida_util
    return (depreciacao_hora + manutencao_hora) * horas * qtd


def custo_mao_de_obra(horas_humanas: float, valor_hora: float) -> float:
    """Custo de mão de obra (não multiplica por qtd — é por lote)."""
    return horas_humanas * valor_hora


def calcular(peso_gramas: float,
             horas_impressao: float,
             preco_filamento_kg: float = 70,
             horas_humanas: float = 0.5,
             custo_acabamento: float = 0,
             qtd: int = 1,
             config: dict | None = None) -> dict:
    """
    Calcula custo total e preço de venda de peça(s) impressa(s) em 3D.

    Retorna dict com composição detalhada de custos e preço sugerido.
    """
    c = {**CONFIG_PADRAO, **(config or {})}

    fil = custo_filamento(peso_gramas, preco_filamento_kg, qtd)
    ener = custo_energia(c["potencia_watts"], horas_impressao, c["tarifa_kwh"], qtd)
    maq = custo_maquina(horas_impressao, c["valor_impressora"], c["vida_util_horas"], c["manutencao_hora"], qtd)
    mo = custo_mao_de_obra(horas_humanas, c["valor_hora_mo"])
    acab = custo_acabamento * qtd

    subtotal = fil + ener + maq + mo + acab
    buffer = subtotal * (c["buffer_falha_pct"] / 100)
    custo_total_lote = subtotal + buffer
    custo_unitario = custo_total_lote / qtd

    preco_unitario = custo_unitario * (1 + c["margem_pct"] / 100)
    lucro_unitario = preco_unitario - custo_unitario
    lucro_lote = lucro_unitario * qtd

    return {
        "composicao": {
            "filamento": round(fil, 2),
            "energia": round(ener, 2),
            "maquina": round(maq, 2),
            "mao_de_obra": round(mo, 2),
            "acabamento": round(acab, 2),
            "buffer_falha": round(buffer, 2),
        },
        "custo_total_lote": round(custo_total_lote, 2),
        "custo_unitario": round(custo_unitario, 2),
        "preco_sugerido": round(preco_unitario, 2),
        "lucro_unitario": round(lucro_unitario, 2),
        "lucro_lote": round(lucro_lote, 2),
        "parametros": {
            "peso_gramas": peso_gramas,
            "horas_impressao": horas_impressao,
            "preco_filamento_kg": preco_filamento_kg,
            "horas_humanas": horas_humanas,
            "custo_acabamento": custo_acabamento,
            "qtd": qtd,
            "margem_pct": c["margem_pct"],
            "buffer_falha_pct": c["buffer_falha_pct"],
        }
    }
