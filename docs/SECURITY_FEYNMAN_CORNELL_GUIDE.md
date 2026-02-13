# 📚 Guía de Seguridad PA vs SV - Método Feynman + Notas Cornell

> **Objetivo:** Entender COMPLETAMENTE cada componente de seguridad implementado,
> de forma que puedas explicarlo a cualquier persona sin experiencia técnica.

---

# 🎯 TEMA 1: Content Security Policy (CSP)

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
│  (Columna Izq.)    │                    (Columna Der.)                       │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Qué es CSP?       │ CSP = Content Security Policy                           │
│                    │ Es una "lista de permisos" que le dice al navegador:    │
│                    │ - ¿De dónde puede cargar scripts?                       │
│                    │ - ¿De dónde puede cargar estilos CSS?                   │
│                    │ - ¿De dónde puede cargar imágenes?                      │
│                    │                                                         │
│ ¿Por qué importa?  │ Previene ataques XSS (Cross-Site Scripting)             │
│                    │ Un atacante NO puede inyectar código malicioso porque   │
│                    │ el navegador RECHAZA scripts de fuentes no autorizadas  │
│                    │                                                         │
│ ¿Dónde se          │ Archivo: settings.py (líneas 290-310)                   │
│ configura?         │ Middleware: SecurityHeadersMiddleware                    │
│                    │                                                         │
│ ¿Cómo funciona?    │ El servidor envía un HEADER con cada respuesta HTTP:    │
│                    │ "Content-Security-Policy: default-src 'self'..."        │
│                    │ El navegador LEE este header y BLOQUEA recursos         │
│                    │ que no cumplan las reglas                               │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN (escrito DESPUÉS de estudiar):                                    │
│                                                                              │
│ CSP es como un guardia de seguridad en la puerta del navegador. Antes de     │
│ dejar entrar cualquier script, imagen o estilo, el guardia revisa una lista  │
│ de "invitados permitidos". Si el recurso no está en la lista, no entra.      │
│ Esto evita que atacantes inyecten código malicioso incluso si logran         │
│ modificar el HTML de la página.                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN (Como si fueras programador junior)

**Imagina que tu página web es una fiesta de cumpleaños.**

En una fiesta normal, cualquiera puede entrar y traer música. Pero si alguien malo trae música con virus, tu computadora se enferma.

**CSP es como tener un papá en la puerta que revisa una lista:**

```
Lista de invitados permitidos:
✅ Música de: tu propia casa ('self')
✅ Imágenes de: tu casa y de internet (https:)
✅ Letras de: Google Fonts
❌ Todo lo demás: NO PUEDE ENTRAR
```

**¿Qué pasa si un hacker intenta meter código malo?**

```
Hacker: "¡Hola! Traigo un script de hackersmalvados.com"
CSP (el papá): *revisa la lista* "No estás en la lista. NO ENTRAS."
Navegador: Rechaza el script. Tu web está segura. 🎉
```

### 📍 Ubicación en el código:

```python
# Archivo: server/pavssv_server/settings.py

CSP_DEFAULT_SRC = ("'self'",)        # Por defecto, solo tu servidor
CSP_SCRIPT_SRC = ("'self'",)         # Scripts solo de tu servidor
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")  # Estilos de tu servidor
CSP_IMG_SRC = ("'self'", "data:", "https:")    # Imágenes locales y HTTPS
CSP_FRAME_ANCESTORS = ("'none'",)    # Nadie puede "enmarcar" tu web
```

---

