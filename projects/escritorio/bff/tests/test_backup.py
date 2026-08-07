"""O banco é a única cópia da vida dele — e não tinha backup nenhum.

`data.db` guarda o que o vault NÃO guarda: pontos, nível, rotinas, checks do dia,
aprendizados, melhorias, fila de captura. Existia um único snapshot manual de
12/jul e mais nada — sem código, sem tarefa agendada. E `data.db*` está no
`.gitignore`, então nem o push do repositório cobre.

O nível é vitalício por desenho (lei 4: não regride). Um disco ruim tornaria essa
promessa mentira, e não teria como reconstruir: a série de checks diários não
existe em nenhum outro lugar.

Cópia via API online do SQLite, não `shutil.copy`: o BFF escreve no banco enquanto
o backup roda, e copiar o arquivo por baixo produz snapshot rasgado no meio de uma
transação.
"""
import sqlite3
from pathlib import Path

import pytest

from app import store
from app.config import settings


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "t.db"))
    store.init_db()
    store.add_melhoria("uma melhoria que precisa sobreviver", alvo="empresa")


def _melhorias_em(caminho: Path) -> list[str]:
    con = sqlite3.connect(caminho)
    try:
        return [r[0] for r in con.execute("SELECT texto FROM melhorias")]
    finally:
        con.close()


def test_backup_do_dia_e_legivel_e_tem_os_dados(tmp_path):
    destino = tmp_path / "backups"

    caminho = store.fazer_backup(destino, hoje="2026-08-06")

    assert caminho == destino / "data-2026-08-06.db"
    assert _melhorias_em(caminho) == ["uma melhoria que precisa sobreviver"]


def test_um_arquivo_por_dia_sempre_com_o_estado_mais_recente(tmp_path):
    """Rodar de novo no mesmo dia atualiza, não acumula.

    O worker roda a cada poucas horas; um arquivo por execução encheria o disco e
    não daria mais informação que "o estado mais recente daquele dia"."""
    destino = tmp_path / "backups"
    store.fazer_backup(destino, hoje="2026-08-06")

    store.add_melhoria("capturada depois do primeiro backup", alvo="fluxo")
    caminho = store.fazer_backup(destino, hoje="2026-08-06")

    assert len(list(destino.glob("data-*.db"))) == 1
    assert "capturada depois do primeiro backup" in _melhorias_em(caminho)


def test_rotacao_mantem_os_mais_recentes(tmp_path):
    destino = tmp_path / "backups"
    for dia in ("2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"):
        store.fazer_backup(destino, hoje=dia, manter=3)

    restantes = sorted(p.name for p in destino.glob("data-*.db"))

    assert restantes == ["data-2026-08-03.db", "data-2026-08-04.db", "data-2026-08-05.db"]


def _inflar(caminho: Path) -> None:
    """Enche o banco para haver páginas de verdade a corromper.

    Com o banco minúsculo do fixture, zerar bytes cai em espaço livre e o SQLite
    não acusa nada — o teste passaria sem exercitar guarda nenhuma."""
    con = sqlite3.connect(caminho)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.executemany(
            "INSERT INTO melhorias (texto, alvo, criado) VALUES (?, 'empresa', 0)",
            [(f"enchimento {i} " + "x" * 200,) for i in range(2000)],
        )
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        con.close()


def _corromper(caminho: Path, fracao_inicial: float, bytes_zerados: int) -> None:
    dados = bytearray(caminho.read_bytes())
    ini = int(len(dados) * fracao_inicial)
    fim = min(ini + bytes_zerados, len(dados))
    dados[ini:fim] = b"\x00" * (fim - ini)
    caminho.write_bytes(bytes(dados))


def test_corrupcao_detectavel_nao_sobrescreve_o_backup_bom(tmp_path):
    """Backup que copia lixo por cima do último estado bom é pior que backup nenhum.

    Sem a checagem, um arquivo corrompido às 22h destruiria o snapshot íntegro das
    03h do mesmo dia — e o erro só apareceria no dia em que ele precisasse.

    Aqui o SQLite ainda ABRE o arquivo e `integrity_check` devolve a descrição do
    estrago: é a guarda explícita que roda, não o `except`."""
    destino = tmp_path / "backups"
    bom = store.fazer_backup(destino, hoje="2026-08-06")
    assert _melhorias_em(bom) == ["uma melhoria que precisa sobreviver"]

    origem = Path(settings.db_path)
    _inflar(origem)
    _corromper(origem, 0.85, 4096)                # página tardia: abre, mas acusa
    con = sqlite3.connect(origem)
    assert con.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
    con.close()

    assert store.fazer_backup(destino, hoje="2026-08-06") is None
    assert _melhorias_em(bom) == ["uma melhoria que precisa sobreviver"]


def test_corrupcao_catastrofica_tambem_preserva_o_backup_bom(tmp_path):
    """Estrago grande faz o SQLite LEVANTAR em vez de descrever.

    Caminho de código diferente do teste acima (o `except`, não o
    `integrity_check`) e a mesma garantia: o arquivo bom continua de pé."""
    destino = tmp_path / "backups"
    bom = store.fazer_backup(destino, hoje="2026-08-06")

    origem = Path(settings.db_path)
    _inflar(origem)
    _corromper(origem, 0.02, 16384)               # páginas iniciais: nem abre

    assert store.fazer_backup(destino, hoje="2026-08-06") is None
    assert _melhorias_em(bom) == ["uma melhoria que precisa sobreviver"]


def test_troca_falha_deixa_o_backup_do_dia_intacto_e_sem_residuo(tmp_path, monkeypatch):
    """A troca é atômica: copia para `.parcial` e só então renomeia.

    Sem isso, uma queda no meio da cópia deixaria um arquivo truncado ocupando o
    nome do backup do dia — parece backup, não restaura. Aqui a cópia completa e
    o RENAME falha, que é o ponto onde o arquivo bom correria risco."""
    destino = tmp_path / "backups"
    bom = store.fazer_backup(destino, hoje="2026-08-06")
    assert _melhorias_em(bom) == ["uma melhoria que precisa sobreviver"]

    store.add_melhoria("entrou depois", alvo="fluxo")
    original = Path.replace

    def falhar_no_rename(self, alvo):
        if self.suffix == ".parcial":
            raise OSError("disco ficou somente-leitura na hora da troca")
        return original(self, alvo)

    monkeypatch.setattr(Path, "replace", falhar_no_rename)

    assert store.fazer_backup(destino, hoje="2026-08-06") is None
    # O backup do dia continua sendo o último estado bom, não um meio-arquivo.
    assert _melhorias_em(bom) == ["uma melhoria que precisa sobreviver"]
    assert list(destino.glob("*.parcial")) == []


def test_falha_de_disco_nao_derruba_o_worker(tmp_path, monkeypatch):
    """O backup nunca pode ser o motivo de o BFF cair — ele é rede de segurança."""
    def explode(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(store.Path, "mkdir", explode)

    assert store.fazer_backup(tmp_path / "backups", hoje="2026-08-06") is None
