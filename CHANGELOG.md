# Changelog

Todos los cambios relevantes del proyecto se documentan en este archivo.

## 2026-04-10

### Fixed
- Se corrigio la autorizacion de eliminacion para el rol `coordinator` en API y capa de dominio.
- Se resolvio el error `403` al eliminar analisis desde Upload cuando la causa era CSRF faltante.
- Se elimino la dependencia de script inline (bloqueado por CSP) para inyeccion de CSRF.

### Changed
- Upload ahora carga scripts desde `dashboard/src` y aplica cache busting por timestamp para evitar assets obsoletos.
- Se agrego una capa defensiva de fetch CSRF global en `server/dashboard/static/dashboard/src/csrf-fetch.js`.
- Se actualizo `server/dashboard/static/dashboard/src/upload.js` para enviar `X-CSRFToken` de forma explicita en metodos inseguros.

### Deployment / Operacion
- Se valido el flujo recomendado de despliegue para frontend estatico: `collectstatic` y reinicio de web.
- Se publico en remoto el commit de hardening CSRF/cache en `main`.

### Commits Relacionados
- `77e3e64` - Permiso de eliminacion para coordinator.
- `3319604` - Limpieza e integracion de cambios previos en rama principal.
- `6455eab` - Hardening CSRF y mitigacion de cache estatico en Upload.