# 🎯 TEMA 2: Rate Limiting (Limitación de Velocidad)

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Qué es Rate       │ Es un LÍMITE de cuántas veces puedes hacer algo en      │
│ Limiting?          │ un periodo de tiempo.                                   │
│                    │                                                         │
│ ¿Por qué lo        │ Previene:                                               │
│ necesitamos?       │ 1. Ataques de fuerza bruta (probar mil contraseñas)     │
│                    │ 2. Ataques DDoS (saturar el servidor)                   │
│                    │ 3. Abuso de la API (scraping masivo)                    │
│                    │                                                         │
│ ¿Cuáles son los    │ TRES NIVELES DE PROTECCIÓN:                             │
│ límites?           │                                                         │
│                    │ 1. LOGIN: 5 intentos por minuto                         │
│                    │    - Si fallas 5 veces → bloqueado 30 minutos            │
│                    │    - django-axes: lockout por user+IP                    │
│                    │    - CAPTCHA matemático después de 3 intentos             │
│                    │                                                         │
│                    │ 2. UPLOAD: 20 archivos por minuto                       │
│                    │    - Previene spam de archivos                          │
│                    │                                                         │
│                    │ 3. API GENERAL: 200 requests por minuto                 │
│                    │    - Uso normal permitido, abuso bloqueado              │
│                    │                                                         │
│ ¿Qué pasa si       │ HTTP 429: "Too Many Requests"                           │
│ excedo el límite?  │ El servidor responde con un error y NO procesa más      │
│                    │ requests hasta que pase el tiempo de bloqueo            │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ Rate limiting es como un cajero automático que solo te deja sacar dinero     │
│ 3 veces al día. Si intentas más, te dice "vuelve mañana". Esto evita que     │
│ un ladrón intente mil combinaciones de PIN o que vacíes la cuenta de         │
│ alguien rápidamente.                                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN

**Imagina que tienes una tienda de galletas.**

Sin rate limiting, un robot malvado puede:
1. Intentar adivinar tu contraseña 1 millón de veces por segundo
2. Eventualmente, ¡la adivina! 😱

**Con rate limiting, es como tener un guardia que cuenta:**

```
Robot: "¡Quiero entrar! Contraseña: 12345"
Guardia: "Incorrecto. Intento 1 de 5."

Robot: "Contraseña: password"
Guardia: "Incorrecto. Intento 2 de 5."

[...3 intentos más...]

Robot: "Contraseña: qwerty"
Guardia: "¡BLOQUEADO! Has gastado tus 5 intentos."
        "Vuelve en 30 minutos. 🚫"
        "Además, ahora necesitas resolver un CAPTCHA matemático 🧩"

Robot: 😡 (tendría que esperar AÑOS para probar todas las contraseñas)
```

### 📍 Ubicación en el código:

```python
# Archivo: server/pavssv_server/middleware.py

class IPRateLimitMiddleware:
    RATE_LIMITS = {
        "auth": {
            "requests": 5,      # Solo 5 intentos
            "window": 60,       # Por minuto (60 segundos)
            "block_time": 1800  # Si excede, bloqueado 30 minutos
        },
        "upload": {
            "requests": 20,
            "window": 60,
            "block_time": 180   # Bloqueado 3 minutos
        },
        "api": {
            "requests": 200,
            "window": 60,
            "block_time": 60    # Bloqueado 1 minuto
        }
    }

    # Endpoints de autenticación protegidos (incluye dashboard y admin)
    AUTH_PATTERNS = [
        "/api/v1/auth/login/",
        "/api/v1/auth/refresh/",
        "/dashboard/login/",
        # + login dinámico del admin según DJANGO_ADMIN_URL
    ]
```

---

