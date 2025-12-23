"""
Script principal para ejecutar la API de análisis Personal Asignado vs Servicio Vivo.

Ejecutar con:
    python main.py

O para desarrollo con recarga automática:
    python main.py --reload

O para producción con múltiples workers:
    python main.py --workers 4
"""

import argparse
import uvicorn


def main():
    """Ejecuta el servidor de la API."""
    parser = argparse.ArgumentParser(description="API de Análisis PA vs SV")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host para el servidor (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Puerto para el servidor (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Habilitar recarga automática (desarrollo)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Número de workers (producción)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 Iniciando API de Análisis PA vs SV")
    print("=" * 60)
    print(f"📡 Host: {args.host}")
    print(f"🔌 Puerto: {args.port}")
    print(f"🔄 Reload: {'✅ Activado' if args.reload else '❌ Desactivado'}")
    print(f"👷 Workers: {args.workers}")
    print("=" * 60)
    print(f"\n📚 Documentación: http://{args.host}:{args.port}/docs")
    print(f"🔍 Health Check: http://{args.host}:{args.port}/api/v1/health")
    print("\n⌨️  Presiona CTRL+C para detener el servidor\n")
    
    uvicorn.run(
        "api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1
    )


if __name__ == "__main__":
    main()
