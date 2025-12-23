import requests
import re

pa = 'C:/Project_PAvsSV/data/11. Personal Asignado - Noviembre 2025 - (191125).xlsx'
sv = 'C:/Project_PAvsSV/data/SV Octubre 2025.xlsx'

with open(pa, 'rb') as f1, open(sv, 'rb') as f2:
    files = {'input_personal_asignado': f1, 'input_servicio_vivo': f2}
    r = requests.post('http://127.0.0.1:8001/api/v1/jobs/', files=files, data={'period_month': '2025-11'})

print('Status:', r.status_code)

if r.status_code == 202:
    print('Response:', r.json())
else:
    # Extraer exception_value del HTML
    match = re.search(r'<pre class="exception_value">(.*?)</pre>', r.text, re.DOTALL)
    if match:
        print('Error:', match.group(1)[:500])
    
    # Extraer traceback
    match2 = re.search(r'<textarea[^>]*id="traceback_area"[^>]*>(.*?)</textarea>', r.text, re.DOTALL)
    if match2:
        print('\nTraceback:')
        print(match2.group(1)[:2000])
