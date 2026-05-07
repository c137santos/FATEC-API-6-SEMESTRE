import re


def normalize_cnpj(value: str) -> str:
    """Remove formatting from CNPJ and return a 14-digit string."""
    digits = re.sub(r'[.\-/]', '', value)
    if len(digits) != 14 or not digits.isdigit():
        raise ValueError(f'Invalid CNPJ after normalization: {value!r}')
    return digits
