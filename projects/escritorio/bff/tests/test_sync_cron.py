"""O consumidor PowerShell da fonte única, testado pelo plano que ele produz."""
import json
import subprocess
from pathlib import Path

import pytest

from app import ritos

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "sync-cron.ps1"


def plano(instaladas: list[str]) -> dict:
    saida = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(_SCRIPT), "-DryRun", "-TarefasInstaladas", ",".join(instaladas)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_registra_um_por_rito_com_o_gatilho_certo():
    p = plano([])
    por_slug = {r["slug"]: r for r in p["registrar"]}
    assert set(por_slug) == {r["slug"] for r in ritos.RITOS}
    assert por_slug["shutdown"]["trigger"] == "Daily 19:00"
    assert por_slug["review"]["trigger"] == "Weekly Sunday 20:00"
    assert por_slug["shutdown"]["script"] == "nudge.ps1"
    assert por_slug["digest"]["script"] == "run-digest.ps1"
    assert por_slug["closing"]["task"] == "Aeternum Fechamento"


def test_remove_tarefa_obsoleta_e_preserva_o_bff():
    p = plano(["Aeternum Toque", "Aeternum Antigo", "Aeternum BFF"])
    assert p["remover"] == ["Aeternum Antigo"]


def test_nao_remove_nada_quando_o_instalado_bate():
    p = plano([r["task"] for r in ritos.RITOS] + ["Aeternum BFF"])
    assert p["remover"] == []


def test_omitir_o_parametro_consulta_o_agendador_de_verdade():
    """Regressão do item A: [string]$TarefasInstaladas = $null é sempre
    'não-null' em PowerShell (coage pra ""), então `if ($null -ne ...)` era
    sempre verdadeiro e o ramo do Get-ScheduledTask nunca rodava fora do teste.
    Aqui a gente chama SEM -TarefasInstaladas e confere, por fora, contra o
    Agendador de verdade -- não contra o próprio script."""
    consulta = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "(Get-ScheduledTask -TaskName 'Aeternum *' -ErrorAction SilentlyContinue "
         "| ForEach-Object { $_.TaskName }) -join \"`n\""],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    instaladas = [l for l in consulta.stdout.splitlines() if l.strip()]
    if not instaladas:
        pytest.skip("nenhuma tarefa 'Aeternum *' instalada nesta máquina")

    desejadas = {r["task"] for r in ritos.RITOS}
    esperado = sorted(t for t in instaladas if t != "Aeternum BFF" and t not in desejadas)

    saida = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(_SCRIPT), "-DryRun"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert saida.returncode == 0, saida.stderr
    p = json.loads(saida.stdout)
    assert sorted(p["remover"]) == esperado


def test_json_invalido_aborta(tmp_path, monkeypatch):
    """Fail-closed: JSON quebrado não pode virar agenda pela metade."""
    ruim = tmp_path / "ritos.json"
    ruim.write_text("{ nao e lista", encoding="utf-8")
    saida = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(_SCRIPT), "-DryRun", "-Arquivo", str(ruim)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert saida.returncode != 0
