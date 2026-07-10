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
from app.config import DEFAULTS, settings

for _field in DEFAULTS:
    setattr(settings, _field, f"test-{_field}")
