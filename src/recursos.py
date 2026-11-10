"""v0.6.3 — medição de memória e CPU do contêiner, para saber quantas ligações ao mesmo tempo ele aguenta.

Só lê /proc e o cgroup (nada é instalado). Tudo devolve None quando o arquivo não existe (fora de Linux/contêiner).
"""
from __future__ import annotations

import os
import resource
from typing import Any

MB = 1024 * 1024


def _ler(caminho: str) -> str | None:
    try:
        with open(caminho, encoding="ascii") as f:
            return f.read().strip()
    except OSError:
        return None


def _num(txt: str | None) -> int | None:
    return int(txt) if txt and txt.isdigit() else None


def memoria_conteiner() -> dict[str, Any]:
    """Uso e teto de memória do contêiner (cgroup v2; v1 como reserva), em MB."""
    uso = _num(_ler("/sys/fs/cgroup/memory.current")) or _num(_ler("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
    teto = _num(_ler("/sys/fs/cgroup/memory.max")) or _num(_ler("/sys/fs/cgroup/memory/memory.limit_in_bytes"))
    if teto and teto > 1 << 50:   # "sem limite" no cgroup v1
        teto = None
    return {"uso_mb": round(uso / MB) if uso else None, "teto_mb": round(teto / MB) if teto else None}


def processos() -> list[dict[str, Any]]:
    """Processos Python do contêiner com a memória residente (RSS) de cada um, em MB."""
    out = []
    for pid in os.listdir("/proc") if os.path.isdir("/proc") else []:
        if not pid.isdigit():
            continue
        st = _ler(f"/proc/{pid}/status")
        if not st:
            continue
        campos = dict(l.split(":", 1) for l in st.splitlines() if ":" in l)
        if "python" not in campos.get("Name", "").lower():
            continue
        rss_kb = _num(campos.get("VmRSS", "").strip().split(" ")[0])
        out.append({"pid": int(pid), "rss_mb": round(rss_kb / 1024) if rss_kb else 0})
    return out


def carga() -> float | None:
    try:
        return round(os.getloadavg()[0], 2)
    except OSError:
        return None


def pico_proprio_mb() -> int:
    """Pico de memória deste processo (no agente, cada ligação roda num processo próprio)."""
    kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(kb / 1024)


class Medidor:
    """Amostra a cada poucos segundos e guarda o pico desde a última batida e desde o início."""

    def __init__(self) -> None:
        self.pico_janela: dict[str, Any] = {}
        self.pico_total: dict[str, Any] = {}

    def amostrar(self) -> dict[str, Any]:
        mem = memoria_conteiner()
        procs = processos()
        a = {"mem_mb": mem["uso_mb"], "teto_mb": mem["teto_mb"], "processos": len(procs),
             "rss_soma_mb": sum(p["rss_mb"] for p in procs), "rss_maior_mb": max((p["rss_mb"] for p in procs), default=0),
             "carga_1min": carga(), "cpus": os.cpu_count()}
        for pico in (self.pico_janela, self.pico_total):
            for k in ("mem_mb", "processos", "rss_soma_mb", "rss_maior_mb", "carga_1min"):
                if a.get(k) is not None and (pico.get(k) is None or a[k] > pico[k]):
                    pico[k] = a[k]
        return a

    def relatorio(self) -> dict[str, Any]:
        """Para a batida: a amostra de agora, o pico dos últimos 30 s e o pico desde que o agente subiu."""
        agora = self.amostrar()
        r = {"agora": agora, "pico_30s": dict(self.pico_janela), "pico_desde_inicio": dict(self.pico_total)}
        self.pico_janela = {}
        return r
