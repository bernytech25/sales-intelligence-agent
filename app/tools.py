"""
Tools del agente: funciones que consultan y analizan los datos de ventas.
Cada función es independiente y retorna un dict listo para serializar.
"""

from functools import lru_cache

import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "ventas.csv"


@lru_cache(maxsize=1)
def _load_df_cached() -> pd.DataFrame:
    """Lee el CSV una sola vez por proceso; los llamados subsiguientes
    reusan el DataFrame en memoria en vez de releer disco en cada tool call."""
    return pd.read_csv(DATA_PATH)


def _load_df() -> pd.DataFrame:
    # .copy() evita que una tool mute el DataFrame cacheado y afecte a las demás
    return _load_df_cached().copy()


def _con_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega la columna 'mes' (YYYY-MM) a partir de 'fecha'. Centraliza el
    parseo que antes estaba duplicado en 3 funciones distintas."""
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["mes"] = df["fecha"].dt.strftime("%Y-%m")
    return df


def ventas_por_vendedor() -> dict:
    df = _load_df()
    resultado = df.groupby("vendedor")["total"].sum().sort_values(ascending=False)
    return resultado.to_dict()


def ventas_por_categoria() -> dict:
    df = _load_df()
    resultado = df.groupby("categoria")["total"].sum().sort_values(ascending=False)
    return resultado.to_dict()


def ventas_por_region() -> dict:
    df = _load_df()
    resultado = df.groupby("region")["total"].sum().sort_values(ascending=False)
    return resultado.to_dict()


def ventas_por_mes() -> dict:
    df = _con_mes(_load_df())
    resultado = df.groupby("mes")["total"].sum().sort_index()
    return resultado.to_dict()


def producto_mas_vendido() -> dict:
    df = _load_df()
    resultado = df.groupby("producto")["cantidad"].sum().sort_values(ascending=False)
    top = resultado.index[0]
    return {"producto": top, "cantidad_total": int(resultado[top])}


def ventas_vendedor_por_mes(vendedor: str) -> dict:
    df = _con_mes(_load_df())
    filtro = df[df["vendedor"].str.lower() == vendedor.lower()]
    if filtro.empty:
        return {"error": f"Vendedor '{vendedor}' no encontrado.", "vendedores_disponibles": df["vendedor"].unique().tolist()}
    resultado = filtro.groupby("mes")["total"].sum().sort_index()
    return {"vendedor": vendedor, "ventas_por_mes": resultado.to_dict()}


def vendedor_ranking_periodo(mes_desde: str, mes_hasta: str, orden: str = "desc") -> dict:
    """Rankea a los vendedores por ventas totales dentro de un rango de meses
    (formato YYYY-MM para ambos límites, inclusive). Usar para preguntas del
    tipo '¿quién vendió más/menos en los últimos N meses?' -- evita tener que
    consultar vendedor por vendedor o mes por mes para armar el ranking.
    orden='desc' -> el primero es el que más vendió; orden='asc' -> el que menos."""
    df = _con_mes(_load_df())
    filtro = df[(df["mes"] >= mes_desde) & (df["mes"] <= mes_hasta)]
    if filtro.empty:
        meses_disponibles = sorted(df["mes"].unique().tolist())
        return {"error": f"No hay datos entre '{mes_desde}' y '{mes_hasta}'.", "meses_disponibles": meses_disponibles}
    resultado = filtro.groupby("vendedor")["total"].sum().sort_values(ascending=(orden == "asc"))
    extremo = resultado.index[0]
    return {
        "periodo": f"{mes_desde} a {mes_hasta}",
        "orden": orden,
        "vendedor": extremo,
        "total_vendido": float(resultado[extremo]),
        "ranking_completo": resultado.to_dict(),
    }


def ventas_producto_por_region(producto: str) -> dict:
    df = _load_df()
    filtro = df[df["producto"].str.lower() == producto.lower()]
    if filtro.empty:
        return {"error": "Producto no encontrado.", "productos_disponibles": df["producto"].unique().tolist()}
    por_region = filtro.groupby("region")["cantidad"].sum().sort_values(ascending=False)
    por_region_pesos = filtro.groupby("region")["total"].sum().sort_values(ascending=False)
    return {
        "producto": producto,
        "region_top": por_region.index[0],
        "unidades_por_region": por_region.to_dict(),
        "pesos_por_region": por_region_pesos.to_dict(),
    }


def _ranking_por_region(entidad: str, campo: str, top_n: int, metrica: str) -> dict:
    """Construye un ranking compacto por región para una entidad de ventas.

    Es un helper privado compartido por las tools de vendedores y productos:
    centraliza validación, agregación y formato sin exponer una tool genérica
    que obligue al LLM a conocer nombres internos de columnas.
    """
    if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
        return {"error": "top_n debe ser un entero mayor o igual a 1."}
    if metrica not in {"total", "cantidad"}:
        return {"error": "metrica debe ser 'total' o 'cantidad'."}

    df = _load_df()
    resumen = (
        df.groupby(["region", campo])
        .agg(total_vendido=("total", "sum"), unidades_vendidas=("cantidad", "sum"))
        .reset_index()
    )
    regiones = df.groupby("region")["total"].sum().sort_values(ascending=False).index
    columna_orden = "total_vendido" if metrica == "total" else "unidades_vendidas"
    ranking_por_region = {}

    for region in regiones:
        ranking = resumen[resumen["region"] == region].sort_values(
            [columna_orden, campo], ascending=[False, True]
        ).head(top_n)
        ranking_por_region[region] = [
            {
                entidad: fila[campo],
                "total_vendido": float(fila["total_vendido"]),
                "unidades_vendidas": int(fila["unidades_vendidas"]),
            }
            for _, fila in ranking.iterrows()
        ]

    return {
        "metrica": metrica,
        "top_n": top_n,
        "ranking_por_region": ranking_por_region,
    }


def ranking_vendedores_por_region(top_n: int = 5, metrica: str = "total") -> dict:
    """Devuelve los vendedores con mejor desempeño en cada región.

    Por defecto los ordena por facturación (``metrica='total'``). Usar
    ``metrica='cantidad'`` para ordenarlos por unidades vendidas.
    """
    return _ranking_por_region("vendedor", "vendedor", top_n, metrica)


def ranking_productos_por_region(top_n: int = 5, metrica: str = "cantidad") -> dict:
    """Devuelve los productos más vendidos en cada región.

    Por defecto los ordena por unidades (``metrica='cantidad'``). Usar
    ``metrica='total'`` para ordenarlos por facturación.
    """
    return _ranking_por_region("producto", "producto", top_n, metrica)


def lista_productos() -> dict:
    """Lista todos los productos con nombre, categoría y unidades vendidas."""
    df = _load_df()
    productos = df.groupby(["producto", "categoria"])["cantidad"].sum().reset_index()
    productos = productos.sort_values("cantidad", ascending=False)
    return {
        "total_productos_distintos": int(df["producto"].nunique()),
        "total_unidades_vendidas": int(df["cantidad"].sum()),
        "productos": [
            {"nombre": row["producto"], "categoria": row["categoria"], "unidades_vendidas": int(row["cantidad"])}
            for row in productos.to_dict("records")
        ]
    }


def resumen_general() -> dict:
    df = _load_df()
    return {
        "total_ingresos": float(df["total"].sum()),
        "total_transacciones": int(len(df)),
        "ticket_promedio": float(df["total"].mean()),
        "productos_distintos": int(df["producto"].nunique()),
        "vendedores": int(df["vendedor"].nunique()),
    }
