import pytest
import json
from pathlib import Path


@pytest.fixture
def obs(tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import memory.observations as mod
    # Point to a temp DB for each test
    mod._DB_PATH = tmp_path / "observations.db"
    mod._conn = None  # force reconnect to new path
    return mod


def test_add_observation_stores_row(obs):
    obs_id = obs.add_observation(
        source="conversation",
        source_detail="chat on 2026-05-28",
        content="I've been reading Open by Andre Agassi and finding it really motivating.",
        relevance_hint="Learning",
    )
    assert isinstance(obs_id, int)
    assert obs_id > 0


def test_quality_filter_passes_good_observation(obs):
    good = {
        "content": "I've decided to stop playing Fortnite and focus on building Addis Market instead.",
        "source": "conversation",
    }
    assert obs.score_observation_quality(good) is True


def test_quality_filter_rejects_chitchat(obs):
    bad = {"content": "hey jarvis how are you doing", "source": "conversation"}
    assert obs.score_observation_quality(bad) is False


def test_quality_filter_rejects_too_short(obs):
    bad = {"content": "I like books", "source": "conversation"}
    assert obs.score_observation_quality(bad) is False


def test_quality_filter_rejects_general_knowledge(obs):
    bad = {
        "content": "The capital of Ethiopia is Addis Ababa which has a population "
                   "of about four million people and is the seat of the African Union.",
        "source": "conversation",
    }
    assert obs.score_observation_quality(bad) is False


def test_quality_filter_rejects_unknown_source(obs):
    bad = {
        "content": "I realized I work best late at night when everything is quiet.",
        "source": "unknown",
    }
    assert obs.score_observation_quality(bad) is False


def test_get_pending_observations_returns_quality_ones(obs):
    obs.add_observation("conversation", "chat", "I feel most productive after midnight when the house is quiet.", "Personal")
    obs.add_observation("conversation", "chat", "ok cool", "")
    pending = obs.get_pending_observations()
    assert len(pending) == 1
    assert "midnight" in pending[0]["content"]


def test_mark_synthesized_removes_from_pending(obs):
    oid = obs.add_observation("conversation", "chat",
        "I want to read more books about entrepreneurship this year.", "Learning")
    obs.mark_synthesized(oid)
    pending = obs.get_pending_observations()
    assert all(p["id"] != oid for p in pending)


def test_dedup_blocks_near_duplicate(obs):
    content = "I started reading Open by Andre Agassi and it is very motivating for me."
    obs.add_observation("conversation", "c", content, "Learning")
    obs.add_observation("conversation", "c", content, "Learning")
    pending = obs.get_pending_observations()
    assert len(pending) == 1


def test_suppress_topic_removes_from_pending(obs):
    obs.add_observation("conversation", "c",
        "I want to keep growing Addis Market vendor count this quarter.", "Addis Market")
    obs.suppress_topic("Addis Market")
    pending = obs.get_pending_observations()
    assert len(pending) == 0


def test_sensitivity_stored_in_observation(obs):
    obs.add_observation("email", "from Yostina", "My sister called and we discussed family plans.",
                        "Relationships", sensitivity="high")
    pending = obs.get_pending_observations(include_high_sensitivity=True)
    assert any(p["sensitivity"] == "high" for p in pending)
