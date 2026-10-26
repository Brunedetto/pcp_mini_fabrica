"""
Módulo 2 - MRP (Planejamento das Necessidades de Materiais)

Para cada componente e cada semana:
    NB   = demanda de velas x quantidade por vela
    Disp = estoque inicial + recebimento programado
    NL   = máximo entre 0 e (NB + estoque de segurança - Disp)
    Q    = NL arredondada para cima ao múltiplo do lote (0 se NL = 0)
    EF   = Disp + Q - NB
    Liberação = semana - lead time (só quando Q > 0)
    Status    = ATRASADA se a liberação for semana 0 ou anterior

Entradas (pasta dados_br): mps.csv, bom.csv, recebimentos.csv
Saídas   (pasta dados_br): mrp_resultado.csv, mrp_cenario_30.csv
"""
import math
from pathlib import Path

import pandas as pd

PASTA = Path(__file__).resolve().parent.parent / "dados_br"


def ler_dados():
    mps = pd.read_csv(PASTA / "mps.csv", sep=";", decimal=",", encoding="utf-8-sig")
    bom = pd.read_csv(PASTA / "bom.csv", sep=";", decimal=",", encoding="utf-8-sig")
    rec = pd.read_csv(PASTA / "recebimentos.csv", sep=";", decimal=",", encoding="utf-8-sig")
    return mps, bom, rec


def mrp_componente(comp, demanda, recebimentos):
    """
    comp: linha do bom.csv (Series) com os parâmetros do componente
    demanda: lista com a demanda semanal de velas (semana 1, 2, 3...)
    recebimentos: dict {semana: quantidade} de recebimentos programados
    Devolve uma lista de dicionários, um por semana.
    """
    estoque = int(comp["estoque_inicial"])
    lote = int(comp["lote_multiplo"])
    es = int(comp["estoque_seguranca"])
    lt = int(comp["lead_time_sem"])
    qtd = int(comp["qtd_por_vela"])

    linhas = []
    for semana, d in enumerate(demanda, start=1):
        nb = int(d) * qtd                              # necessidade bruta
        rp = int(recebimentos.get(semana, 0))          # recebimento programado
        disp = estoque + rp                            # disponível antes da ordem
        nl = max(0, nb + es - disp)                    # necessidade líquida
        q = math.ceil(nl / lote) * lote if nl > 0 else 0   # ordem planejada
        ef = disp + q - nb                             # estoque final

        if q > 0:
            liberacao = semana - lt
            status = "ATRASADA" if liberacao <= 0 else "No prazo"
        else:
            liberacao, status = None, ""

        linhas.append({
            "componente": comp["componente"],
            "semana": semana,
            "nec_bruta": nb,
            "estoque_inicial": estoque,
            "receb_programado": rp,
            "disp": disp,
            "nec_liquida": nl,
            "ordem": q,
            "estoque_final": ef,
            "liberacao": liberacao,
            "status": status,
        })
        estoque = ef          # o estoque final vira o inicial da semana seguinte
    return linhas


def rodar_mrp(demanda, bom, rec):
    resultado = []
    for _, comp in bom.iterrows():
        r = rec[rec["componente"] == comp["componente"]]
        recebimentos = dict(zip(r["semana"], r["quantidade"]))
        resultado += mrp_componente(comp, demanda, recebimentos)
    df = pd.DataFrame(resultado)
    df["liberacao"] = df["liberacao"].astype("Int64")   # inteiro, com vazio quando não há ordem
    return df


def testar(df, bom, rec, demanda):
    """Validações: estoque >= segurança, ordens múltiplas do lote e fechamento do saldo."""
    for _, comp in bom.iterrows():
        d = df[df["componente"] == comp["componente"]]
        nome = comp["componente"]
        assert (d["estoque_final"] >= comp["estoque_seguranca"]).all(), f"{nome}: estoque abaixo da segurança"
        assert (d["ordem"] % comp["lote_multiplo"] == 0).all(), f"{nome}: ordem fora do múltiplo do lote"
        recebido = rec.loc[rec["componente"] == nome, "quantidade"].sum()
        saldo = comp["estoque_inicial"] + recebido + d["ordem"].sum() - d["nec_bruta"].sum()
        assert saldo == d["estoque_final"].iloc[-1], f"{nome}: saldo não fecha"
    print("Testes OK: estoque de segurança, lote múltiplo e fechamento do saldo.")


def salvar(df, nome, cenario):
    df = df.copy()
    df.insert(0, "cenario", cenario)
    df.to_csv(PASTA / nome, index=False, sep=";", decimal=",", encoding="utf-8-sig")


if __name__ == "__main__":
    mps, bom, rec = ler_dados()

    # Cenário base
    demanda_base = mps["demanda_velas"].tolist()
    base = rodar_mrp(demanda_base, bom, rec)
    testar(base, bom, rec, demanda_base)
    salvar(base, "mrp_resultado.csv", "Base")

    # Cenário +30% a partir da semana 7
    demanda_30 = [round(d * 1.3) if s >= 7 else d for s, d in zip(mps["semana"], demanda_base)]
    c30 = rodar_mrp(demanda_30, bom, rec)
    testar(c30, bom, rec, demanda_30)
    salvar(c30, "mrp_cenario_30.csv", "Demanda +30% (sem 7+)")

    # Resumo no terminal
    print("\nOrdens atrasadas no cenário base:")
    print(base[base["status"] == "ATRASADA"][["componente", "semana", "ordem", "liberacao"]].to_string(index=False))
    print("\nTotal de ordens planejadas (unidades) por componente:")
    resumo = pd.DataFrame({
        "base": base.groupby("componente")["ordem"].sum(),
        "+30%": c30.groupby("componente")["ordem"].sum(),
    })
    resumo["diferença"] = resumo["+30%"] - resumo["base"]
    print(resumo.to_string())
