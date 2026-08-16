"""Tests for the evidence model and store."""

import pytest
from app.models.evidence import Evidence, EvidenceStore


def test_add_assigns_sequential_ids():
    store = EvidenceStore()
    e1 = store.add(Evidence.new("transaction", description="a"))
    e2 = store.add(Evidence.new("block", description="b"))
    assert e1.id == "EVID-0001"
    assert e2.id == "EVID-0002"


def test_get_and_missing():
    store = EvidenceStore()
    e = store.add(Evidence.new("balance", description="x"))
    assert store.get(e.id) is e
    assert store.get("EVID-9999") is None


def test_unique_ids_per_store():
    store = EvidenceStore()
    a = EvidenceStore()
    e1 = store.add(Evidence.new("transfer", description="1"))
    e2 = a.add(Evidence.new("transfer", description="2"))
    assert e1.id == e2.id == "EVID-0001"  # ids are per-store


def test_resolve_all_or_raise():
    store = EvidenceStore()
    e = store.add(Evidence.new("contract", description="c"))
    assert store.resolve(["EVID-0001"])[0] is e
    with pytest.raises(ValueError):
        store.resolve(["EVID-0001", "EVID-0002"])


def test_validate_references():
    store = EvidenceStore()
    store.add(Evidence.new("transaction", description="t"))
    assert store.validate_references(["EVID-0001"]) == []
    assert store.validate_references(["EVID-0001", "MISSING"]) == ["MISSING"]


def test_add_many():
    store = EvidenceStore()
    out = store.add_many([Evidence.new("block", description="b"), Evidence.new("block", description="b2")])
    assert store.count() == 2
    assert out[1].id == "EVID-0002"


def test_to_records_json_safe():
    store = EvidenceStore()
    store.add(Evidence.new("transaction", description="t", transaction_hash="0xabc", block_number=42))
    records = store.to_records()
    assert records[0]["id"] == "EVID-0001"
    assert records[0]["transaction_hash"] == "0xabc"
    assert records[0]["block_number"] == 42


def test_unknown_evidence_type_rejected():
    with pytest.raises(ValueError):
        Evidence.new("made_up_type", description="nope")