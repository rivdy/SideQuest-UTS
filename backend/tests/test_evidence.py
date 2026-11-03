"""Protect scientific scope and source provenance in the literature draft."""

from pathlib import Path

import pytest

from app.chemistry.engine import screen
from app.chemistry.evidence import SOURCES, research_note
from app.chemistry.rules import RULES
from app.rag.store import Store, chunks


def test_sources_do_not_promote_rules_to_validated():
    assert len({s.id for s in SOURCES}) == 6
    assert all(r.status == "draft" for r in RULES)
    assert not any(r.id.startswith("R-") for r in RULES)
    assert all(s.limitation and s.access_level for s in SOURCES)
    assert all(s.review_status == "literature_draft" for s in SOURCES)


def test_alkene_has_both_reaction_and_matrix_evidence():
    result = screen("C=CC")
    evidence = result.matches[0].rule.evidence
    assert {s.id for s in evidence} == {"DOI:10.1039/C8RE00094H", "DOI:10.1002/ffj.3210"}
    assert result.risk_status == "not_assessed"
    assert result.validated_rule_count == 0


def test_ester_has_no_invented_stability_evidence():
    rule = screen("CC(=O)OC").matches[0].rule
    assert rule.evidence == ()
    assert rule.chemical_evidence == "belum ada sumber"


def test_hydrogen_peroxide_guidance_is_not_applied_to_organic_peroxide():
    result = screen("COOC")
    assert result.matches[0].rule.evidence == ()
    assert result.formulation_context[0].id == "EVONIK-H2O2-STABILITY"
    assert result.risk_status == "not_assessed"


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.id)
def test_retrieved_notes_preserve_limitations_in_one_chunk(source, tmp_path: Path):
    note = research_note(source)
    assert len(chunks(note)) == 1
    store = Store(tmp_path / "notes.sqlite3")
    first = store.add(source.title, source.id, [note])
    assert store.add(source.title, source.id, [note])["duplicate"]
    result = store.search("CATATAN LITERATUR", [first["id"]])
    assert result[0]["source_ref"] == source.id
    assert source.url in result[0]["text"]
    assert source.limitation in result[0]["text"]
    assert "bukan teks asli artikel" in result[0]["text"]
