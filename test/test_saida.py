"""v0.4.0 — ligação feita pela Martha: só fala depois que o médico atende."""
import asyncio
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("VOZ_ESPERA_ATENDER_S", "3")
import agente  # noqa: E402


class SessaoFalsa:
    def __init__(self):
        self.cb = {}

    def on(self, nome, f):
        self.cb.setdefault(nome, []).append(f)

    def off(self, nome, f):
        self.cb.get(nome, []).remove(f)

    def emitir(self, nome, ev):
        for f in list(self.cb.get(nome, [])):
            f(ev)


@pytest.fixture(autouse=True)
def _rapido(monkeypatch):
    monkeypatch.setattr(agente, "ESPERA_ALO_S", 0.3)


def _est():
    return types.SimpleNamespace(ligacao_id="L1")


def test_atende_pelo_status(monkeypatch):
    estados = iter([{"atendida": False}, {"atendida": True}])

    async def rpc(nome, args):
        assert nome == "ligacao_estado" and args == {"p_ligacao_id": "L1"}
        return next(estados)

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    s = SessaoFalsa()
    assert asyncio.run(agente.esperar_atender(_est(), s)) is True
    assert s.cb["user_state_changed"] == []


def test_atende_pela_voz(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": False}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    s = SessaoFalsa()

    async def roda():
        t = asyncio.create_task(agente.esperar_atender(_est(), s))
        await asyncio.sleep(0.2)
        s.emitir("user_state_changed", types.SimpleNamespace(new_state="speaking"))
        return await t

    assert asyncio.run(roda()) is True


def test_nao_atendeu(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": False, "encerrada": True}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    assert asyncio.run(agente.esperar_atender(_est(), SessaoFalsa())) is False


def test_tempo_esgotado(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": False}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    monkeypatch.setattr(agente, "ESPERA_ATENDER_S", 1.5)
    assert asyncio.run(agente.esperar_atender(_est(), SessaoFalsa())) is False


def test_espera_o_alo_terminar(monkeypatch):
    """v0.4.1: atendeu (ACCEPTED) e disse "alô": a Martha só começa depois que ele para de falar."""
    async def rpc(nome, args):
        return {"atendida": True}

    monkeypatch.setattr(agente.banco, "rpc", rpc)
    monkeypatch.setattr(agente, "ESPERA_ALO_S", 2.0)
    s = SessaoFalsa()

    async def roda():
        t0 = time.monotonic()
        t = asyncio.create_task(agente.esperar_atender(_est(), s))
        await asyncio.sleep(0.2)
        s.emitir("user_state_changed", types.SimpleNamespace(new_state="speaking"))
        await asyncio.sleep(0.8)
        assert not t.done()   # ainda falando: não pode começar
        s.emitir("user_state_changed", types.SimpleNamespace(new_state="listening"))
        ok = await t
        return ok, time.monotonic() - t0

    ok, dt = asyncio.run(roda())
    assert ok is True and dt >= 1.3
