"""Tests for infra/scripts/refresh_demos.py"""
from infra.scripts.refresh_demos import DEMO_CONFIGS, validate_snapshot


def test_demo_configs_defined():
    """Curated landing-page set — keep small. Bump when the list intentionally grows."""
    assert len(DEMO_CONFIGS) == 6
    slugs = [c["slug"] for c in DEMO_CONFIGS]
    assert len(slugs) == len(set(slugs)), f"Duplicate slugs: {slugs}"


def test_each_config_has_required_fields():
    """Each demo config must have all required fields."""
    required_fields = {"slug", "title", "description", "seed_summary", "goal", "tier"}
    for config in DEMO_CONFIGS:
        missing = required_fields - set(config.keys())
        assert not missing, f"Config '{config.get('slug')}' missing fields: {missing}"


def test_validate_snapshot_valid():
    """validate_snapshot returns True for a well-formed snapshot."""
    snapshot = {
        "slug": "test-demo",
        "report_markdown": "# Report\n\nSome content here.",
        "chat_log": [{"agent_name": "Agent_1", "action_type": "CREATE_POST", "round": 1}],
    }
    assert validate_snapshot(snapshot) is True


def test_validate_snapshot_missing_report():
    """validate_snapshot returns False when report_markdown is empty or missing."""
    snapshot_empty = {
        "slug": "test-demo",
        "report_markdown": "   ",
        "chat_log": [],
    }
    assert validate_snapshot(snapshot_empty) is False

    snapshot_missing = {
        "slug": "test-demo",
        "chat_log": [],
    }
    assert validate_snapshot(snapshot_missing) is False
