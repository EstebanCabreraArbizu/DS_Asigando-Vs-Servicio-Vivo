# -*- coding: utf-8 -*-
"""
Test minimo para identificar fuente de no-determinismo
"""
import polars as pl
import tempfile
from pathlib import Path

# Test 1: Leer mismo archivo Excel dos veces
print("TEST 1: Lectura de Excel")
print("-" * 40)

pa_file = "11. Personal Asignado - Noviembre 2025 - (191125).xlsx"

df1 = pl.read_excel(pa_file, sheet_name="ASIGNADO", engine="calamine")
df2 = pl.read_excel(pa_file, sheet_name="ASIGNADO", engine="calamine")

print(f"Filas df1: {len(df1)}, Filas df2: {len(df2)}")

# Comparar primeras 5 filas
cols = df1.columns[:3]
print(f"\nPrimeras 3 filas de columnas {cols}:")
print("df1:", df1.select(cols).head(3).to_dicts())
print("df2:", df2.select(cols).head(3).to_dicts())

if df1.equals(df2):
    print("\n[OK] Lecturas de Excel son IDENTICAS")
else:
    print("\n[ERROR] Lecturas de Excel son DIFERENTES!")
    
# Test 2: Group by determinism
print("\n\nTEST 2: Group By Determinism")
print("-" * 40)

# Crear datos simples
data = pl.DataFrame({
    "key": ["A", "B", "A", "C", "B", "A"],
    "value": [1, 2, 3, 4, 5, 6]
})

# Group by sin maintain_order
g1 = data.group_by("key").agg(pl.col("value").sum())
g2 = data.group_by("key").agg(pl.col("value").sum())

print("Sin maintain_order:")
print("g1:", g1.to_dicts())
print("g2:", g2.to_dicts())

if g1.equals(g2):
    print("[OK] Group by sin maintain_order es determinístico")
else:
    print("[ERROR] Group by sin maintain_order NO es determinístico")

# Group by con maintain_order
g3 = data.group_by("key", maintain_order=True).agg(pl.col("value").sum())
g4 = data.group_by("key", maintain_order=True).agg(pl.col("value").sum())

print("\nCon maintain_order=True:")
print("g3:", g3.to_dicts())
print("g4:", g4.to_dicts())

if g3.equals(g4):
    print("[OK] Group by con maintain_order es determinístico")
else:
    print("[ERROR] Group by con maintain_order NO es determinístico")

# Test 3: Join determinism
print("\n\nTEST 3: Join Determinism")
print("-" * 40)

left = pl.DataFrame({"key": ["A", "B", "C"], "val_l": [1, 2, 3]})
right = pl.DataFrame({"key": ["B", "C", "D"], "val_r": [20, 30, 40]})

j1 = left.join(right, on="key", how="full", coalesce=True)
j2 = left.join(right, on="key", how="full", coalesce=True)

print("Join 1:", j1.to_dicts())
print("Join 2:", j2.to_dicts())

if j1.equals(j2):
    print("[OK] Join full outer es determinístico")
else:
    print("[ERROR] Join full outer NO es determinístico")

print("\n\n" + "=" * 40)
print("RESUMEN DE TESTS COMPLETADO")
print("=" * 40)
