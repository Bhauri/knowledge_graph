from app.chunk_sync.text_cleaner import clean_text


def test_clean_text_normalizes_spaces_and_trims() -> None:
    assert clean_text("  hello    world\n\tagain ") == "hello world again"


def test_clean_text_skips_none_and_empty() -> None:
    assert clean_text(None) is None
    assert clean_text("   ") is None
