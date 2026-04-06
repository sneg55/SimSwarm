"""Tests for resume claim/release helpers."""
from unittest.mock import patch, MagicMock

from saas.jobs.persistence import _claim_resume, _release_resume


class TestClaimResume:
    """Verify atomic resume claiming via DB."""

    def test_claim_succeeds_when_unclaimed(self):
        """First claim on an unclaimed RUNNING job should return True."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (42,)
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
            result = _claim_resume(job_id=42, task_id="celery-task-abc")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_claim_fails_when_already_claimed(self):
        """Second claim on an already-claimed job should return False."""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None  # no row returned
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
            result = _claim_resume(job_id=42, task_id="celery-task-def")

        assert result is False

    def test_claim_fails_when_no_engine(self):
        """Claim returns False when DATABASE_URL is unset."""
        with patch("saas.jobs.persistence._get_sync_engine", return_value=None):
            result = _claim_resume(job_id=42, task_id="celery-task-ghi")

        assert result is False

    def test_release_clears_resume_task_id(self):
        """Release should NULL out resume_task_id."""
        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("saas.jobs.persistence._get_sync_engine", return_value=mock_engine):
            _release_resume(job_id=42)

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
