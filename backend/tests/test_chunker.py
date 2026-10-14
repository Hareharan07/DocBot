from app.services.chunker import chunk_pages, split_text
from app.services.extractor import ExtractedPage


def test_short_text_is_one_chunk():
    assert split_text("hello world", 800, 150) == ["hello world"]


def test_chunks_respect_size_and_overlap():
    text = " ".join(f"word{i}" for i in range(600))
    chunks = split_text(text, 200, 40)
    assert len(chunks) > 3
    assert all(len(c) <= 200 for c in chunks)
    # consecutive chunks share some text (overlap)
    for a, b in zip(chunks, chunks[1:]):
        tail = a.split()[-2:]
        assert any(w in b.split()[:12] for w in tail)


def test_no_text_lost():
    text = " ".join(f"w{i}" for i in range(400))
    joined = " ".join(split_text(text, 120, 20))
    assert all(f"w{i}" in joined for i in range(400))


def test_prefers_paragraph_boundaries():
    text = ("A" * 150 + "\n\n") + ("B" * 150 + "\n\n") + ("C" * 150)
    chunks = split_text(text, 320, 0)
    assert chunks[0].startswith("A") and "B" in chunks[0]


def test_unbroken_text_is_hard_split():
    chunks = split_text("x" * 1000, 300, 50)
    assert all(len(c) <= 300 for c in chunks) and len(chunks) >= 4


def test_page_metadata_and_running_index():
    pages = [ExtractedPage(1, "alpha " * 200), ExtractedPage(2, "beta " * 200)]
    chunks = chunk_pages(pages, 300, 50)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert {c.page for c in chunks} == {1, 2}
    assert all("beta" not in c.text for c in chunks if c.page == 1)
