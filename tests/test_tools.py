"""
Tests unitarios para las tools del agente.
Cada test verifica que la función retorna el tipo correcto
y que maneja casos edge correctamente.
"""

import pytest
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools import (
    ventas_por_vendedor,
    ventas_por_categoria,
    ventas_por_region,
    ventas_por_mes,
    ventas_vendedor_por_mes,
    vendedor_ranking_periodo,
    ventas_producto_por_region,
    ranking_vendedores_por_region,
    ranking_productos_por_region,
    analisis_vendedores_y_productos_por_region,
    DATA_PATH,
    lista_productos,
    producto_mas_vendido,
    resumen_general,
)


# ── ventas_por_vendedor ───────────────────────────────────────────────────────

def test_ventas_por_vendedor_retorna_dict():
    resultado = ventas_por_vendedor()
    assert isinstance(resultado, dict)

def test_ventas_por_vendedor_no_vacio():
    resultado = ventas_por_vendedor()
    assert len(resultado) > 0

def test_ventas_por_vendedor_valores_positivos():
    resultado = ventas_por_vendedor()
    for vendedor, total in resultado.items():
        assert total > 0, f"{vendedor} tiene ventas negativas"

def test_ventas_por_vendedor_ordenado_descendente():
    resultado = ventas_por_vendedor()
    valores = list(resultado.values())
    assert valores == sorted(valores, reverse=True)


# ── ventas_por_categoria ──────────────────────────────────────────────────────

def test_ventas_por_categoria_retorna_dict():
    assert isinstance(ventas_por_categoria(), dict)

def test_ventas_por_categoria_tiene_categorias():
    resultado = ventas_por_categoria()
    assert len(resultado) > 0


# ── ventas_por_region ─────────────────────────────────────────────────────────

def test_ventas_por_region_retorna_dict():
    assert isinstance(ventas_por_region(), dict)

def test_ventas_por_region_regiones_conocidas():
    resultado = ventas_por_region()
    regiones = set(resultado.keys())
    assert len(regiones) > 0


# ── ventas_por_mes ────────────────────────────────────────────────────────────

def test_ventas_por_mes_retorna_dict():
    assert isinstance(ventas_por_mes(), dict)

def test_ventas_por_mes_formato_fecha():
    resultado = ventas_por_mes()
    for mes in resultado.keys():
        assert len(mes) == 7, f"Formato incorrecto: {mes}"
        assert mes[4] == "-", f"Formato incorrecto: {mes}"


# ── ventas_vendedor_por_mes ───────────────────────────────────────────────────

def test_ventas_vendedor_por_mes_vendedor_existente():
    vendedores = list(ventas_por_vendedor().keys())
    vendedor = vendedores[0]
    resultado = ventas_vendedor_por_mes(vendedor)
    assert "ventas_por_mes" in resultado
    assert isinstance(resultado["ventas_por_mes"], dict)

def test_ventas_vendedor_por_mes_vendedor_inexistente():
    resultado = ventas_vendedor_por_mes("Vendedor Fantasma")
    assert "error" in resultado
    assert "vendedores_disponibles" in resultado

def test_ventas_vendedor_por_mes_case_insensitive():
    vendedores = list(ventas_por_vendedor().keys())
    vendedor = vendedores[0]
    resultado = ventas_vendedor_por_mes(vendedor.upper())
    assert "ventas_por_mes" in resultado


# ── vendedor_ranking_periodo ──────────────────────────────────────────────────

def test_vendedor_ranking_periodo_estructura():
    resultado = vendedor_ranking_periodo("2024-01", "2024-12")
    campos = ["periodo", "orden", "vendedor", "total_vendido", "ranking_completo"]
    for campo in campos:
        assert campo in resultado, f"Falta campo: {campo}"

def test_vendedor_ranking_periodo_orden_desc_es_el_mayor():
    resultado = vendedor_ranking_periodo("2024-01", "2024-12", orden="desc")
    valores = list(resultado["ranking_completo"].values())
    assert valores == sorted(valores, reverse=True)
    assert resultado["total_vendido"] == max(valores)

def test_vendedor_ranking_periodo_orden_asc_es_el_menor():
    resultado = vendedor_ranking_periodo("2024-01", "2024-12", orden="asc")
    valores = list(resultado["ranking_completo"].values())
    assert valores == sorted(valores)
    assert resultado["total_vendido"] == min(valores)

def test_vendedor_ranking_periodo_rango_sin_datos():
    resultado = vendedor_ranking_periodo("2030-01", "2030-12")
    assert "error" in resultado
    assert "meses_disponibles" in resultado

