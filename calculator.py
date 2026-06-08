"""
calculadora.py — lógica pura de precificação de impressão 3D.
Sem dependências externas, testável isoladamente.
"""
from typing import Union

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
    "purga_tempo_h": 0.033,    # 2 min por troca de cor
    "purga_filamento_g": 3,    # ~3g de filamento por troca
    "setup_cor_min": 5,        # 5 min extra de M.O. por cor adicional
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
             preco_filamento_kg: Union[float, list] = 70,
             horas_humanas: float = 0.5,
             custo_acabamento: float = 0,
             qtd: int = 1,
             cores: int = 1,
             config: Union[dict, None] = None) -> dict:
    """
    Calcula custo total e preço de venda de peça(s) impressa(s) em 3D.

    Parâmetros:
        peso_gramas: peso do modelo (por peça) em gramas
        horas_impressao: tempo de impressão (por peça) em horas
        preco_filamento_kg: preço do filamento por kg (float) ou lista de preços por cor
        horas_humanas: horas de trabalho humano (setup + pós, por lote)
        custo_acabamento: custo extra de acabamento (por peça)
        qtd: quantidade de peças no lote
        cores: número de cores diferentes (afeta purga, filamento extra e setup)

    Retorna dict com composição detalhada de custos e preço sugerido.
    """
    c = {**CONFIG_PADRAO, **(config or {})}

    # Preço do filamento: se for lista, usa média; senão usa o valor único
    if isinstance(preco_filamento_kg, list):
        preco_medio = sum(preco_filamento_kg) / len(preco_filamento_kg)
    else:
        preco_medio = preco_filamento_kg

    trocas = max(0, cores - 1)  # número de trocas de cor

    # Tempo extra de impressão por troca de cor (purga)
    horas_extra_por_peca = trocas * c["purga_tempo_h"]
    horas_total_por_peca = horas_impressao + horas_extra_por_peca

    # Filamento extra por troca de cor (purga/wipe tower)
    filamento_extra_por_peca = trocas * c["purga_filamento_g"]
    peso_total_por_peca = peso_gramas + filamento_extra_por_peca

    # Mão de obra extra por cor adicional (configurar slicer, carregar filamento)
    horas_humanas_extra = trocas * (c["setup_cor_min"] / 60)
    horas_humanas_total = horas_humanas + horas_humanas_extra

    fil = custo_filamento(peso_total_por_peca, preco_medio, qtd)
    ener = custo_energia(c["potencia_watts"], horas_total_por_peca, c["tarifa_kwh"], qtd)
    maq = custo_maquina(horas_total_por_peca, c["valor_impressora"], c["vida_util_horas"], c["manutencao_hora"], qtd)
    mo = custo_mao_de_obra(horas_humanas_total, c["valor_hora_mo"])
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
            "horas_impressao_com_purga": round(horas_total_por_peca, 2),
            "preco_filamento_kg": preco_filamento_kg,
            "preco_medio_kg": round(preco_medio, 2),
            "filamento_extra_purga_g": round(filamento_extra_por_peca, 2),
            "peso_total_com_purga_g": round(peso_total_por_peca, 2),
            "horas_humanas": horas_humanas,
            "horas_humanas_total": round(horas_humanas_total, 2),
            "custo_acabamento": custo_acabamento,
            "qtd": qtd,
            "cores": cores,
            "margem_pct": c["margem_pct"],
            "buffer_falha_pct": c["buffer_falha_pct"],
        }
    }
