from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase

from jobs.models import AnalysisJob, JobStatus


class JobCreateErrorShapeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="staff_upload",
            password="TestPass123!",
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.url = "/dashboard/api/v1/jobs/"

    def _build_payload(self):
        return {
            "period_month": "2026-04",
            "input_personal_asignado": SimpleUploadedFile(
                "personal.xlsx",
                b"dummy-pa",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            "input_servicio_vivo": SimpleUploadedFile(
                "servicio.xlsx",
                b"dummy-sv",
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        }

    def test_returns_json_error_shape_on_integrity_error(self):
        with patch("jobs.views.AnalysisJob.objects.create", side_effect=IntegrityError("boom")):
            response = self.client.post(self.url, self._build_payload())

        self.assertEqual(response.status_code, 500)
        self.assertIn("application/json", response["Content-Type"])
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "job_integrity_error")
        self.assertIn("message", data["error"])

    def test_returns_json_error_shape_on_queue_failure_and_marks_job_failed(self):
        with patch("jobs.views.run_analysis_job.delay", side_effect=RuntimeError("celery unavailable")):
            response = self.client.post(self.url, self._build_payload())

        self.assertEqual(response.status_code, 503)
        self.assertIn("application/json", response["Content-Type"])
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "job_queue_error")
        self.assertIn("message", data["error"])

        job = AnalysisJob.objects.order_by("-created_at").first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIn("No se pudo iniciar", job.error_message)
