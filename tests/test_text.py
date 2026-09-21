from jev_verdict.text import normalize_text, split_sentences


def test_normalize_text_collapses_whitespace_and_normalizes_unicode():
    assert normalize_text("  안녕\r\n  하세요  ") == "안녕 하세요"
    assert normalize_text("e\u0301") == "é"


def test_split_sentences_handles_korean_punctuation_and_newlines():
    assert split_sentences("첫 문장입니다. 둘째인가요? 네!\n마지막") == [
        "첫 문장입니다.", "둘째인가요?", "네!", "마지막"
    ]
    assert split_sentences("   ") == []
