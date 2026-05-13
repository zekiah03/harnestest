"""Tests for the reputation tier system."""

import pytest

from favorgame.tiers import TIERS, status_for, tier_for, next_tier


class TestTierFor:
    @pytest.mark.parametrize(
        "points, expected_key",
        [
            (-200, "debt"),
            (-1, "debt"),
            (0, "newbie"),
            (5, "newbie"),
            (9, "newbie"),
            (10, "apprentice"),
            (49, "apprentice"),
            (50, "regular"),
            (199, "regular"),
            (200, "master"),
            (999, "master"),
            (1000, "sage"),
            (10_000, "sage"),
        ],
    )
    def test_boundaries(self, points, expected_key):
        assert tier_for(points).key == expected_key


class TestNextTier:
    def test_chain(self):
        assert next_tier(TIERS[0]).key == "newbie"
        assert next_tier(TIERS[1]).key == "apprentice"
        assert next_tier(TIERS[2]).key == "regular"
        assert next_tier(TIERS[3]).key == "master"
        assert next_tier(TIERS[4]).key == "sage"

    def test_top_has_no_next(self):
        assert next_tier(TIERS[-1]) is None


class TestStatusFor:
    def test_at_sage_max_no_progress_to_next(self):
        s = status_for(2000)
        assert s.tier.key == "sage"
        assert s.next is None
        assert s.points_to_next is None
        assert s.progress == 1.0

    def test_partway_through_master(self):
        # master band is 200..999. At 700, progress should be (700-200)/(1000-200) = 0.625
        s = status_for(700)
        assert s.tier.key == "master"
        assert s.next.key == "sage"
        assert s.points_to_next == 300
        assert abs(s.progress - 0.625) < 1e-6

    def test_just_entered_regular(self):
        s = status_for(50)
        assert s.tier.key == "regular"
        assert s.next.key == "master"
        assert s.points_to_next == 150
        assert s.progress == 0.0

    def test_about_to_promote_apprentice(self):
        # apprentice band is 10..49. At 49, very close to regular.
        s = status_for(49)
        assert s.tier.key == "apprentice"
        assert s.points_to_next == 1
        # (49-10)/(50-10) = 0.975
        assert abs(s.progress - 0.975) < 1e-6

    def test_in_debt_uses_soft_floor(self):
        # debt soft floor is -50. At -20, progress = (-20 - (-50)) / (0 - (-50)) = 0.6
        s = status_for(-20)
        assert s.tier.key == "debt"
        assert s.next.key == "newbie"
        assert s.points_to_next == 20
        assert abs(s.progress - 0.6) < 1e-6

    def test_deep_debt_clamps_progress_to_zero(self):
        s = status_for(-500)
        assert s.tier.key == "debt"
        assert s.progress == 0.0

    def test_zero_is_newbie_not_debt(self):
        s = status_for(0)
        assert s.tier.key == "newbie"

    def test_progress_never_exceeds_one(self):
        # Hand-constructed scenario: ensure clamping is in place.
        s = status_for(999)
        assert 0.0 <= s.progress <= 1.0

    def test_to_dict_serializes_cleanly(self):
        s = status_for(120)
        data = s.to_dict()
        assert data["tier"]["key"] == "regular"
        assert data["next"]["key"] == "master"
        assert data["points"] == 120
        assert isinstance(data["progress"], float)


class TestTiersConfiguration:
    def test_ranks_are_dense_and_sequential(self):
        assert [t.rank for t in TIERS] == list(range(len(TIERS)))

    def test_thresholds_strictly_ascending(self):
        thresholds = [t.threshold for t in TIERS]
        assert thresholds == sorted(thresholds)
        assert len(set(thresholds)) == len(thresholds)

    def test_each_tier_has_distinct_color(self):
        colors = [t.color for t in TIERS]
        assert len(set(colors)) == len(colors)
