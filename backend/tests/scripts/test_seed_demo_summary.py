"""Tests for the demo seed command's success summary."""

from __future__ import annotations

from datetime import UTC, datetime

from app.scripts.seed_demo import SeedResult, format_seed_summary


def test_seed_summary_reports_checks_dataset_and_repeat_behavior() -> None:
    summary = format_seed_summary(
        SeedResult(
            seeded_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            users=1,
            entries=9,
            opportunity_cost_examples=3,
        )
    )

    assert "Demo seed completed successfully." in summary
    assert "local safety guards" in summary
    assert "migration heads match" in summary
    assert "committed in one transaction" in summary
    assert "Demo users: 1 (demo@penny-saved.local)" in summary
    assert "Demo password (local development only): PennySavedDemo!2026" in summary
    assert "Entries: 9" in summary
    assert "4 waiting: 2 still waiting and 2 eligible for check-in" in summary
    assert "4 saved" in summary
    assert "1 purchased" in summary
    assert "Opportunity-cost examples: 3" in summary
    assert "rerunning does not create duplicates" in summary
    assert "Manual and unrelated-user records were left unchanged" in summary
    assert "2026-07-24T12:00:00+00:00" in summary
    assert "Automated tests were not run by this command" in summary


def test_seed_summary_does_not_expose_hashes_or_database_credentials() -> None:
    summary = format_seed_summary(SeedResult(seeded_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC)))

    assert "postgresql+" not in summary
    assert "$argon2" not in summary
