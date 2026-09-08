from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repositories.interaction_repo import _derived_text_id, _rich_text_blocks


def test_rich_text_blocks_chunks_long_content():
    content = "x" * 4100
    blocks = _rich_text_blocks(content, max_chunk_size=1900)
    assert len(blocks) == 3
    assert "".join(block["text"]["content"] for block in blocks) == content
    assert all(len(block["text"]["content"]) <= 1900 for block in blocks)


def test_derived_text_id_reads_from_nested_conference_bundle():
    parsed = {
        "answer": {
            "session": {
                "text_id": "dalembertiennes_v1",
            }
        },
        "bundle": {
            "session": {
                "text_id": "dalembertiennes_v1",
            }
        },
    }
    assert _derived_text_id(parsed) == "dalembertiennes_v1"
