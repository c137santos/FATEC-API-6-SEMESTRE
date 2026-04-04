import pytest
from pydantic import ValidationError

from backend.schemas import DownloadRequest


def test_url_valida():
    req = DownloadRequest(url='https://example.com/file.zip')
    assert str(req.url) == 'https://example.com/file.zip'


def test_url_invalida_lanca_erro():
    with pytest.raises(ValidationError):
        DownloadRequest(url='nao-e-url')


def test_campo_obrigatorio():
    with pytest.raises(ValidationError):
        DownloadRequest()