# 🎯 TEMA 3: Validación de Archivos

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Por qué validar   │ Un archivo puede MENTIR sobre lo que es.                │
│ archivos?          │ "foto.jpg" podría ser en realidad "virus.exe"           │
│                    │                                                         │
│ ¿Qué validaciones  │ 5 CAPAS DE VALIDACIÓN:                                  │
│ hacemos?           │                                                         │
│                    │ 1. EXTENSIÓN: Solo .csv, .xlsx, .xls                    │
│                    │                                                         │
│                    │ 2. MAGIC BYTES: Los primeros bytes revelan el tipo      │
│                    │    real. XLSX siempre empieza con "PK" (es un ZIP)      │
│                    │                                                         │
│                    │ 3. TAMAÑO: Máximo 50 MB                                 │
│                    │                                                         │
│                    │ 4. NOMBRE: Sin caracteres peligrosos (../, <, >, etc.)  │
│                    │                                                         │
│                    │ 5. CONTENIDO: Buscar patrones maliciosos                │
│                    │    (<?php, <script>, eval(), etc.)                      │
│                    │                                                         │
│ ¿Qué son los       │ Son los primeros bytes de un archivo que identifican    │
│ "Magic Bytes"?     │ su tipo REAL, independiente del nombre.                 │
│                    │                                                         │
│                    │ Ejemplos:                                               │
│                    │ - XLSX: empieza con "PK\x03\x04" (es un ZIP)            │
│                    │ - XLS:  empieza con "\xd0\xcf\x11\xe0"                  │
│                    │ - PDF:  empieza con "%PDF"                              │
│                    │ - JPG:  empieza con "\xff\xd8\xff"                      │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ No confíes en la etiqueta del archivo. Es como revisar el contenido de       │
│ una caja, no solo leer lo que dice afuera. Un atacante puede renombrar       │
│ "virus.exe" a "documento.xlsx", pero los magic bytes revelan la verdad.      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN

**Imagina que trabajas en seguridad de aeropuerto.**

Alguien llega con una maleta que dice "ROPA" afuera.

**Sin validación:** "¡Ok, dice ROPA, pasa!" → 💣 ¡Era una bomba!

**Con validación (lo que hacemos):**

```
Paso 1: ¿Qué dice la etiqueta?
        → "archivo.xlsx" ✓ Extensión permitida

Paso 2: Abrir y ver los primeros bytes (rayos X)
        → "PK\x03\x04..." ✓ Es realmente un archivo XLSX

Paso 3: ¿Qué tan grande es?
        → 5 MB ✓ Menos de 50 MB

Paso 4: ¿El nombre tiene caracteres raros?
        → "archivo.xlsx" ✓ Sin "../" ni "<script>"

Paso 5: ¿El contenido tiene código malicioso?
        → Escanear... ✓ No hay "<?php" ni "eval()"

RESULTADO: ✅ ARCHIVO SEGURO - PUEDE PASAR
```

### 📍 Ubicación en el código:

```python
# Archivo: server/api_v1/validators.py

MAGIC_SIGNATURES = {
    ".xlsx": [b"PK\x03\x04"],  # XLSX es un ZIP
    ".xls": [b"\xd0\xcf\x11\xe0"],  # Formato binario antiguo
}

ALLOWED_EXTENSIONS = {
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}
```

---

# 🎯 TEMA 4: AWS WAF (Web Application Firewall)

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Qué es WAF?       │ WAF = Web Application Firewall                          │
│                    │ Es un "muro de fuego" específico para aplicaciones web  │
│                    │ Se coloca ANTES del servidor, filtrando tráfico malo    │
│                    │                                                         │
│ ¿Dónde está?       │ En AWS, ENTRE internet y tu aplicación:                 │
│                    │                                                         │
│                    │ [Internet] → [WAF] → [Load Balancer] → [Tu App]         │
│                    │                                                         │
│ ¿Qué reglas        │ 7 REGLAS CONFIGURADAS:                                  │
│ tenemos?           │                                                         │
│                    │ 1. Rate Limit Global: 2000 req/5min por IP              │
│                    │ 2. Rate Limit Login: 100 req/5min en /auth/login        │
│                    │ 3. Common Rules: Ataques comunes (OWASP)                │
│                    │ 4. SQLi Rules: Inyección SQL                            │
│                    │ 5. Bad Inputs: XSS, path traversal                      │
│                    │ 6. IP Reputation: IPs maliciosas conocidas              │
│                    │ 7. Size Limit: Bloquea requests > 50MB                  │
│                    │                                                         │
│ ¿Diferencia con    │ WAF está en AWS (ANTES del servidor)                    │
│ middleware local?  │ Middleware está en Django (DENTRO del servidor)         │
│                    │                                                         │
│                    │ Es DEFENSA EN PROFUNDIDAD: dos capas de protección      │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ WAF es como un guardia de seguridad EN LA CALLE, antes de llegar a tu        │
│ edificio. Filtra a los atacantes conocidos antes de que siquiera lleguen     │
│ a tocar tu puerta. Tu middleware es otro guardia DENTRO del edificio.        │
│ Si uno falla, el otro te protege.                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN

