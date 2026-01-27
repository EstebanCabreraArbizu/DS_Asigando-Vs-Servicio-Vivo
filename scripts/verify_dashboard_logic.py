
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pavssv_server.settings')
django.setup()

from django.contrib.auth import get_user_model
from tenants.models import Tenant, Membership
from jobs.models import AnalysisJob, JobStatus, AnalysisSnapshot
from dashboard.views import get_tenant_for_user

User = get_user_model()
user = User.objects.get(username="Jose_Luis")

print(f"Testing for user: {user.username}")
tenant = get_tenant_for_user(user)
print(f"Resolved tenant: {tenant.slug if tenant else 'None'}")

if tenant:
    # Simular PeriodsAPIView logica
    snapshots = AnalysisSnapshot.objects.filter(tenant=tenant).order_by("-period_month")
    print(f"Snapshots count for {tenant.slug}: {snapshots.count()}")
    
    jobs = AnalysisJob.objects.filter(tenant=tenant, status=JobStatus.SUCCEEDED).order_by("-created_at")
    print(f"Succeeded jobs count for {tenant.slug}: {jobs.count()}")
    
    if jobs.exists():
        for job in jobs:
            print(f" - Job ID: {job.id}, Period: {job.period_month}")
else:
    print("ERROR: Could not resolve tenant for user.")
