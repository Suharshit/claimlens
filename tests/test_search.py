"""Tests for the Policy Retrieval search tools (M3): policy filter, scores, threshold, topic queries."""

from __future__ import annotations

import pytest

from tools.config import load_config
from tools.retrieval_tools import (
    get_policy_limits,
    search_irdai_rules,
    search_policy_clauses,
    tokenize,
)

MIN = load_config()["retrieval"]["min_similarity"]


def ids(hits):
    return [h["clause_id"] for h in hits]


def test_tokenize_drops_stop_words_and_folds_plurals():
    assert tokenize("Charges for the Rooms, per day!") == ["charge", "room", "day"]
    assert tokenize("expenses illness") == ["expense", "illness"]


# The queries the Policy Retrieval Agent asks for each limit it needs, and the clause each must find.
TOPICS = [
    ("room rent boarding nursing expenses per day limit", "ASJ-01:4.1.i"),
    ("intensive care unit ICU expenses per day limit", "ASJ-01:4.1.ii"),
    ("rates exceeding limits proportion other expenses", "ASJ-01:4.1.1.note2"),
    ("co-payment admissible claim", "ASJ-01:9.3"),
    ("first thirty days waiting period illness", "ASJ-01:6.2.i"),
    ("specific waiting period inguinal hernia", "ASJ-01:6.3.i"),
    ("joint replacement waiting period", "ASJ-01:6.3.ii"),
    ("cataract treatment limit", "ASJ-01:4.3"),
    ("pre-existing disease waiting period", "ASJ-01:6.1"),
]


@pytest.mark.parametrize("query,clause_id", TOPICS)
def test_topic_queries_find_their_clause(query, clause_id):
    assert clause_id in ids(search_policy_clauses("ASJ-01", query))


@pytest.mark.parametrize("query,clause_id", TOPICS[:4])
def test_limit_clauses_rank_first(query, clause_id):
    assert ids(search_policy_clauses("ASJ-01", query))[0] == clause_id


def test_hits_carry_text_score_and_page():
    (hit, *_) = search_policy_clauses("ASJ-01", "co-payment admissible claim")
    assert hit["clause_id"] == "ASJ-01:9.3" and "5%" in hit["text"] and hit["page"] == 13
    assert 0 < hit["score"] <= 1


def test_every_hit_clears_the_threshold_and_k_is_respected():
    hits = search_policy_clauses("ASJ-01", "waiting period", k=3)
    assert len(hits) <= 3
    assert all(h["score"] >= MIN for h in hits)


def test_results_are_filtered_by_policy():
    assert all(h["clause_id"].startswith("ASJ-01:") for h in search_policy_clauses("ASJ-01", "gloves mask"))


def test_policy_without_wording_finds_nothing_scenario_6():
    assert search_policy_clauses("GHC-01", "room rent boarding nursing expenses per day limit") == []


def test_unrelated_query_finds_nothing():
    assert search_policy_clauses("ASJ-01", "zebra xylophone") == []
    assert search_policy_clauses("ASJ-01", "the of and") == []        # only stop words


def test_irdai_lists_are_searched_separately():
    assert ids(search_irdai_rules("items for which coverage is not available"))[0] == "IRDAI:List-I"
    assert ids(search_irdai_rules("gloves mask laundry charges"))[0] == "IRDAI:List-I"
    with pytest.raises(ValueError):
        search_policy_clauses("IRDAI", "gloves")


def test_get_policy_limits():
    assert get_policy_limits("ASJ-01")["room_cap_per_day"] == 5000
    with pytest.raises(KeyError):
        get_policy_limits("XYZ-99")