**Imagina tu aplicación como un castillo medieval.**

```
                    🏰 TU CASTILLO (Aplicación)
                           │
                    [Guardia Interior]  ← Middleware Django
                           │
                    ═══════════════════ Muralla
                           │
                    [Guardia Exterior]  ← AWS WAF
                           │
         ═══════════════════════════════════ Foso
                           │
                    🌍 Internet (atacantes + usuarios buenos)
```

**El WAF (guardia exterior) detiene:**
- Ejércitos de bots (rate limiting)
- Atacantes con armas conocidas (SQL injection, XSS)
- Personas en la "lista negra" (IP reputation)

**Si algo pasa el WAF, el middleware (guardia interior) revisa de nuevo.**

### 📍 Ubicación en el código:

```yaml
# Archivo: server/aws-security-infrastructure.yaml

WebACL:
  Type: AWS::WAFv2::WebACL
  Properties:
    Rules:
      - Name: RateLimitRule
        Statement:
          RateBasedStatement:
            Limit: 2000  # 2000 requests por 5 minutos
            
      - Name: AWSManagedRulesCommonRuleSet  # Reglas OWASP
      - Name: AWSManagedRulesSQLiRuleSet    # Anti SQL Injection
```

---

# 🎯 TEMA 5: Secrets Manager (Gestión de Secretos)

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Qué es un         │ Datos sensibles que NO deben estar en el código:        │
│ "secreto"?         │ - Contraseñas de base de datos                          │
│                    │ - API keys                                              │
│                    │ - Claves de encriptación (SECRET_KEY)                   │
│                    │ - Credenciales de servicios externos                    │
│                    │                                                         │
│ ¿Por qué NO        │ PELIGROS de secretos en código:                         │
│ ponerlos en el     │ 1. Si el código se sube a GitHub, TODOS lo ven          │
│ código?            │ 2. Cualquier desarrollador tiene acceso                 │
│                    │ 3. No se pueden rotar (cambiar) fácilmente              │
│                    │ 4. Quedan en el historial de Git PARA SIEMPRE           │
│                    │                                                         │
│ ¿Cómo funciona     │ AWS Secrets Manager:                                    │
│ Secrets Manager?   │ 1. Guardas secretos en AWS (encriptados)                │
│                    │ 2. Tu app pide el secreto por su nombre                 │
│                    │ 3. AWS verifica permisos (IAM)                          │
│                    │ 4. Si tiene permiso, devuelve el secreto                │
│                    │                                                         │
│ ¿Y en desarrollo?  │ En desarrollo local usamos .env (archivo local)         │
│                    │ El archivo .env está en .gitignore (no se sube)         │
│                    │ El código detecta si está en AWS o local                │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ Nunca escribas contraseñas en tu código. Es como escribir el PIN de tu       │
│ tarjeta en un Post-it pegado a la tarjeta. AWS Secrets Manager es como       │
│ una caja fuerte digital donde guardas tus secretos, y solo tu aplicación     │
│ (con la llave correcta) puede abrirla.                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN

**Imagina que tu contraseña del banco es "MiGato123".**

❌ **MAL:** Escribirla en un papel y pegarlo en la computadora
```python
# ¡NUNCA HAGAS ESTO!
DATABASE_PASSWORD = "MiGato123"
```

✅ **BIEN:** Guardarla en una caja fuerte
```python
# Así lo hacemos
from pavssv_server.secrets import get_secret
DATABASE_PASSWORD = get_secret("POSTGRES_PASSWORD")
```

**¿Cómo funciona la "caja fuerte" (AWS Secrets Manager)?**

