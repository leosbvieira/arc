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

from app import store
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
