# 📖 Manual de Usuario - PA vs SV

Bienvenido al manual de usuario del sistema de análisis **PA vs SV**. Este sistema te permitirá realizar cruces de información entre el Personal Asignado y el Servicio Vivo de forma automática.

---

## 🚀 Acceso al Sistema

1. Abre tu navegador web.
2. Ingresa a la URL del sistema (ej. `http://pavssv.liderman.com.pe` o `http://localhost:8001/dashboard/`).
3. Inicia sesión con tus credenciales de Liderman (si se solicita).

---

## 📥 Carga de Archivos (Upload)

Para generar un nuevo análisis, sigue estos pasos:

1. Dirígete a la sección de **Upload** en el menú lateral o superior.
2. Verás dos áreas de carga (Drag & Drop):
    - **Personal Asignado (PA)**: Arrastra el archivo Excel correspondiente a la nómina de personal.
    - **Servicio Vivo (SV)**: Arrastra el archivo Excel con la planificación de servicios.
3. **Selecciona el Período**: Elige el mes y año al que corresponden los datos.
4. Haz clic en el botón **"Procesar Archivos"**.
5. Espera a que la barra de progreso complete el 100%. El sistema te notificará cuando el procesamiento haya terminado.

---

## 📊 Exploración del Dashboard

Una vez procesados los datos, navega al **Dashboard** para ver los resultados:

- **Filtros**: Usa la barra superior para filtrar por Macro Zona, Zona, Compañía o Gerente. Los gráficos se actualizarán automáticamente.
- **Pestañas de Análisis**:
    - **Resumen**: Visión general con los KPIs más importantes (Cobertura, Diferencial, etc.).
    - **Por Cliente/Unidad**: Tablas detalladas para identificar desviaciones por cada cliente.
    - **Gráficos**: Visualizaciones de tendencias y distribuciones.
- **Estados del Personal**:
    - `SOBRECARGA`: Más horas en SV que en PA.
    - `FALTA`: Menos horas en SV que en PA.
    - `COINCIDE`: Las horas coinciden perfectamente.

---

## 📥 Exportación de Resultados

Si necesitas trabajar con los datos en Excel:

1. En cualquier sección del Dashboard, busca el botón **"📥 Excel"**.
2. Al hacer clic, el sistema generará un archivo con el cruce completo (Join) y lo descargará automáticamente a tu computadora.

---

## ❓ Preguntas Frecuentes

**¿Qué pasa si subo un archivo con columnas inválidas?**
> El sistema intentará normalizar los nombres comunes, pero si no encuentra las columnas críticas (como DNI o Fotocheck), mostrará un error. Asegúrate de usar los formatos estándar.

**¿Puedo ver historiales anteriores?**
> Sí, usa el selector de **Período** en el Dashboard para cargar datos de meses previamente procesados.

---
*Manual actualizado: 12 de Enero de 2026*