```
Tu App: "¡Hola AWS! Soy la app PA vs SV. 
         Necesito el secreto 'POSTGRES_PASSWORD'"
         [Muestra credenciales IAM]

AWS:    "Déjame verificar... 
         ✓ Eres quien dices ser
         ✓ Tienes permiso para este secreto
         Aquí tienes: MiGato123"

Tu App: "¡Gracias!" [Usa la contraseña para conectar a la DB]
```

### 📍 Ubicación en el código:

```python
# Archivo: server/pavssv_server/secrets.py

def get_secret(secret_name: str, default = None):
    """Obtiene secreto de AWS o variable de entorno."""
    manager = get_secrets_manager()
    return manager.get_secret(secret_name, default)

# Uso en settings.py — SECRET_KEY ahora es OBLIGATORIA (sin valor por defecto)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY no está configurada.")
```

---

# 🎯 TEMA 6: Docker Seguro

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Por qué usuario   │ Si un atacante compromete la app, obtiene los permisos  │
│ no-root?           │ del usuario que la ejecuta.                             │
│                    │                                                         │
│                    │ - Con root: puede hacer CUALQUIER COSA en el sistema    │
│                    │ - Sin root: solo puede tocar archivos de la app         │
│                    │                                                         │
│ ¿Qué es multi-     │ Dockerfile en DOS FASES:                                │
│ stage build?       │                                                         │
│                    │ 1. BUILDER: Instala todo (compiladores, headers, etc.)  │
│                    │ 2. PRODUCTION: Solo copia lo necesario para ejecutar    │
│                    │                                                         │
│                    │ Resultado: Imagen más pequeña y sin herramientas que    │
│                    │ un atacante podría usar                                 │
│                    │                                                         │
│ ¿Por qué Gunicorn  │ `python manage.py runserver` es para DESARROLLO:        │
│ en producción?     │ - Un solo proceso                                       │
│                    │ - No maneja bien múltiples conexiones                   │
│                    │ - Tiene modo debug activo                               │
│                    │                                                         │
│                    │ Gunicorn es para PRODUCCIÓN:                            │
│                    │ - Múltiples workers                                     │
│                    │ - Maneja miles de conexiones                            │
│                    │ - Sin modo debug                                        │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ El Dockerfile de producción es como empacar para un viaje: llevas solo lo    │
│ necesario (multi-stage), no viajas como administrador del avión (no-root),   │
│ y usas un piloto profesional (Gunicorn) en lugar de un estudiante (runserver)│
└──────────────────────────────────────────────────────────────────────────────┘
```

### 📍 Ubicación en el código:

```dockerfile
# Archivo: server/Dockerfile

# Usuario no-root
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser appuser

# Cambiar al usuario seguro
USER appuser

