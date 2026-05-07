"""Tests for normalize_cnpj utility."""

import pytest

from backend.core.utils import normalize_cnpj


def test_cnpj_com_formatacao_completa():
    assert normalize_cnpj('76.535.764/0001-43') == '76535764000143'


def test_cnpj_so_digitos():
    assert normalize_cnpj('76535764000143') == '76535764000143'


def test_cnpj_ja_normalizado_nao_e_alterado():
    result = normalize_cnpj('76535764000143')
    assert result == '76535764000143'
    assert len(result) == 14


def test_cnpj_com_formatacao_parcial():
    assert normalize_cnpj('76535764/0001-43') == '76535764000143'


def test_cnpj_invalido_curto_levanta_erro():
    with pytest.raises(ValueError):
        normalize_cnpj('123')


def test_cnpj_invalido_longo_levanta_erro():
    with pytest.raises(ValueError):
        normalize_cnpj('765357640001430000')


def test_cnpj_string_vazia_levanta_erro():
    with pytest.raises(ValueError):
        normalize_cnpj('')


def test_cnpj_com_letras_apos_limpeza_levanta_erro():
    with pytest.raises(ValueError):
        normalize_cnpj('ABCDEFGHIJKLMN')
