# -*- coding: utf-8 -*-
"""Debug del error 500 en POST /jobs/"""
import requests
import os
import sys
import re

# Forzar UTF-8
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8001/api/v1"
PA_FILE = r"C:\Project_PAvsSV\data\11. Personal Asignado - Noviembre 2025 - (191125).xlsx"
SV_FILE = r"C:\Project_PAvsSV\data\SV Octubre 2025.xlsx"

print(f"PA existe: {os.path.exists(PA_FILE)}")
print(f"SV existe: {os.path.exists(SV_FILE)}")

with open(PA_FILE, "rb") as pa, open(SV_FILE, "rb") as sv:
    files = {
        "input_personal_asignado": ("pa.xlsx", pa, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "input_servicio_vivo": ("sv.xlsx", sv, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    data = {"period_month": "2025-11"}
    
    resp = requests.post(f"{BASE_URL}/jobs/", files=files, data=data)

print(f"Status: {resp.status_code}")

if resp.status_code != 202:
    text = resp.text
    # Buscar exception type y value
    exc_type = re.search(r'<th>Exception Type:</th>\s*<td>([^<]+)</td>', text)
    exc_value = re.search(r'<th>Exception Value:</th>\s*<td[^>]*>([^<]+)</td>', text, re.DOTALL)
    exc_location = re.search(r'<th>Exception Location:</th>\s*<td>([^<]+)</td>', text)
    
    if exc_type:
        print(f"\nException Type: {exc_type.group(1).strip()}")
    if exc_value:
        # Decodificar HTML entities
        val = exc_value.group(1).strip()
        val = val.replace('&#x27;', "'").replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
        print(f"Exception Value: {val}")
    if exc_location:
        print(f"Exception Location: {exc_location.group(1).strip()}")
    
    # Buscar el error específico en el traceback
    # El último error suele estar después de "The above exception was the direct cause"
    last_error = re.findall(r'(\w+Error[^\n]*)', text)
    if last_error:
        print(f"\nErrors encontrados:")
        for err in last_error[-5:]:
            err = err.replace('&#x27;', "'").replace('&quot;', '"')
            print(f"  - {err}")
else:
    print(f"Response: {resp.json()}")