# Gunicorn en producción
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "4", ...]
```

---

# 🎯 TEMA 7: Logging de Auditoría

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Qué es logging    │ Registro DETALLADO de quién hizo qué y cuándo.          │
│ de auditoría?      │ Como las cámaras de seguridad de un banco.              │
│                    │                                                         │
│ ¿Qué se registra?  │ EVENTOS CRÍTICOS:                                       │
│                    │ - Intentos de login (exitosos y fallidos)               │
│                    │ - Cambios de contraseña                                 │
│                    │ - Cambios de tenant                                     │
│                    │ - Errores de permisos (403)                             │
│                    │ - Errores del servidor (5xx)                            │
│                    │                                                         │
│ ¿Qué información   │ Por cada evento:                                        │
│ se guarda?         │ - Timestamp (fecha y hora exacta)                       │
│                    │ - IP del usuario                                        │
│                    │ - ID del usuario                                        │
│                    │ - Acción realizada                                      │
│                    │ - Resultado (éxito/fallo)                               │
│                    │ - Duración de la request                                │
│                    │                                                         │
│ ¿Dónde se guardan? │ 3 archivos de log separados:                            │
│                    │ - audit.log: Acciones de usuarios                       │
│                    │ - security.log: Eventos de seguridad                    │
│                    │ - error.log: Errores del sistema                        │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ Los logs de auditoría son como un diario detallado de todo lo que pasa en    │
│ tu aplicación. Si algo malo sucede, puedes "rebobinar la cinta" y ver        │
│ exactamente qué pasó, quién lo hizo y desde dónde.                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN

**Imagina que tu aplicación es un museo.**

Sin logging: Si alguien roba una pintura, no sabes quién fue.

Con logging: Tienes cámaras que registran TODO:

```
[2026-01-14 10:30:15] Usuario juan@empresa.com entró por la puerta principal
[2026-01-14 10:30:20] juan@empresa.com intentó acceder a la bóveda
[2026-01-14 10:30:21] ACCESO DENEGADO - juan no tiene permiso para la bóveda
[2026-01-14 10:31:00] juan@empresa.com salió del edificio
```

Si mañana desaparece algo, puedes revisar los logs y saber exactamente qué pasó.

---

# 🎯 DIAGRAMA COMPLETO DE SEGURIDAD

```
                          🌍 INTERNET
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AWS WAF                                 │
│  ┌─────────────┬─────────────┬─────────────┬──────────────┐ │
│  │ Rate Limit  │ SQL Inject. │ XSS Block   │ IP Blacklist │ │
│  └─────────────┴─────────────┴─────────────┴──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   LOAD BALANCER (ALB)                        │
│              [HTTPS only - TLS 1.2+]                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     DJANGO APP                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │               MIDDLEWARE STACK                        │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐ │   │
│  │  │ Sanitization│→│ Rate Limit  │→│ Security Headers│ │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘ │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐ │   │
│  │  │  Admin IP  │→│ Axes+CAPTCHA│→│ CSRF Protection │ │   │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘ │   │
│  │  ┌─────────────┐ ┌─────────────────────────────┐ │   │
│  │  │ Audit Log   │→│ Auth Check (LoginReqJSONMixin)│ │   │
│  │  └─────────────┘ └─────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 JWT AUTHENTICATION                    │   │
│  │         [Argon2 hashing, Token rotation]              │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  FILE VALIDATOR                       │   │
│  │    [Extension, Magic bytes, Size, Content scan]       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│   PostgreSQL     │ │  S3 Storage  │ │    Redis     │
│  [Encrypted]     │ │ [Encrypted]  │ │   [Cache]    │
└──────────────────┘ └──────────────┘ └──────────────┘
```

---

# 🎯 TEMA 8: Protección del Panel Admin y Anti Brute Force

## 📝 NOTAS CORNELL

```
┌────────────────────┬─────────────────────────────────────────────────────────┐
│  PREGUNTAS CLAVE   │                    NOTAS PRINCIPALES                    │
├────────────────────┼─────────────────────────────────────────────────────────┤
│                    │                                                         │
│ ¿Por qué ocultar   │ /admin/ es una ruta PREDECIBLE que los bots y           │
│ el admin?          │ atacantes buscan automáticamente. Si la encuentran:     │
│                    │ - Intentan fuerza bruta en el login                     │
│                    │ - Buscan vulnerabilidades en el panel                   │
│                    │ - Enumeran usuarios                                     │
│                    │                                                         │
│ ¿Qué capas de      │ 5 CAPAS DE PROTECCIÓN:                                  │
│ protección hay?    │                                                         │
│                    │ 1. URL personalizable (DJANGO_ADMIN_URL)               │
│                    │    → No es /admin/ sino /{nombre-secreto}/              │
│                    │                                                         │
│                    │ 2. AdminIPRestrictionMiddleware                         │
│                    │    → Solo IPs en ADMIN_ALLOWED_IPS pueden acceder       │
│                    │    → Retorna 404 (no 403) - no confirma existencia      │
│                    │                                                         │
│                    │ 3. django-axes: lockout tras 5 intentos (30 min)        │
│                    │    → Bloquea por combinación user+IP                    │
│                    │                                                         │
│                    │ 4. CAPTCHA matemático después de 3 intentos              │
│                    │    → Dificulta ataques automatizados                    │
│                    │                                                         │
│                    │ 5. Rate limiting en login del admin                      │
│                    │    → 5 req/min, bloqueo 30 minutos                      │
│                    │                                                         │
│ ¿Por qué 404 y     │ Si responder 403 ("Prohibido"), el atacante SABE que    │
│ no 403?            │ la ruta existe pero no tiene acceso.                    │
│                    │ Con 404 ("No encontrado"), el atacante piensa que       │
│                    │ la ruta NO EXISTE y se va a buscar otra.                │
│                    │                                                         │
│ ¿Qué es CAPTCHA    │ En lugar de letras difíciles de leer, usamos            │
│ matemático?        │ problemas como "3 + 7 = ?"                              │
│                    │ Más accesible para personas, difícil para bots.         │
│                    │                                                         │
├────────────────────┴─────────────────────────────────────────────────────────┤
│ 📌 RESUMEN:                                                                  │
│                                                                              │
│ El panel admin tiene 5 capas de protección, como un búnker militar:          │
│ URL secreta (puerta oculta), restricción IP (solo personas autorizadas),     │
│ lockout (cierre automático), CAPTCHA (prueba de humanidad), y rate           │
│ limiting (límite de velocidad). Si un atacante supera una capa, las         │
│ otras lo detienen.                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 🧠 EXPLICACIÓN FEYNMAN

