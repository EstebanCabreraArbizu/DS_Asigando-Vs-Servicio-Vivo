from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from jobs.models import AnalysisJob, AnalysisSnapshot, JobStatus
from tenants.models import Membership, MembershipRole, Tenant


class DashboardJobScopedRegressionTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.user = user_model.objects.create_user(
			username="dashboard_user",
			password="TestPass123!",
		)
		self.tenant = Tenant.objects.create(name="Tenant QA", slug="tenant-qa")
		Membership.objects.create(
			user=self.user,
			tenant=self.tenant,
			role=MembershipRole.ADMIN,
			is_default=True,
		)
		self.client.force_login(self.user)

	def _create_job(self, *, period_month: date, status: str, suffix: str) -> AnalysisJob:
		return AnalysisJob.objects.create(
			tenant=self.tenant,
			period_month=period_month,
			status=status,
			source="dashboard_upload",
			input_personal_asignado=SimpleUploadedFile(
				f"pa-{suffix}.xlsx",
				b"pa",
				content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
			),
			input_servicio_vivo=SimpleUploadedFile(
				f"sv-{suffix}.xlsx",
				b"sv",
				content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
			),
			created_by=self.user,
		)

	def test_periods_api_returns_job_options_and_selects_first_succeeded_job(self):
		period = date(2026, 4, 1)
		succeeded_job = self._create_job(period_month=period, status=JobStatus.SUCCEEDED, suffix="ok")
		queued_job = self._create_job(period_month=period, status=JobStatus.QUEUED, suffix="queued")

		response = self.client.get("/dashboard/api/periods/")

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertIn("periods", data)
		self.assertEqual(len(data["periods"]), 1)

		period_entry = data["periods"][0]
		self.assertEqual(period_entry["value"], "2026-04")
		self.assertEqual(period_entry["job_id"], str(succeeded_job.id))
		self.assertEqual(len(period_entry["jobs"]), 2)

		jobs_by_id = {item["id"]: item for item in period_entry["jobs"]}
		self.assertFalse(jobs_by_id[str(queued_job.id)]["can_export"])
		self.assertTrue(jobs_by_id[str(succeeded_job.id)]["can_export"])

	def test_metrics_api_returns_zero_shape_for_not_ready_job(self):
		queued_job = self._create_job(
			period_month=date(2026, 5, 1),
			status=JobStatus.QUEUED,
			suffix="not-ready",
		)

		response = self.client.get(f"/dashboard/api/metrics/?job_id={queued_job.id}")

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["job_id"], str(queued_job.id))
		self.assertEqual(data["job_status"], JobStatus.QUEUED)
		self.assertIn("error", data)
		self.assertEqual(data["kpis"]["total_personal_asignado"], 0)
		self.assertEqual(data["kpis"]["total_servicio_vivo"], 0)
		self.assertEqual(data["charts"], {})
		self.assertEqual(data["filtros_disponibles"], {})

	def test_metrics_api_resolves_selected_job_and_period(self):
		succeeded_job = self._create_job(
			period_month=date(2026, 6, 1),
			status=JobStatus.SUCCEEDED,
			suffix="snapshot",
		)

		AnalysisSnapshot.objects.create(
			tenant=self.tenant,
			job=succeeded_job,
			period_month=date(2026, 6, 1),
			metrics={
				"total_personal_asignado": 10,
				"total_servicio_vivo": 8,
				"coincidencias": 7,
				"diferencia_total": 2,
				"cobertura_porcentaje": 125,
				"cobertura_diferencial": 25,
				"total_servicios": 2,
				"by_estado": [],
				"by_zona": [],
				"by_macrozona": [],
				"by_cliente_top10": [],
				"by_unidad_top10": [],
				"by_servicio_top10": [],
				"by_grupo": [],
				"filtros_disponibles": {"macrozona": ["M1"]},
			},
		)

		response = self.client.get(f"/dashboard/api/metrics/?job_id={succeeded_job.id}")

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertNotIn("error", data)
		self.assertEqual(data["job_id"], str(succeeded_job.id))
		self.assertEqual(data["job_status"], JobStatus.SUCCEEDED)
		self.assertEqual(data["period"], "2026-06")
		self.assertEqual(data["kpis"]["total_personal_asignado"], 10)
		self.assertEqual(data["kpis"]["total_servicio_vivo"], 8)
		self.assertIn("filtros_disponibles", data)

