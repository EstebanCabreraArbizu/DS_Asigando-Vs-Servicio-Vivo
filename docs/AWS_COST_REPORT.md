# 💰 Reporte de Costos Estimados en AWS

Este documento detalla una estimación mensual de costos para desplegar el sistema **PA vs SV** en una arquitectura de producción en AWS (Región: `us-east-1`, Virginia).

---

## 🏗️ Alternativas de Cómputo: ECS vs EC2

El sistema puede desplegarse de dos formas principales en AWS:

### Opción A: Amazon ECS (Fargate) - *Recomendado*
*   **Gestión**: Serverless (sin administración de servidores).
*   **Ventaja**: Escalabilidad automática y alta disponibilidad nativa. Ideal para separar el servidor Web de los Celery Workers.
*   **Perfil**: Para aplicaciones de producción que requieren estabilidad y bajo mantenimiento.

### Opción B: Amazon EC2 (Instancia Única)
*   **Gestión**: Manual (requiere configurar Docker y parches del SO).
*   **Ventaja**: Control total y potencialmente más económico para cargas pequeñas y constantes usando `docker-compose`.
*   **Perfil**: Para entornos de desarrollo o si se cuenta con un administrador de sistemas.

---

## 📊 Estimación Mensual (On-Demand)

| Servicio | Componente | Configuración | Costo Est. (USD) |
|----------|------------|---------------|------------------|
| **Compute (Fargate)** | Web + Worker | 2 tasks (0.5 vCPU, 1GB RAM) | ~$35.00 |
| **Database (RDS)** | PostgreSQL | db.t4g.micro (20GB SSD) | ~$25.00 |
| **Cache (ElastiCache)**| Redis | cache.t4g.micro | ~$12.00 |
| **Storage (S3)** | Archivos | 50GB Standard + 10k PUT/GET | ~$3.00 |
| **Networking** | ALB | 1 ALB + 10GB Data Transfer | ~$20.00 |
| **Total Estimado** | | | **~$95.00 / mes** |

---

## 💡 Estrategias de Optimización de Costos

### 1. AWS Free Tier
Si es una cuenta nueva, gran parte de estos costos pueden ser cubiertos por la capa gratuita durante los primeros 12 meses:
- **S3**: 5GB gratis.
- **RDS**: 750 horas de micro instancias.
- **EC2/Fargate**: Depende de la disponibilidad.

### 2. Instancias Reservadas o Savings Plans
Si se planea mantener el servicio activo por 1 a 3 años, se puede ahorrar hasta un **30-40%** mediante el compromiso de uso.

### 3. Escalado Automático
Configurar los Celery Workers para que se apaguen o reduzcan a 1 tarea durante horas no laborales para minimizar el consumo de Fargate.

### 4. Alternativa Económica (EC2 Single Instance)
Para un entorno de pruebas o bajo tráfico, se puede desplegar todo mediante `docker-compose` en una única instancia **EC2 t3.medium** (~$30/mes), aunque se pierde la alta disponibilidad y la gestión delegada de servicios.

---
> [!NOTE]
> Los precios son referenciales y pueden variar según el tráfico real y los cambios en las tarifas de AWS.
