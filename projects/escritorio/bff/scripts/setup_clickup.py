"""Cria/renomeia as 10 listas do Aeternum. Defensivo: confirma antes, aborta em colisao."""
import asyncio, sys
sys.path.insert(0, ".")
import httpx
from app.config import settings
from app.clickup_client import ssl_verify   # extrair o bloco SSL :29-36 para funcao reutilizavel

SPACE = "90133461895"
BASE = "https://api.clickup.com/api/v2"
RENAMES = {"901327729095": "Finance", "901327729097": "Corpo", "901327729099": "Responsabilidade"}
CREATES = ["Staging", "Saúde Mental", "Carreira", "Estudo", "Relacionamentos", "Lazer"]
KEEP = {"Trabalho": "901327729093"}

async def main():
    headers = {"Authorization": settings.clickup_token}
    async with httpx.AsyncClient(timeout=30, verify=ssl_verify(), headers=headers) as c:
        lists = (await c.get(f"{BASE}/space/{SPACE}/list?archived=false")).json()["lists"]
        by_name = {l["name"]: l for l in lists}
        by_id = {l["id"]: l for l in lists}
        plan, final = [], dict(KEEP)
        for lid, novo in RENAMES.items():
            cur = by_id.get(lid)
            assert cur, f"lista {lid} sumiu do space"
            if cur["name"] == novo:
                final[novo] = lid; continue
            assert novo not in by_name, f"COLISAO: ja existe lista '{novo}' (id {by_name[novo]['id']}) != {lid}"
            assert int(cur.get("task_count") or 0) == 0, f"'{cur['name']}' NAO esta vazia; migrar antes de renomear"
            plan.append(("rename", lid, cur["name"], novo)); final[novo] = lid
        for nome in CREATES:
            if nome in by_name:
                final[nome] = by_name[nome]["id"]
            else:
                plan.append(("create", None, None, nome))
        print("PLANO:"); [print("  ", p) for p in plan]
        if input("executar? [s/N] ").strip().lower() != "s":
            return
        for op, lid, _de, para in plan:
            if op == "rename":
                (await c.put(f"{BASE}/list/{lid}", json={"name": para})).raise_for_status()
            else:
                r = await c.post(f"{BASE}/space/{SPACE}/list", json={"name": para}); r.raise_for_status()
                final[para] = r.json()["id"]
        done_status = {}
        for nome, lid in final.items():
            statuses = (await c.get(f"{BASE}/list/{lid}")).json().get("statuses", [])
            fech = [s["status"] for s in statuses if s.get("type") in ("done", "closed")]
            assert fech, f"lista {nome} sem status de fechamento!"
            done_status[lid] = "complete" if "complete" in fech else fech[0]
            print(f"{nome}: {lid} fechamento={done_status[lid]}")
        print("\nAREA_LISTS = {"); [print(f'    "{n}": "{l}",') for n, l in final.items()]; print("}")
        print("DONE_STATUS = {"); [print(f'    "{l}": "{s}",') for l, s in done_status.items()]; print("}")

asyncio.run(main())
