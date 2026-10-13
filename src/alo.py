"""v0.6.0 — detecção do "alô" na ligação feita pela Martha (sem passar o áudio ao modelo).

O ACCEPTED da Meta chega ao banco segundos depois do atendimento (no 1º retorno, 4,5 s). O agente escuta a faixa do médico
e, quando ele termina o "alô" (fala >= FALA_MIN_MS seguida de FIM_MS de silêncio), a Martha começa. O limiar sobe sozinho
com o ruído da linha (chiado): é o maior entre LIMIAR_DB e o piso de ruído (percentil 20 da última ~1 s) + MARGEM_DB.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any


def nivel_db(amostras: Any) -> float:
    """Nível RMS em dBFS de um bloco PCM int16 (bytes, memoryview ou numpy)."""
    import numpy as np
    a = amostras if isinstance(amostras, np.ndarray) else np.frombuffer(amostras, dtype=np.int16)
    if a.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(a.astype(np.float64)))))
    return 20 * math.log10(rms / 32768.0) if rms > 0 else -120.0


class DetectorAlo:
    def __init__(self, limiar_db: float = -42.0, margem_db: float = 12.0, fala_min_ms: float = 120.0,
                 fim_ms: float = 350.0, janela: int = 100):
        self.limiar_db, self.margem_db, self.fala_min_ms, self.fim_ms = limiar_db, margem_db, fala_min_ms, fim_ms
        self.hist: deque[float] = deque(maxlen=janela)
        self.falando_ms = 0.0
        self.silencio_ms = 0.0
        self.fala_total_ms = 0.0
        self.ouviu = False
        self.terminou = False

    def limiar(self) -> float:
        if len(self.hist) < 5:
            return self.limiar_db
        piso = sorted(self.hist)[int(len(self.hist) * 0.2)]
        return max(self.limiar_db, piso + self.margem_db)

    def alimentar(self, db: float, dur_ms: float) -> bool:
        """Um bloco de áudio; devolve True quando o "alô" terminou. Os primeiros 5 blocos só medem o ruído da linha."""
        if len(self.hist) < 5:
            self.hist.append(db)
            return False
        lim = self.limiar()
        self.hist.append(db)
        if db >= lim:
            self.falando_ms += dur_ms
            self.silencio_ms = 0.0
            if self.falando_ms >= self.fala_min_ms:
                self.ouviu = True
            if self.ouviu:
                self.fala_total_ms += dur_ms
        elif self.ouviu:
            self.silencio_ms += dur_ms
            if self.silencio_ms >= self.fim_ms:
                self.terminou = True
        else:
            self.falando_ms = 0.0   # estalo curto não conta
        return self.terminou
