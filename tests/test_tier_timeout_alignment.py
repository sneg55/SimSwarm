import inspect
from saas.workers.job_runner import TIER_TIMEOUTS, JobRunner


def test_small_tier_polling_within_timeout():
    timeout = TIER_TIMEOUTS["small"]
    assert timeout // 10 >= 270

def test_medium_tier_polling_within_timeout():
    timeout = TIER_TIMEOUTS["medium"]
    assert timeout // 10 >= 1800

def test_large_tier_polling_within_timeout():
    timeout = TIER_TIMEOUTS["large"]
    assert timeout // 10 >= 4320

def test_polling_not_hardcoded_to_one_hour():
    source = inspect.getsource(JobRunner._poll_until_complete)
    assert "max_polls = 360" not in source