def test_vendedor_ranking_periodo_filtra_por_rango():
    completo = vendedor_ranking_periodo("2024-01", "2024-12")
    parcial = vendedor_ranking_periodo("2024-01", "2024-03")
    assert sum(parcial["ranking_completo"].values()) <= sum(completo["ranking_completo"].values())


# ── ventas_producto_por_region ────────────────────────────────────────────────

def test_ventas_producto_por_region_producto_existente():
    productos = [p["nombre"] for p in lista_productos()["productos"]]
    producto = productos[0]
    resultado = ventas_producto_por_region(producto)
    assert "region_top" in resultado
    assert "unidades_por_region" in resultado
    assert "pesos_por_region" in resultado

def test_ventas_producto_por_region_producto_inexistente():
    resultado = ventas_producto_por_region("Producto Fantasma")
    assert "error" in resultado
    assert "productos_disponibles" in resultado

def test_ventas_producto_por_region_case_insensitive():
    productos = [p["nombre"] for p in lista_productos()["productos"]]
    producto = productos[0]
    resultado = ventas_producto_por_region(producto.lower())
    assert "region_top" in resultado


# ── rankings por región ──────────────────────────────────────────────────────

def test_ranking_vendedores_por_region_estructura_y_orden():
    resultado = ranking_vendedores_por_region(top_n=2)
    assert resultado["metrica"] == "total"
    assert resultado["top_n"] == 2
    assert set(resultado["ranking_por_region"]) == set(ventas_por_region())
    for ranking in resultado["ranking_por_region"].values():
        assert 1 <= len(ranking) <= 2
        assert all("vendedor" in fila for fila in ranking)
        assert [fila["total_vendido"] for fila in ranking] == sorted(
            (fila["total_vendido"] for fila in ranking), reverse=True
        )


def test_ranking_vendedores_por_region_permite_unidades_y_valida_parametros():
    por_unidades = ranking_vendedores_por_region(top_n=1, metrica="cantidad")
    for ranking in por_unidades["ranking_por_region"].values():
        assert len(ranking) == 1
    assert "error" in ranking_vendedores_por_region(top_n=0)
    assert "error" in ranking_vendedores_por_region(metrica="margen")


def test_ranking_productos_por_region_estructura_y_orden():
    resultado = ranking_productos_por_region(top_n=3)
    assert resultado["metrica"] == "cantidad"
    assert resultado["top_n"] == 3
    assert set(resultado["ranking_por_region"]) == set(ventas_por_region())
    for ranking in resultado["ranking_por_region"].values():
        assert 1 <= len(ranking) <= 3
        assert all("producto" in fila for fila in ranking)
        assert [fila["unidades_vendidas"] for fila in ranking] == sorted(
            (fila["unidades_vendidas"] for fila in ranking), reverse=True
        )


def test_ranking_productos_por_region_permite_facturacion_y_valida_parametros():
    por_facturacion = ranking_productos_por_region(top_n=1, metrica="total")
    for ranking in por_facturacion["ranking_por_region"].values():
        assert len(ranking) == 1
    assert "error" in ranking_productos_por_region(top_n=False)
    assert "error" in ranking_productos_por_region(metrica="margen")


