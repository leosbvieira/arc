"""Higiene do ambiente de teste.

W4 adicionou `_guard_default_secrets()` no `lifespan`: o boot é bloqueado se qualquer
segredo em `config.DEFAULTS` permanecer no valor default. Os testes que sobem o app via
`with TestClient(...)` executam o lifespan de verdade — e o `.env` real do Leo ainda mantém
`internal_token` no default, o que derrubaria esses testes.

Setamos os segredos guardados para valores não-default AQUI, no nível de módulo do conftest:
o pytest importa o conftest antes dos módulos de teste, então isto vale inclusive para
`test_digest_v2.HDR`, que captura `settings.internal_token` no import. Só a sessão de teste é
afetada; o `.env` não é tocado.
"""
import tempfile
from pathlib import Path

import pytest

from app import hermes_client, store
from app.config import DEFAULTS, settings

for _field in DEFAULTS:
    setattr(settings, _field, f"test-{_field}")

# --- db da suíte: temporário, por sessão ------------------------------------
# A maioria dos testes já aponta `db_path` pra um tmp_path próprio, mas nem todos
# (test_fixes_auditoria escreve pela store diretamente). Sem esta linha, esses testes
# batiam no `data.db` de PRODUÇÃO — e isso é ruim de duas formas:
#
# 1. A suíte enfileirava capturas de teste na fila real. O BFF de produção está de pé:
#    o worker dele drena `capture_queue` a cada 5s e ingeriria "conteúdo de teste" no
#    vault do Leo.
# 2. Corrida entre o worker de prod e a suíte: `process_pending()` pega a linha pendente
#    de MENOR id, então uma linha que sobrou da rodada anterior (ou que o worker ainda
#    não drenou) era processada no lugar da linha do teste — vermelho intermitente,
#    dependendo de quem chegasse primeiro.
#
# Um db temporário por SESSÃO preserva o compartilhamento entre testes do mesmo arquivo
# (que test_fixes_auditoria assume) e nasce limpo a cada rodada.
_TMP_DB = Path(tempfile.mkdtemp(prefix="escritorio-tests-")) / "test.db"
settings.db_path = str(_TMP_DB)
store.init_db()


# --- nenhum teste fala com o Hermes de verdade -------------------------------
# Descoberto quando o recap da fatia 3 entrou no /compile: os testes de compile
# fakeiam `compile_reading`, mas o recap é OUTRA chamada, e ela caiu no `_oneshot`
# real — que dispara o `hermes.exe` como subprocesso. A suíte foi de 56s para 200s
# sem ninguém notar, porque a chamada é best-effort e o erro é engolido.
#
# Falhar alto e na hora é melhor que esperar: quem precisa do modelo stuba
# `_oneshot` no próprio teste, e essa substituição vence esta (o corpo do teste
# roda depois das fixtures).
@pytest.fixture(autouse=True)
def _sem_hermes_de_verdade(request, monkeypatch):
    # Quem testa o PRÓPRIO `_oneshot` (classificação de erro, serialização,
    # prompt por stdin) pede exceção com @pytest.mark.hermes_oneshot.
    if request.node.get_closest_marker("hermes_oneshot"):
        return

    async def proibido(*_args, **_kwargs):
        raise RuntimeError("hermes_oneshot_nao_stubado_neste_teste")

    monkeypatch.setattr(hermes_client, "_oneshot", proibido)