**Imagina que tienes una caja fuerte secreta en tu casa.**

**Sin protección:** La caja fuerte está en la sala, visible para todos, y solo tiene una cerradura.

**Con protección (lo que hacemos):**

```
Capa 1: PUERTA OCULTA
        La caja fuerte está detrás de un cuadro secreto.
        → URL personalizada (no /admin/, sino /panel-gestion/)

Capa 2: GUARDIAS EN LA PUERTA
        Solo personas con credencial (IP autorizada) pueden pasar.
        → Si no tienes credencial: "¿Qué puerta? Aquí no hay nada." (404)

Capa 3: CERRADURA CON LÍMITE DE INTENTOS
        Después de 5 intentos fallidos, la caja se bloquea 30 minutos.
        → django-axes bloquea por user+IP

Capa 4: PRUEBA DE HUMANIDAD
        Después de 3 intentos: "¿Cuánto es 5 + 8? 🧩"
        → CAPTCHA matemático que los robots no pueden resolver

Capa 5: ALARMA SILENCIOSA
        Cada intento queda registrado con IP, hora y resultado.
        → Audit logging + django-axes failure log
```

### 📍 Ubicación en el código:

```python
# Archivo: server/pavssv_server/middleware.py

class AdminIPRestrictionMiddleware(MiddlewareMixin):
    """Solo permite acceso desde IPs en ADMIN_ALLOWED_IPS."""
    
    def process_request(self, request):
        if not request.path.startswith(self._admin_prefix):
            return None  # No es ruta admin, dejar pasar
        
        if not self._allowed_ips:
            return None  # Sin restricción en desarrollo
        
        client_ips = self._get_all_client_ips(request)
        if any(ip in self._allowed_ips for ip in client_ips):
            return None  # IP autorizada
        
        raise Http404()  # 404, NO 403

# Archivo: server/pavssv_server/settings.py

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
CAPTCHA_CHALLENGE_FUNCT = "captcha.helpers.math_challenge"
```

---

# 🧪 CONFIGURACIÓN DE TESTS DE SEGURIDAD

## Tests a Ejecutar por Función

| Función | Test de Seguridad | Test de Lógica |
|---------|-------------------|----------------|
| Login | Rate limiting, Brute force | Credenciales válidas/inválidas |
| Upload | File validation, Size limit | Formato correcto, procesamiento |
| Jobs API | SQL injection, XSS | CRUD operations, permisos |
| Export | Path traversal | Formato de exportación |
| Dashboard | CSRF, Clickjacking | Visualización de datos |

---

*Documento creado usando metodología Feynman + Notas Cornell*
*Fecha: Febrero 2026*
*Última actualización: 13 de febrero de 2026 — AdminIPRestrictionMiddleware, django-axes, CAPTCHA, __Host- cookies*
