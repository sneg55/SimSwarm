"""Tests for saas.models.__init__ lazy __getattr__."""
import pytest


def test_lazy_import_simulation_job():
    import saas.models as m
    assert m.SimulationJob is not None


def test_lazy_import_job_status():
    import saas.models as m
    assert m.JobStatus is not None


def test_lazy_import_model_routing():
    import saas.models as m
    assert m.ModelRouting is not None


def test_lazy_import_error_event():
    import saas.models as m
    assert m.ErrorEvent is not None


def test_lazy_import_credit_entry():
    import saas.models as m
    assert m.CreditEntry is not None


def test_lazy_import_credit_pack():
    import saas.models as m
    assert m.CreditPack is not None


def test_lazy_import_user():
    import saas.models as m
    assert m.User is not None


def test_unknown_attribute_raises():
    import saas.models as m
    with pytest.raises(AttributeError):
        _ = m.SomethingUnknown
