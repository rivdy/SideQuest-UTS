"""Index original BAYLab research summaries; do not copy publisher full texts."""
from app.chemistry.evidence import SOURCES, research_note
from app.rag.api import get_store

if __name__ == "__main__":
    store = get_store()
    for source in SOURCES:
        result = store.add(
            "Catatan literatur draft - " + source.title,
            source.id,
            [research_note(source)],
        )
        print(f"{source.id}: chunks={result['chunks']}, duplicate={result['duplicate']}")
