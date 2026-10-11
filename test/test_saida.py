"""v0.4.2 — ligação feita pela Martha: só abre depois que o médico atende e o "alô" passa; ligação refeita."""
import asyncio
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import agente  # noqa: E402
import instrucoes  # noqa: E402


@pytest.fixture(autouse=True)
def _rapido(monkeypatch):
    monkeypatch.setattr(agente, "ESPERA_ALO_S", 0.6)
    monkeypatch.setattr(agente, "ESPERA_ATENDER_S", 3.0)


def _est():
    return types.SimpleNamespace(ligacao_id="L1")


def test_atende_e_espera_o_alo(monkeypatch):
    n = {"c": 0}

    async def rpc(nome, args):
        assert nome == "ligacao_estado" and args == {"p_ligacao_id": "L1"}
        n["c"] += 1   # 2ª consulta: acabou de atender
        return {"atendida": False} if n["c"] == 1 else {"atendida": True, "ultimo_status": {"status": "ACCEPTED", "em": str(time.time())}}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    t0 = time.monotonic()
    assert asyncio.run(agente.esperar_atender(_est(), None)) is True
    assert time.monotonic() - t0 >= 0.9   # 0,5 s da primeira consulta + ~0,6 s do alô


def test_atendimento_antigo_nao_espera_de_novo(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": True, "ultimo_status": {"status": "ACCEPTED", "em": str(time.time() - 5)}}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    t0 = time.monotonic()
    assert asyncio.run(agente.esperar_atender(_est(), None)) is True
    assert time.monotonic() - t0 < 0.3


def test_nao_atendeu(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": False, "encerrada": True}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    assert asyncio.run(agente.esperar_atender(_est(), None)) is False


def test_tempo_esgotado(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": False}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    monkeypatch.setattr(agente, "ESPERA_ATENDER_S", 1.2)
    assert asyncio.run(agente.esperar_atender(_est(), None)) is False


def test_abertura_da_ligacao_refeita():
    txt = instrucoes.abertura({"ligacao": {"direcao": "feita", "religada": True}, "lead": {"nome": "Leonardo Daher"}})
    assert "liguei de novo" in txt and "gravada" in txt


def test_roteiro_manda_religar_e_nao_consultora():
    txt = instrucoes.montar({"ligacao": {"direcao": "feita"}, "lead": {"nome": "Leonardo"}})
    assert "religar" in txt and "Vou desligar e já te ligo de novo" in txt
