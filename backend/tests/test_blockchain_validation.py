"""Tests for Ethereum input validation."""

import pytest
from app.blockchain.validators import (
    ValidationError,
    validate_block_number,
    validate_eth_address,
    validate_tx_hash,
)

from tests.fakes import EIP55

VALID_TX = "0x" + "ab" * 32


def test_valid_address_returns_checksummed():
    assert validate_eth_address("0x0f52fd2320d48e4f2cbdf29196bdbaa65e0e1d04") == EIP55


def test_valid_checksummed_address_passes():
    assert validate_eth_address(EIP55) == EIP55


@pytest.mark.parametrize("bad", ["", "0x123", "not-an-address", "0x" + "g" * 40, None, 123])
def test_invalid_addresses_rejected(bad):
    with pytest.raises(ValidationError):
        validate_eth_address(bad)  # type: ignore[arg-type]


def test_mixed_case_wrong_checksum_rejected():
    wrong = "0x0f52fD2320D48e4f2cBdF29196BdBAa65e0E1D04"  # valid shape, broken checksum
    with pytest.raises(ValidationError):
        validate_eth_address(wrong)


def test_valid_tx_hash():
    assert validate_tx_hash(VALID_TX) == VALID_TX.lower()


@pytest.mark.parametrize("bad", ["", "0xabc", "0x" + "z" * 64, None, 42])
def test_invalid_tx_hashes_rejected(bad):
    with pytest.raises(ValidationError):
        validate_tx_hash(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [-1, "12", None, 1.5, True])
def test_invalid_block_numbers_rejected(bad):
    with pytest.raises(ValidationError):
        validate_block_number(bad)  # type: ignore[arg-type]


def test_valid_block_number():
    assert validate_block_number(12345) == 12345