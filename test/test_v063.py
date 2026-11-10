"""v0.6.3 — medição de memória e CPU para dimensionar as ligações ao mesmo tempo."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import agente  # noqa: E402
import recursos  # noqa: E402


def test_versao():
    assert agente.VERSAO == "0.6.3"


def test_medidor_guarda_picos_e_zera_a_janela():
    m = recursos.Medidor()
    a = m.amostrar()
    assert a["processos"] >= 1 and a["rss_maior_mb"] > 0 and a["cpus"] >= 1
    r = m.relatorio()
    assert set(r) == {"agora", "pico_30s", "pico_desde_inicio"}
    assert r["pico_desde_inicio"]["rss_maior_mb"] >= a["rss_maior_mb"]
    assert m.pico_janela == {} and m.pico_total


def test_pico_proprio():
    assert recursos.pico_proprio_mb() > 0


def test_sem_arquivo_nao_quebra():
    assert recursos._ler("/nao/existe") is None and recursos._num(None) is None