def test_rankings_por_region_filtran_periodo_y_coinciden_con_datos_fuente():
    vendedores = ranking_vendedores_por_region(top_n=1, mes_desde="2024-09", mes_hasta="2024-09")
    productos = ranking_productos_por_region(top_n=1, mes_desde="2024-09", mes_hasta="2024-09")
    assert vendedores["periodo"] == "2024-09 a 2024-09"
    assert productos["periodo"] == "2024-09 a 2024-09"

    df = pd.read_csv(DATA_PATH)
    df["mes"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m")
    septiembre = df[df["mes"] == "2024-09"]
    for region in vendedores["ranking_por_region"]:
        vendedor_esperado = (
            septiembre[septiembre["region"] == region]
            .groupby("vendedor", as_index=False)["total"].sum()
            .sort_values(["total", "vendedor"], ascending=[False, True]).iloc[0]["vendedor"]
        )
        producto_esperado = (
            septiembre[septiembre["region"] == region]
            .groupby("producto", as_index=False)["cantidad"].sum()
            .sort_values(["cantidad", "producto"], ascending=[False, True]).iloc[0]["producto"]
        )
        assert vendedores["ranking_por_region"][region][0]["vendedor"] == vendedor_esperado
        assert productos["ranking_por_region"][region][0]["producto"] == producto_esperado


def test_rankings_por_region_validan_rango_temporal():
    assert "error" in ranking_vendedores_por_region(mes_desde="2024-09", mes_hasta=None)
    assert "error" in ranking_productos_por_region(mes_desde="septiembre", mes_hasta="2024-09")
    assert "error" in ranking_vendedores_por_region(mes_desde="2024-10", mes_hasta="2024-09")
    assert "error" in ranking_productos_por_region(mes_desde="2030-01", mes_hasta="2030-01")


def test_analisis_vendedores_y_productos_por_region_cruza_datos_del_mismo_periodo():
    resultado = analisis_vendedores_y_productos_por_region("2024-09", "2024-09")
    assert resultado["periodo"] == "2024-09 a 2024-09"
    assert resultado["top_vendedores"] == 1
    assert resultado["top_productos"] == 3

    df = pd.read_csv(DATA_PATH)
    septiembre = df[pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m") == "2024-09"]
    for region, detalle in resultado["analisis_por_region"].items():
        assert len(detalle) == 1
        vendedor = detalle[0]["vendedor"]
        esperado = (
            septiembre[septiembre["region"] == region]
            .groupby("vendedor", as_index=False)["total"].sum()
            .sort_values(["total", "vendedor"], ascending=[False, True]).iloc[0]["vendedor"]
        )
        assert vendedor == esperado
        producto_esperado = (
            septiembre[(septiembre["region"] == region) & (septiembre["vendedor"] == vendedor)]
            .groupby("producto", as_index=False)["cantidad"].sum()
            .sort_values(["cantidad", "producto"], ascending=[False, True]).iloc[0]["producto"]
        )
        assert detalle[0]["productos_top"][0]["producto"] == producto_esperado


def test_analisis_vendedores_y_productos_por_region_soporta_limites_y_metricas():
    resultado = analisis_vendedores_y_productos_por_region(
        "2024-09", "2024-09", top_vendedores=2, top_productos=1,
        metrica_vendedor="cantidad", metrica_producto="total",
    )
    assert resultado["metrica_vendedor"] == "cantidad"
    assert resultado["metrica_producto"] == "total"
    for detalle in resultado["analisis_por_region"].values():
        assert 1 <= len(detalle) <= 2
        assert all(len(vendedor["productos_top"]) == 1 for vendedor in detalle)


def test_analisis_vendedores_y_productos_por_region_valida_parametros():
    assert "error" in analisis_vendedores_y_productos_por_region("2024-09", "2024-09", top_vendedores=0)
    assert "error" in analisis_vendedores_y_productos_por_region("2024-09", "2024-09", top_productos=False)
    assert "error" in analisis_vendedores_y_productos_por_region("2024-09", "2024-09", metrica_vendedor="margen")
    assert "error" in analisis_vendedores_y_productos_por_region("2024-09", "2024-09", metrica_producto="margen")


# ── lista_productos ───────────────────────────────────────────────────────────

def test_lista_productos_estructura():
    resultado = lista_productos()
    assert "total_productos_distintos" in resultado
    assert "total_unidades_vendidas" in resultado
    assert "productos" in resultado

def test_lista_productos_tiene_productos():
    resultado = lista_productos()
    assert len(resultado["productos"]) > 0

def test_lista_productos_cada_item_tiene_campos():
    resultado = lista_productos()
    for p in resultado["productos"]:
        assert "nombre" in p
        assert "categoria" in p
        assert "unidades_vendidas" in p

def test_lista_productos_unidades_positivas():
    resultado = lista_productos()
    for p in resultado["productos"]:
        assert p["unidades_vendidas"] > 0


# ── producto_mas_vendido ──────────────────────────────────────────────────────

def test_producto_mas_vendido_estructura():
    resultado = producto_mas_vendido()
    assert "producto" in resultado
    assert "cantidad_total" in resultado

def test_producto_mas_vendido_cantidad_positiva():
    resultado = producto_mas_vendido()
    assert resultado["cantidad_total"] > 0

def test_producto_mas_vendido_es_el_mayor():
    top = producto_mas_vendido()
    todos = lista_productos()["productos"]
    for p in todos:
        assert top["cantidad_total"] >= p["unidades_vendidas"]


# ── resumen_general ───────────────────────────────────────────────────────────

def test_resumen_general_estructura():
    resultado = resumen_general()
    campos = ["total_ingresos", "total_transacciones", "ticket_promedio",
              "productos_distintos", "vendedores"]
    for campo in campos:
        assert campo in resultado, f"Falta campo: {campo}"

def test_resumen_general_valores_positivos():
    resultado = resumen_general()
    assert resultado["total_ingresos"] > 0
    assert resultado["total_transacciones"] > 0
    assert resultado["ticket_promedio"] > 0

def test_resumen_general_ticket_promedio_correcto():
    resultado = resumen_general()
    esperado = resultado["total_ingresos"] / resultado["total_transacciones"]
    assert abs(resultado["ticket_promedio"] - esperado) < 0.01
