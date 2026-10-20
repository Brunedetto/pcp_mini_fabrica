"""
Módulo 1 - Gerador de dados fictícios para OEE
Simula 90 dias de produção de velas de ignição em 3 linhas de montagem, 3 turnos/dia.

Saídas (pasta /dados):
  - producao_turnos.csv : 1 linha por data x turno x linha
  - paradas.csv         : 1 linha por parada ocorrida (com motivo e duração)
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)  # semente fixa = resultados reproduzíveis

# ---------------- Premissas (ajuste conforme sua vivência) ----------------
DIAS = 90
DATA_INICIO = "2026-07-01"
TURNOS = {"1º Turno": 480, "2º Turno": 480, "3º Turno": 480}  # min planejados (já sem intervalo)

# Linha: ciclo ideal (segundos por peça) e "perfil" de qualidade/desempenho
LINHAS = {
    "Linha A": {"ciclo_ideal_s": 2.0, "desempenho_med": 0.90, "refugo_med": 0.015},
    "Linha B": {"ciclo_ideal_s": 2.5, "desempenho_med": 0.85, "refugo_med": 0.025},
    "Linha C": {"ciclo_ideal_s": 3.0, "desempenho_med": 0.80, "refugo_med": 0.035},  # pior linha
}

# Motivos de parada: (probabilidade relativa, duração média em min, categoria)
MOTIVOS = {
    "Setup / Troca de produto": (0.25, 28, "Planejada"),
    "Quebra de máquina":        (0.20, 35, "Não planejada"),
    "Falta de material":        (0.20, 18, "Não planejada"),
    "Ajuste de processo":       (0.15, 12, "Não planejada"),
    "Limpeza / Manutenção":     (0.10, 15, "Planejada"),
    "Aguardando qualidade":     (0.10, 10, "Não planejada"),
}
nomes = list(MOTIVOS)
pesos = np.array([MOTIVOS[m][0] for m in nomes])

# ---------------- Geração ----------------
datas = pd.date_range(DATA_INICIO, periods=DIAS, freq="D")
producao, paradas = [], []

for data in datas:
    for turno, t_plan in TURNOS.items():
        for linha, p in LINHAS.items():
            # número de paradas no turno (3º turno tem um pouco mais de problemas)
            lam = 3.0 if turno == "3º Turno" else 2.3
            n_paradas = rng.poisson(lam)

            tempo_parado = 0.0
            for _ in range(n_paradas):
                motivo = rng.choice(nomes, p=pesos / pesos.sum())
                dur = max(2, rng.gamma(shape=2.0, scale=MOTIVOS[motivo][1] / 2.0))
                dur = round(float(dur), 1)
                tempo_parado += dur
                paradas.append({
                    "data": data.date(), "turno": turno, "linha": linha,
                    "motivo": motivo, "categoria": MOTIVOS[motivo][2],
                    "duracao_min": dur,
                })

            tempo_parado = min(tempo_parado, t_plan * 0.6)  # limite realista
            tempo_operando = t_plan - tempo_parado

            # Desempenho: velocidade real vs. ideal (microparadas, lentidão)
            desempenho = float(np.clip(rng.normal(p["desempenho_med"], 0.04), 0.60, 1.0))
            pecas_ideais = tempo_operando * 60 / p["ciclo_ideal_s"]
            total_produzido = int(pecas_ideais * desempenho)

            # Refugo
            taxa_refugo = float(np.clip(rng.normal(p["refugo_med"], 0.01), 0.002, 0.10))
            refugo = int(total_produzido * taxa_refugo)

            producao.append({
                "data": data.date(), "turno": turno, "linha": linha,
                "tempo_planejado_min": t_plan,
                "ciclo_ideal_s": p["ciclo_ideal_s"],
                "total_produzido": total_produzido,
                "refugo": refugo,
            })

# ---------------- Exportação ----------------
saida = Path(__file__).resolve().parent.parent / "dados"
saida.mkdir(exist_ok=True)
df_prod = pd.DataFrame(producao)
df_par = pd.DataFrame(paradas)
df_prod.to_csv(saida / "producao_turnos.csv", index=False)
df_par.to_csv(saida / "paradas.csv", index=False)

print(f"producao_turnos.csv: {len(df_prod):,} linhas")
print(f"paradas.csv:         {len(df_par):,} linhas")
