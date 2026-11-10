"""v0.6.2 — modalidade sempre perguntada, ligação automática (crm_18) e fala por cima."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import agente  # noqa: E402
import instrucoes  # noqa: E402

LEAD = {"nome": "Ana Teste", "fase": "qualificado"}


def ctx(**extra):
    base = {"ligacao": {"direcao": "feita"}, "lead": dict(LEAD), "mensagens": [{"quem": "medico", "texto": "Belém"}]}
    base.update(extra)
    return base


def test_versao():
    assert agente.VERSAO == "0.6.2"
    assert "10/11" in instrucoes.VERSAO_ROTEIRO


def test_modalidade_perguntada_antes_do_horario():
    txt = instrucoes.montar(ctx())
    pergunta = "Prefere um café aqui no escritório, na Doca, ou uma videochamada"
    assert pergunta in txt
    assert txt.index(pergunta) < txt.index("Qual dia e horário ficam melhores para você?")
    assert "ofereça PRIMEIRO o café" not in txt
    assert "não ofereça o café" in txt          # interior: vídeo


def test_retorno_combinado_continua_igual():
    c = agente.marcar_contexto(ctx(), {"retorno": True})
    assert c["ligacao"].get("retorno") is True
    assert "Como combinamos" in instrucoes.abertura(c)


def test_ligacao_automatica_nao_abre_como_retorno():
    c = agente.marcar_contexto(ctx(automatica=True), {"retorno": True})
    assert "retorno" not in c["ligacao"]
    ab = instrucoes.abertura(c)
    assert "Como combinamos" not in ab
    assert "assistente virtual da Conta Medical" in ab and "gravada" in ab
    assert "permitiu esta ligação pelo WhatsApp" in ab
    assert "primeira ligação" in instrucoes.montar(c)


def test_ligacao_automatica_com_reuniao_marcada_fala_da_reuniao():
    comp = [{"modalidade": "video", "texto": "quarta-feira, 11 de novembro, às 15h", "consultora": "Priscila"}]
    ab = instrucoes.abertura(agente.marcar_contexto(ctx(automatica=True, compromissos=comp), {"retorno": True}))
    assert "uma videochamada marcada" in ab and "permitiu esta ligação" not in ab


def test_religada_continua_igual():
    c = agente.marcar_contexto(ctx(), {"religada": True})
    assert c["ligacao"].get("religada") is True
    assert "liguei de novo" in instrucoes.abertura(c)


def test_ligacao_manual_sem_mudanca():
    c = agente.marcar_contexto(ctx(), {})
    ab = instrucoes.abertura(c)
    assert "Ele já nos conhece" in ab and "permitiu esta ligação" not in ab
    assert "com horário combinado antes" in instrucoes.montar(c)


def test_regra_de_nao_falar_por_cima():
    txt = instrucoes.montar(ctx())
    assert "PARE na hora" in txt
    assert "frase curta de ponte" in txt
