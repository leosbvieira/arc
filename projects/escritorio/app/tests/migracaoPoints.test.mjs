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


// A fatia 1A matou `POINTS`, e a mesma classe de cópia continuava viva em outros
// três lugares. Estas guardas existem pelo mesmo motivo que a de cima: um call site
// esquecido passa despercebido e a fonte única fica pela metade.

test("nenhuma tela desenha um número fixo de prioridades do Shutdown", () => {
  // `main.py` declara PRIORIDADES_SHUTDOWN e o /wiki/parametros publica. A tela
  // desenhava [0,1,2] fixo, e o api.ts fatiava em 3: mudar para 4 no servidor fazia
  // o push dizer 4 enquanto a tela mostrava 3 caixas e o POST cortava a quarta.
  const shutdown = readFileSync("src/screens/Shutdown.tsx", "utf8");
  assert.ok(
    !/\[0,\s*1,\s*2\]/.test(shutdown),
    "Shutdown.tsx voltou a assumir três prioridades",
  );
  const api = readFileSync("src/api.ts", "utf8");
  assert.ok(
    !/prioridades\.slice\(0,\s*\d+\)/.test(api),
    "api.ts voltou a cortar as prioridades num número fixo",
  );
});

test("a lista de áreas não volta a ser copiada nas telas", () => {
  // `tasks.AREAS` é a fonte; o /wiki/parametros publica. `AREAS_TRIAGEM` (api.ts) é
  // OUTRA lista de propósito — a triagem tira coisas DE Staging, então Staging não é
  // destino — e por isso a guarda olha só as telas.
  for (const arquivo of ["src/screens/Tasks.tsx"]) {
    const texto = readFileSync(arquivo, "utf8");
    const copia = /"Trabalho",\s*"Staging"/.test(texto);
    assert.ok(!copia, `${arquivo} voltou a embutir a lista de áreas`);
  }
});
