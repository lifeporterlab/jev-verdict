from jev_verdict.cache import VerdictCache, cache_key, questions_fingerprint


def test_cache_latest_wins_and_question_change_invalidates(tmp_path):
    cache = VerdictCache(tmp_path / "cache.jsonl")
    questions = [{"id": "leak", "type": "noul", "instructions": "Is it private?", "criteria": {"true": "yes", "false": "no"}}]
    version = questions_fingerprint(questions)
    key = cache_key(" hello  world ", "privacy", version, "jev-latest")
    cache.put(key, question_version=version, model="jev-latest", value={"scores": {"leak": 0.2}})
    cache.put(key, question_version=version, model="jev-latest", value={"scores": {"leak": 0.8}})
    assert cache.get(key, question_version=version, model="jev-latest")["scores"]["leak"] == 0.8

    changed = [{**questions[0], "instructions": "Does it expose private data?"}]
    changed_version = questions_fingerprint(changed)
    changed_key = cache_key("hello world", "privacy", changed_version, "jev-latest")
    assert changed_version != version
    assert changed_key != key
    assert cache.get(changed_key, question_version=changed_version, model="jev-latest") is None


def test_prune_keeps_newest_record_per_key_and_preserves_lookups(tmp_path):
    cache = VerdictCache(tmp_path / "cache.jsonl")
    questions = [{"id": "leak", "type": "noul", "instructions": "Is it private?"}]
    version = questions_fingerprint(questions)
    key_a = cache_key("first subject", "privacy", version, "jev-latest")
    key_b = cache_key("second subject", "privacy", version, "jev-latest")
    cache.put(key_a, question_version=version, model="jev-latest", value={"scores": {"leak": 0.1}})
    cache.put(key_b, question_version=version, model="jev-latest", value={"scores": {"leak": 0.9}})
    cache.put(key_a, question_version=version, model="jev-latest", value={"scores": {"leak": 0.8}})
    assert cache.stats()["records"] == 3

    assert cache.prune() == {"before": 3, "after": 2, "removed": 1}
    assert cache.prune() == {"before": 2, "after": 2, "removed": 0}
    assert cache.get(key_a, question_version=version, model="jev-latest")["scores"]["leak"] == 0.8
    assert cache.get(key_b, question_version=version, model="jev-latest")["scores"]["leak"] == 0.9

    fresh = VerdictCache(tmp_path / "fresh.jsonl")
    assert fresh.prune() == {"before": 0, "after": 0, "removed": 0}
