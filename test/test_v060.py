"""v0.6.0 — alô detectado na linha, janela antes de desligar, hora falada, agenda vigente, repetir."""
import asyncio
import os
import sys
import time
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import agente  # noqa: E402
import alo  # noqa: E402
import instrucoes  # noqa: E402


def bloco(db, ms=10, sr=16000):
    n = int(sr * ms / 1000)
    amp = 32768 * 10 ** (db / 20) * np.sqrt(2)
    return (amp * np.sin(np.arange(n) / 5)).astype(np.int16)


def test_nivel_db():
    assert abs(alo.nivel_db(bloco(-20)) + 20) < 1.0
    assert alo.nivel_db(np.zeros(160, dtype=np.int16)) == -120.0
    assert abs(alo.nivel_db(bloco(-30).tobytes()) + 30) < 1.0


def test_detector_alo_em_linha_silenciosa():
    d = alo.DetectorAlo()
    for _ in range(50):
        assert not d.alimentar(alo.nivel_db(bloco(-90)), 10)
    for _ in range(40):                     # "alô" de 400 ms
        d.alimentar(alo.nivel_db(bloco(-25)), 10)
    assert d.ouviu and not d.terminou
    for _ in range(40):                     # 400 ms de silêncio (fim do alô = 350 ms)
        d.alimentar(alo.nivel_db(bloco(-90)), 10)
    assert d.terminou


def test_detector_ignora_estalo_e_chiado():
    d = alo.DetectorAlo()
    for _ in range(100):                    # chiado constante a -40 dBFS (acima do limiar fixo de -42)
        d.alimentar(-40.0, 10)
    assert d.limiar() >= -28.5 and not d.ouviu   # o limiar subiu com o piso de ruído: chiado não é alô
    for _ in range(30):                      # alô por cima do chiado
        d.alimentar(-20.0, 10)
    for _ in range(40):
        d.alimentar(-40.0, 10)
    assert d.ouviu and d.terminou
    d2 = alo.DetectorAlo()
    for _ in range(30):
        d2.alimentar(-90.0, 10)
    d2.alimentar(-20.0, 10); d2.alimentar(-20.0, 10)   # estalo de 20 ms
    for _ in range(50):
        d2.alimentar(-90.0, 10)
    assert not d2.ouviu and not d2.terminou


def test_hora_falada_e_confirmacao():
    assert agente.hora_falada("quarta-feira, 14 de outubro, às 15h") == "quarta-feira, 14 de outubro, às três da tarde"
    assert agente.hora_falada("às 8h") == "às oito da manhã"
    assert agente.hora_falada("às 12h30") == "ao meio-dia e meia"
    assert agente.hora_falada("às 13h") == "à uma da tarde"
    assert agente.hora_falada("às 19h15") == "às sete e quinze da noite"
    assert agente.hora_falada("às 18h") == "às seis da tarde"
    f = agente.frase_confirmacao({"texto": "quarta-feira, 14 de outubro, às 15h", "consultora": "Priscila"}, "cafe")
    assert f == ("Fechado! Quarta-feira... 14 de outubro... às três da tarde... aqui no nosso escritório: edifício Quadra "
                 "Corporate... décimo sétimo andar... na Doca... com a Priscila.")


class Est:
    def __init__(self):
        self.ligacao_id = "L1"; self.ferramentas = []; self.inicio = time.monotonic()
        self.ctx = types.SimpleNamespace(room=None)
    def anotar(self, nome, t0, obs=""):
        self.ferramentas.append({"f": nome, "obs": obs})


def test_atende_pelo_alo_antes_do_accepted(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": False}                       # o ACCEPTED ainda não chegou ao banco
    monkeypatch.setattr(agente.banco, "rpc", rpc)

    async def ouvir(room, medico, det):
        for _ in range(30): det.alimentar(-90, 10)
        await asyncio.sleep(0.2)
        for _ in range(40): det.alimentar(-25, 10)       # alô
        for _ in range(40): det.alimentar(-90, 10)
    monkeypatch.setattr(agente, "ouvir_alo", ouvir)
    est = Est()
    t0 = time.monotonic()
    assert asyncio.run(agente.esperar_atender(est, None, medico=object())) is True
    assert time.monotonic() - t0 < 1.0
    assert est.ferramentas[-1]["obs"].startswith("alo;")


def test_atendeu_calado_comeca_pelo_accepted(monkeypatch):
    async def rpc(nome, args):
        return {"atendida": True, "ultimo_status": {"status": "ACCEPTED", "em": str(time.time() - 4.5)}}
    monkeypatch.setattr(agente.banco, "rpc", rpc)

    async def ouvir(room, medico, det):
        await asyncio.sleep(10)
    monkeypatch.setattr(agente, "ouvir_alo", ouvir)
    est = Est()
    t0 = time.monotonic()
    assert asyncio.run(agente.esperar_atender(est, None, medico=object())) is True
    assert time.monotonic() - t0 < 0.5 and est.ferramentas[-1]["obs"].startswith("meta_sem_alo")


def test_desligar_escuta_antes(monkeypatch):
    monkeypatch.setattr(agente, "JANELA_FIM_S", 0.6)

    class Ctx:
        def __init__(self): self.desligou = False
        async def delete_room(self): self.desligou = True
        def shutdown(self, m): pass

    async def corre(fala):
        est = agente.Estado("L1", Ctx(), {})
        sess = types.SimpleNamespace(current_speech=None, agent_state="listening", user_state="listening")
        est.session = sess
        est.encerrar_pedido = True
        async def medico():
            await asyncio.sleep(0.2); sess.user_state = "speaking"
        if fala:
            asyncio.create_task(medico())
        monkeypatch.setattr(agente, "esperar_silencio", lambda s: asyncio.sleep(0))
        await agente.desligar(est, "agente encerrou", ouvir_antes=True)
        return est
    est = asyncio.run(corre(True))
    assert not est.ctx.desligou and not est.encerrando and not est.encerrar_pedido
    assert est.ferramentas[-1]["f"] == "desligar_cancelado"
    est = asyncio.run(corre(False))
    assert est.ctx.desligou


def test_roteiro_v060():
    s = instrucoes.montar({"ligacao": {"direcao": "feita"}, "lead": {"nome": "Leonardo"}, "compromissos": []})
    assert "REPETIR (inegociável)" in s and "AGENDA VIGENTE" in s and "Ficou alguma dúvida" not in s
    assert "ESPERE a resposta" in s and "Não espere o médico falar de novo para desligar" not in s
    s2 = instrucoes.montar({"ligacao": {"direcao": "feita"}, "lead": {"nome": "Leonardo"},
                            "compromissos": [{"modalidade": "cafe", "texto": "x", "consultora": "Priscila"}]})
    assert "AGENDA VIGENTE" not in s2
    a = instrucoes.abertura({"ligacao": {"direcao": "feita", "retorno": True}, "lead": {"nome": "Leonardo Daher"}})
    assert "PARE e espere" in a
