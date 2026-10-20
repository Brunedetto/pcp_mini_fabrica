"""
Módulo 1 - Cálculo do OEE (Overall Equipment Effectiveness)

    Disponibilidade = tempo operando / tempo planejado
    Desempenho      = (total produzido x ciclo ideal) / tempo operando
    Qualidade       = peças boas / total produzido
    OEE             = Disponibilidade x Desempenho x Qualidade

Saídas (pasta /dados):
  - oee_turnos.csv   : OEE por data x turno x linha (alimenta o Power BI)
  - pareto_paradas.csv : minutos parados por motivo (Pareto)
"""
import pandas as pd
from pathlib import Path

base = Path(__file__).resolve().parent.parent / "dados"
prod = pd.read_csv(base / "producao_turnos.csv", parse_dates=["data"])
par = pd.read_csv(base / "paradas.csv", parse_dates=["data"])

# Tempo parado por turno/linha, vindo da tabela de paradas
parado = (par.groupby(["data", "turno", "linha"], as_index=False)["duracao_min"]
             .sum().rename(columns={"duracao_min": "tempo_parado_min"}))

df = prod.merge(parado, on=["data", "turno", "linha"], how="left")
df["tempo_parado_min"] = df["tempo_parado_min"].fillna(0)

# Garante coerência: parada nunca excede o tempo planejado
df["tempo_parado_min"] = df[["tempo_parado_min", "tempo_planejado_min"]].min(axis=1)
df["tempo_operando_min"] = df["tempo_planejado_min"] - df["tempo_parado_min"]
df["pecas_boas"] = df["total_produzido"] - df["refugo"]

# Os 3 fatores do OEE
df["disponibilidade"] = df["tempo_operando_min"] / df["tempo_planejado_min"]
df["desempenho"] = (df["total_produzido"] * df["ciclo_ideal_s"] / 60) / df["tempo_operando_min"]
df["qualidade"] = df["pecas_boas"] / df["total_produzido"]
df["desempenho"] = df["desempenho"].clip(upper=1.0)
df["oee"] = df["disponibilidade"] * df["desempenho"] * df["qualidade"]

df.to_csv(base / "oee_turnos.csv", index=False)

# Pareto de paradas
pareto = (par.groupby(["motivo", "categoria"], as_index=False)["duracao_min"].sum()
             .sort_values("duracao_min", ascending=False))
pareto["pct"] = pareto["duracao_min"] / pareto["duracao_min"].sum()
pareto["pct_acumulado"] = pareto["pct"].cumsum()
pareto.to_csv(base / "pareto_paradas.csv", index=False)

# ---------------- Resumo no terminal ----------------
def resumo(g):
    # Médias ponderadas pelo tempo/produção (forma correta de agregar OEE)
    disp = g["tempo_operando_min"].sum() / g["tempo_planejado_min"].sum()
    desemp = (g["total_produzido"] * g["ciclo_ideal_s"] / 60).sum() / g["tempo_operando_min"].sum()
    qual = g["pecas_boas"].sum() / g["total_produzido"].sum()
    return pd.Series({"Disp.": disp, "Desemp.": desemp, "Qualid.": qual, "OEE": disp * desemp * qual})

print("\nOEE por linha:")
print(df.groupby("linha").apply(resumo, include_groups=False).map("{:.1%}".format))
print("\nOEE por turno:")
print(df.groupby("turno").apply(resumo, include_groups=False).map("{:.1%}".format))
print("\nPareto de paradas (minutos):")
print(pareto[["motivo", "duracao_min", "pct", "pct_acumulado"]]
      .assign(pct=lambda d: d.pct.map("{:.1%}".format),
              pct_acumulado=lambda d: d.pct_acumulado.map("{:.1%}".format))
      .to_string(index=False))
