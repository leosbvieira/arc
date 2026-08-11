import assert from "node:assert/strict";
import test from "node:test";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

// `DEFAULT_PARAMS`, em parametrosCore.ts, é a ÚNICA semente das tarifas no app.
// `POINTS` deixou de existir -- manter os dois seria recriar a duplicação que esta
// fatia mata --, então NADA em src/ pode citá-lo. Sem esta guarda, um call site
// esquecido passa despercebido e a fonte única fica pela metade.

function arquivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return arquivos(p);
    return /\.(ts|tsx)$/.test(n) ? [p] : [];
  });
}

test("POINTS não existe mais em lugar nenhum", () => {
  const infratores = arquivos("src")
    .filter((p) => /\bPOINTS\b/.test(readFileSync(p, "utf8")));
  assert.deepEqual(infratores, [], `ainda leem POINTS: ${infratores.join(", ")}`);
});
