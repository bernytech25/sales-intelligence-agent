"""
Tools del agente: funciones que consultan y analizan los datos de ventas.
Cada función es independiente y retorna un dict listo para serializar.
"""

from functools import lru_cache
import re

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


def _filtrar_por_periodo(
    df: pd.DataFrame, mes_desde: str | None, mes_hasta: str | None
) -> tuple[pd.DataFrame | None, str | None, str | None]:
    """Filtra un DataFrame por un rango mensual inclusivo y valida su contrato.

    Devuelve ``(datos, periodo, error)`` para que las tools públicas mantengan
    el patrón existente de devolver un dict con ``error`` en vez de lanzar una
    excepción ante parámetros de consulta inválidos.
    """
    if mes_desde is None and mes_hasta is None:
        return df, "todo el período", None
    if not mes_desde or not mes_hasta:
        return None, None, "mes_desde y mes_hasta deben enviarse juntos en formato YYYY-MM."

    patron_mes = r"^\d{4}-(0[1-9]|1[0-2])$"
    if not re.fullmatch(patron_mes, mes_desde) or not re.fullmatch(patron_mes, mes_hasta):
        return None, None, "mes_desde y mes_hasta deben tener formato YYYY-MM."
    if mes_desde > mes_hasta:
        return None, None, "mes_desde no puede ser posterior a mes_hasta."

    df = _con_mes(df)
    filtro = df[(df["mes"] >= mes_desde) & (df["mes"] <= mes_hasta)]
    if filtro.empty:
        return None, None, f"No hay datos entre '{mes_desde}' y '{mes_hasta}'."
    return filtro, f"{mes_desde} a {mes_hasta}", None


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


def _ranking_por_region(
    entidad: str,
    campo: str,
    top_n: int,
    metrica: str,
    mes_desde: str | None = None,
    mes_hasta: str | None = None,
) -> dict:
    """Construye un ranking compacto por región para una entidad de ventas.

    Es un helper privado compartido por las tools de vendedores y productos:
    centraliza validación, agregación y formato sin exponer una tool genérica
    que obligue al LLM a conocer nombres internos de columnas.
    """
    if not isinstance(top_n, int) or isinstance(top_n, bool) or top_n < 1:
        return {"error": "top_n debe ser un entero mayor o igual a 1."}
    if metrica not in {"total", "cantidad"}:
        return {"error": "metrica debe ser 'total' o 'cantidad'."}

    df, periodo, error = _filtrar_por_periodo(_load_df(), mes_desde, mes_hasta)
    if error:
        return {"error": error}
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
        "periodo": periodo,
        "metrica": metrica,
        "top_n": top_n,
        "ranking_por_region": ranking_por_region,
    }


def ranking_vendedores_por_region(
    top_n: int = 5,
    metrica: str = "total",
    mes_desde: str | None = None,
    mes_hasta: str | None = None,
) -> dict:
    """Devuelve los vendedores con mejor desempeño en cada región.

    Por defecto los ordena por facturación (``metrica='total'``). Usar
    ``metrica='cantidad'`` para ordenarlos por unidades vendidas.
    """
    return _ranking_por_region("vendedor", "vendedor", top_n, metrica, mes_desde, mes_hasta)


def ranking_productos_por_region(
    top_n: int = 5,
    metrica: str = "cantidad",
    mes_desde: str | None = None,
    mes_hasta: str | None = None,
) -> dict:
    """Devuelve los productos más vendidos en cada región.

    Por defecto los ordena por unidades (``metrica='cantidad'``). Usar
    ``metrica='total'`` para ordenarlos por facturación.
    """
    return _ranking_por_region("producto", "producto", top_n, metrica, mes_desde, mes_hasta)


def analisis_vendedores_y_productos_por_region(
    mes_desde: str,
    mes_hasta: str,
    top_vendedores: int = 1,
    top_productos: int = 3,
    metrica_vendedor: str = "total",
    metrica_producto: str = "cantidad",
) -> dict:
    """Relaciona vendedores líderes y sus productos líderes por región y período.

    Es una herramienta de reporte jerárquico para preguntas que requieren el
    cruce exacto región → vendedor → producto, sin pedirle al LLM que una
    resultados de múltiples consultas independientes.
    """
    if not isinstance(top_vendedores, int) or isinstance(top_vendedores, bool) or top_vendedores < 1:
        return {"error": "top_vendedores debe ser un entero mayor o igual a 1."}
    if not isinstance(top_productos, int) or isinstance(top_productos, bool) or top_productos < 1:
        return {"error": "top_productos debe ser un entero mayor o igual a 1."}
    if metrica_vendedor not in {"total", "cantidad"}:
        return {"error": "metrica_vendedor debe ser 'total' o 'cantidad'."}
    if metrica_producto not in {"total", "cantidad"}:
        return {"error": "metrica_producto debe ser 'total' o 'cantidad'."}

    df, periodo, error = _filtrar_por_periodo(_load_df(), mes_desde, mes_hasta)
    if error:
        return {"error": error}

    vendedores = (
        df.groupby(["region", "vendedor"])
        .agg(total_vendido=("total", "sum"), unidades_vendidas=("cantidad", "sum"))
        .reset_index()
    )
    regiones = df.groupby("region")["total"].sum().sort_values(ascending=False).index
    columna_vendedor = "total_vendido" if metrica_vendedor == "total" else "unidades_vendidas"
    columna_producto = "total_vendido" if metrica_producto == "total" else "unidades_vendidas"
    analisis_por_region = {}

    for region in regiones:
        lideres = vendedores[vendedores["region"] == region].sort_values(
            [columna_vendedor, "vendedor"], ascending=[False, True]
        ).head(top_vendedores)
        detalle_vendedores = []

        for _, lider in lideres.iterrows():
            ventas_vendedor = df[
                (df["region"] == region) & (df["vendedor"] == lider["vendedor"])
            ]
            productos = (
                ventas_vendedor.groupby("producto")
                .agg(total_vendido=("total", "sum"), unidades_vendidas=("cantidad", "sum"))
                .reset_index()
                .sort_values([columna_producto, "producto"], ascending=[False, True])
                .head(top_productos)
            )
            detalle_vendedores.append({
                "vendedor": lider["vendedor"],
                "total_vendido": float(lider["total_vendido"]),
                "unidades_vendidas": int(lider["unidades_vendidas"]),
                "productos_top": [
                    {
                        "producto": producto["producto"],
                        "total_vendido": float(producto["total_vendido"]),
                        "unidades_vendidas": int(producto["unidades_vendidas"]),
                    }
                    for _, producto in productos.iterrows()
                ],
            })
        analisis_por_region[region] = detalle_vendedores

    return {
        "periodo": periodo,
        "top_vendedores": top_vendedores,
        "top_productos": top_productos,
        "metrica_vendedor": metrica_vendedor,
        "metrica_producto": metrica_producto,
        "analisis_por_region": analisis_por_region,
    }


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
