from backend.rag.chunking import chunk_filing, chunk_section, count_tokens, split_sections


def _fake_filing() -> str:
    para = "The Company designs accelerated computing platforms. " * 40
    risk = "Customer concentration and supply constraints may impact revenue. " * 40
    mdna = "Revenue increased driven by data center demand. " * 40
    return (
        "TABLE OF CONTENTS\nItem 1. Business\nItem 1A. Risk Factors\nItem 7. MD&A\n\n"
        f"Item 1. Business\n{para}\n"
        f"Item 1A. Risk Factors\n{risk}\n"
        f"Item 7. Management's Discussion\n{mdna}\n"
    )


class TestSectionSplit:
    def test_detects_body_sections_not_toc(self):
        sections = split_sections(_fake_filing())
        items = [item for item, _, _ in sections]
        assert items == ["1", "1A", "7"]
        # bodies must be the real sections, not the one-line TOC entries
        assert all(len(body) > 500 for _, _, body in sections)

    def test_no_items_falls_back_to_full(self):
        sections = split_sections("Just some text without any structure. " * 50)
        assert len(sections) == 1
        assert sections[0][0] == "FULL"


class TestChunking:
    def test_windows_respect_token_budget(self):
        text = "word " * 5000
        chunks = chunk_section("1A", "Risk Factors", text, chunk_tokens=800, overlap_tokens=100)
        assert len(chunks) > 1
        assert all(count_tokens(c.content) <= 800 for c in chunks)

    def test_consecutive_chunks_overlap(self):
        text = " ".join(f"tok{i}" for i in range(3000))
        chunks = chunk_section("7", "MD&A", text, chunk_tokens=200, overlap_tokens=50)
        for a, b in zip(chunks, chunks[1:], strict=False):
            assert a.content[-20:] not in ("",)  # sanity
            # the start of chunk b must appear inside chunk a (the overlap)
            assert b.content[:30] in a.content

    def test_chunk_metadata(self):
        chunks = chunk_filing(_fake_filing())
        assert {c.item for c in chunks} == {"1", "1A", "7"}
        assert all(c.section_title for c in chunks)

    def test_max_chunks_bound(self):
        text = "Item 1. Business\n" + "filler words here " * 100_000
        chunks = chunk_filing(text, max_chunks=10)
        assert len(chunks) == 10
