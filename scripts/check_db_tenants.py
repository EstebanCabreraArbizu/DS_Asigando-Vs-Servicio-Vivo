
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pavssv_server.settings')
django.setup()

from tenants.models import Tenant, Membership
from jobs.models import AnalysisJob, JobStatus

print("--- Tenants ---")
for t in Tenant.objects.all():
    print(f"Tenant: {t.name} (Slug: {t.slug}, ID: {t.id})")

print("\n--- Memberships ---")
for m in Membership.objects.all():
    print(f"User: {m.user.username}, Tenant: {m.tenant.slug}, Role: {m.role}, Is Default: {m.is_default}")

print("\n--- Recent Jobs ---")
for j in AnalysisJob.objects.all().order_by('-created_at')[:5]:
    print(f"Job ID: {j.id}, Tenant: {j.tenant.slug}, Status: {j.status}, Created at: {j.created_at}")

print("\n--- Succeeded Jobs count ---")
print(AnalysisJob.objects.filter(status=JobStatus.SUCCEEDED).count())
