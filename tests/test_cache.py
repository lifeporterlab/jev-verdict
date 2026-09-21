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
