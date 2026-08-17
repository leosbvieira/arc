// O laço de drenagem da fila offline, separado do que fala com o aparelho.
//
// Isto existe por uma razão só: o conserto de verdade da fila mora AQUI (rotação do
// item recusado, contagem de tentativa, escaninho, ordem das escritas), e enquanto ele
// morava dentro de `captureQueue.ts` não havia como testá-lo — aquele módulo importa
// `expo-secure-store` e `expo-constants` no topo, e o `node --test` não sobe nenhum
// dos dois. Era a mesma situação que deixou o `catch { break }` viver a vida inteira
// do arquivo sem ninguém notar.
//
// Regra deste arquivo: NENHUM import, nem de valor nem de tipo. Tudo entra por
// `deps` — inclusive a política de decisão. É o que permite o teste injetar uma fila
// de mentira e observar a ordem exata das escritas.

export type EntradaDaFila = { id: string; chunks: number; tentativas?: number };

export type DecisaoDaFila =
  | "esperar_rede"
  | "esperar_login"
  | "recolocar_no_fim"
  | "desistir";

export type ResultadoDoFlush = {
  restantes: number;
  parou: "rede" | "login" | null;
  rejeitados: number;
};

export type DepsDaDrenagem<Item> = {
  lerIndice: () => Promise<EntradaDaFila[]>;
  gravarIndice: (idx: EntradaDaFila[]) => Promise<void>;
  lerItem: (e: EntradaDaFila) => Promise<Item>;
  apagarItem: (e: EntradaDaFila) => Promise<void>;
  enviar: (item: Item) => Promise<void>;
  arquivarRejeitado: (e: EntradaDaFila) => Promise<void>;
  decidir: (erro: unknown, tentativasFeitas: number) => DecisaoDaFila;
  paraAFila: (d: DecisaoDaFila) => boolean;
};

export async function drenar<Item>(
  deps: DepsDaDrenagem<Item>,
): Promise<ResultadoDoFlush> {
  let idx = await deps.lerIndice();
  // Uma volta só: assim que reencontramos alguém que já falhou nesta drenagem, a fila
  // só tem recusados e continuar seria girar para sempre.
  const jaFalharamAgora = new Set<string>();
  let parou: "rede" | "login" | null = null;
  let rejeitados = 0;

  while (idx.length > 0) {
    const entrada = idx[0];
    if (jaFalharamAgora.has(entrada.id)) break;

    let item: Item;
    try {
      item = await deps.lerItem(entrada);
    } catch {
      // Item envenenado (JSON corrompido / chunks ausentes): o conteúdo já se perdeu.
      // De-indexa e descarta pra não travar o resto da fila.
      idx = idx.slice(1);
      await deps.gravarIndice(idx); // de-indexa ANTES de apagar (órfão > fantasma)
      await deps.apagarItem(entrada);
      continue;
    }

    try {
      await deps.enviar(item);
    } catch (erro) {
      const tentativas = (entrada.tentativas ?? 0) + 1;
      const decisao = deps.decidir(erro, tentativas);

      if (deps.paraAFila(decisao)) {
        // Rede caída ou sessão expirada: não é culpa deste item, e o resto da fila
        // responderia igual. Não gasta tentativa.
        parou = decisao === "esperar_login" ? "login" : "rede";
        break;
      }

      jaFalharamAgora.add(entrada.id);
      idx = idx.slice(1);

      if (decisao === "desistir") {
        // Arquiva ANTES de de-indexar. Na ordem inversa, um crash entre as duas
        // escritas — ou um throw do arquivamento, que nem precisa de crash — deixava
        // o item fora dos DOIS índices, com os chunks órfãos e ilegíveis: perda total
        // no único caminho criado pra impedir perda. Assim o pior caso é duplicata.
        await deps.arquivarRejeitado({ ...entrada, tentativas });
        await deps.gravarIndice(idx);
        rejeitados += 1;
      } else {
        // Pro fim da fila, com a tentativa contada: um 404 eterno não segura mais a
        // captura que entrou depois dele.
        idx = [...idx, { ...entrada, tentativas }];
        await deps.gravarIndice(idx);
      }
      continue;
    }

    idx = idx.slice(1);
    await deps.gravarIndice(idx); // de-indexa ANTES de apagar os chunks
    await deps.apagarItem(entrada);
  }

  return { restantes: idx.length, parou, rejeitados };
}
