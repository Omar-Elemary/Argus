"""Input validation helpers used across tools and the API."""

from __future__ import annotations

import re

from web3 import Web3

_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


class ValidationError(ValueError):
    """Raised when an input is not a valid Ethereum value."""


def validate_eth_address(address: str) -> str:
    """Validate an Ethereum address and normalise to checksum form.

    Raises :class:`ValidationError` for anything that is not a valid
    address. Mixed-case addresses that fail EIP-55 checksum validation
    are also rejected (Web3's lenient ``is_address`` only checks the
    shape, so we layer the strict checksum check on top) to catch
    copy/paste errors.
    """
    if not isinstance(address, str) or not address:
        raise ValidationError("Address must be a non-empty string")
    if not Web3.is_address(address):
        raise ValidationError(f"{address!r} is not a valid Ethereum address")
    if address == address.lower():
        return Web3.to_checksum_address(address)
    if not Web3.is_checksum_address(address):
        raise ValidationError(f"{address!r} has mixed case but fails EIP-55 checksum")
    return Web3.to_checksum_address(address)


def validate_tx_hash(tx_hash: str) -> str:
    if not isinstance(tx_hash, str) or not tx_hash:
        raise ValidationError("Transaction hash must be a non-empty string")
    value = tx_hash.lower()
    if not _TX_HASH_RE.match(value):
        raise ValidationError(f"{tx_hash!r} is not a valid transaction hash")
    return value


def validate_block_number(block_number: int) -> int:
    if isinstance(block_number, bool) or not isinstance(block_number, int):
        raise ValidationError("Block number must be an integer")
    if block_number < 0:
        raise ValidationError("Block number cannot be negative")
    return block_number


def validate_count(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("Count must be an integer")
    if value <= 0:
        raise ValidationError("Count must be positive")
    return value