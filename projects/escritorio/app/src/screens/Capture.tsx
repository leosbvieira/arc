import Feather from "@expo/vector-icons/Feather";
import { LinearGradient } from "expo-linear-gradient";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { capture, contarCapturasFalhadas, reprocessarCapturasFalhadas } from "../api";
import {
  createCaptureClientKey,
  enqueue,
  flush,
  pendingCount,
  rejectedCount,
  discardRejected,
  listRejected,
  retryRejected,
} from "../captureQueue";
import { ehFalhaDeRede, mensagemDaRecusa } from "../offlineError";
import {
  clearReadingDraft,
  loadReadingDraft,
  mutateReadingDraft,
  ReadingDraft,
  ReadingDraftItem,
  saveReadingDraft,
} from "../readingDraft";
import {
  appendReadingBuffer,
  Book,
  compileReadingSession,
  createBook,
  createReadingSession,
  discardReadingSession,
  deleteLastReadingBuffer,
  draftReadingSession,
  getReadingSession,
  listBooks,
  listPendingReadingSessions,
  reabrirBook,
  readingErrorDetail,
  ReadingApiError,
  ReadingHook,
  ReadingReconcileResult,
  ReadingSession,
  ReadingSnapshot,
  reconciliarTerminarBook,
  reconcileReadingSession,
  rejectReadingDraft,
  terminarBook,
  updateLastReadingBuffer,
} from "../readingApi";
import {
  avisoDeObrasPresas,
  mensagemDeReconciliacao,
  mensagemDeResolucaoFalha,
  mensagemDeTermino,
  mensagemDeTerminoFalho,
} from "../estanteResumo";
import { parseReadingEntry } from "../readingParser";
import { readingPreviewFromSession } from "../readingStaging";
import { montarEstante, LinhaEstante } from "../shelfView";
import {
  canClearLocalAfterDiscardFailure,
  formatReadingElapsed,
  normalizeReadingActiveSeconds,
} from "../readingSessionState";
import { useParams } from "../parametros";
import { colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, Field } from "../ui";
import { useReadingSpeech } from "../useReadingSpeech";

type Mode = "captura" | "leitura";
type Item = ReadingDraftItem;

const KIND: Record<string, { color: string; icon: any }> = {
  "citação": { color: colors.primary, icon: "book-open" },
  "comentário": { color: colors.textMuted, icon: "message-square" },
  ideia: { color: "#A88CBE", icon: "zap" },
  coach: { color: "#6FB58C", icon: "user" },
};

function createSessionKey(ts: number): string {
  return `session:${createCaptureClientKey(ts)}`;
}

function kindToHook(kind: string): ReadingHook {
  if (kind === "citação") return "quote";
  if (kind === "comentário") return "comentario";
  if (kind === "ideia" || kind === "coach" || kind === "lista") {
    return kind;
  }
  return "texto";
}

function hookToKind(hook: ReadingHook): string {
  if (hook === "quote") return "citação";
  if (hook === "comentario" || hook === "texto") return "comentário";
  return hook;
}

function draftFromRemote(session: ReadingSession): ReadingDraft {
  const startedAt = Math.round(session.inicio * 1000);
  const updatedAt = Math.round(session.updated * 1000);
  return {
    sessionKey: session.client_key,
    remoteId: session.id,
    book: session.livro ?? "",
    bookId: session.book_id,
    pageStart:
      session.pagina_inicial === null
        ? ""
        : String(session.pagina_inicial),
    pageEnd:
      session.pagina_final === null ? "" : String(session.pagina_final),
    startedAt,
    activeSeconds: normalizeReadingActiveSeconds(undefined, startedAt, updatedAt),
    updatedAt,
    items: (session.buffer ?? []).map((chunk) => ({
      id: `${session.client_key}:${chunk.seq}`,
      kind: hookToKind(chunk.hook),
      text: chunk.texto,
      seq: chunk.seq,
    })),
    syncedSeq: Math.max(0, ...(session.buffer ?? []).map((chunk) => chunk.seq)),
    status: "pending",
  };
}

export default function Capture({
  initialMode = "captura",
  modeRequestId = 0,
  active = true,
}: {
  initialMode?: Mode;
  modeRequestId?: number;
  active?: boolean;
}) {
  // Depois da 1A a tarifa vem do servidor, não mais de uma constante no theme.
  const { tarifas } = useParams();
  const [mode, setMode] = useState<Mode>(initialMode);
  const modeRef = useRef<Mode>(initialMode);
  const modeSelectionRef = useRef(0);
  const activeRef = useRef(active);
  const handledModeRequestRef = useRef(modeRequestId);

  // captura livre
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const replyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [busy, setBusy] = useState(false);
  const [sensitive, setSensitive] = useState(false);
  const [pending, setPending] = useState(0);
  const [rejected, setRejected] = useState(0);
  const [status, setStatus] = useState("");

  // sessão de leitura
  const [book, setBook] = useState("");
  const [selectedBookId, setSelectedBookId] = useState<number | null>(null);
  const [pageStart, setPageStart] = useState("");
  const [pageEnd, setPageEnd] = useState("");
  const [items, setItems] = useState<Item[]>([]);
  const [entry, setEntry] = useState("");
  const [editingSeq, setEditingSeq] = useState<number | null>(null);
  const [removeConfirmSeq, setRemoveConfirmSeq] = useState<number | null>(null);
  const [editingBusy, setEditingBusy] = useState(false);
  const [compiling, setCompiling] = useState(false);
  // Preview read-only da nota gerada (staged), aguardando aprovar/rejeitar. Null
  // = editor cru. Enquanto != null a edição fica congelada (bate com o servidor).
  const [preview, setPreview] = useState<string | null>(null);
  const [sessionStart, setSessionStart] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const elapsedSecondsRef = useRef(0);
  const [speechError, setSpeechError] = useState("");
  const [serverPending, setServerPending] = useState<ReadingSession[]>([]);
  const [readingDraftReady, setReadingDraftReady] = useState(false);
  const draftRef = useRef<ReadingDraft | null>(null);
  const draftRevisionRef = useRef(0);
  const readingFormRevisionRef = useRef(0);
  const compileLockRef = useRef(false);
  const syncChain = useRef<Promise<void>>(Promise.resolve());

  // a estante
  const [shelf, setShelf] = useState<Book[] | null>(null);
  const [finished, setFinished] = useState<Book[] | null>(null);
  const [showFinished, setShowFinished] = useState(false);
  const [shelfBusyId, setShelfBusyId] = useState<number | null>(null);
  const [newBookMode, setNewBookMode] = useState(false);
  // true só depois de um loadShelf que falhou de verdade — nunca durante o
  // primeiro carregamento, senão a mensagem de "indisponível" pisca em toda
  // entrada na tela antes do fetch normal responder.
  const [shelfError, setShelfError] = useState(false);
  // Obras que ficaram reservadas: o resumão foi pedido ao ClickUp e a resposta não
  // veio. Não voltam sozinhas — é ele quem manda perguntar como ficou.
  const [presas, setPresas] = useState<Book[]>([]);
  const [presaErro, setPresaErro] = useState("");
  // Capturas que o SERVIDOR desistiu de processar (fila do BFF, não a do aparelho).
  const [falhadasNoServidor, setFalhadasNoServidor] = useState(0);
  const [reprocessando, setReprocessando] = useState(false);

  const loadShelf = useCallback(async () => {
    // Qualquer recarga torna a explicação anterior obsoleta por definição — sem isto
    // uma frase velha reaparecia colada na próxima obra que ficasse presa.
    setPresaErro("");
    try {
      const { books } = await listBooks("lendo");
      setShelf(books);
      setShelfError(false);
      // Obra reservada some das duas listas normais: ela não está lendo nem
      // terminada. Sem esta busca, ficaria invisível — e obra invisível é obra
      // que ninguém reconcilia.
      try {
        setPresas((await listBooks("terminando")).books);
      } catch {
        // Falhar aqui não pode derrubar a estante: é informação extra.
        setPresas([]);
      }
    } catch {
      // null = NÃO CARREGOU. A tela mostra o campo livre, e nunca uma estante
      // vazia que o Leo leria como "não tenho livro nenhum". Mas a degradação
      // não pode ficar muda: sem isto, a sessão nasce com bookId null e some
      // da estante para sempre, sem que nada avise que isso aconteceu.
      setShelf(null);
      setShelfError(true);
    }
  }, []);

  useEffect(() => {
    if (mode === "leitura") void loadShelf();
  }, [mode, loadShelf]);

  function replaceDraft(next: ReadingDraft | null): void {
    draftRevisionRef.current += 1;
    draftRef.current = next;
  }

  function updateReadingField(
    setter: (value: string) => void,
    value: string,
  ): void {
    readingFormRevisionRef.current += 1;
    setter(value);
  }

  // Mexer no texto é dizer "não é essa obra". Sem isso, a tela mostra um
  // título e a sessão grava outro — o servidor ignora `livro` quando há
  // `book_id`, então o estrago é de rótulo, não de dado. Mas é estrago.
  function editarTitulo(value: string): void {
    updateReadingField(setBook, value);
    if (selectedBookId !== null) setSelectedBookId(null);
  }

  // Saída para quem entrou em "novo livro" sem querer: sem isto, o único jeito
  // de ver a estante de novo era terminar ou descartar uma sessão, porque
  // `Capture` fica montado (com `active` só trocando de estilo) a vida inteira
  // do app — trocar de aba e voltar não desfaz o toque.
  function voltarParaEstante(): void {
    setNewBookMode(false);
    updateReadingField(setBook, "");
    updateReadingField(setPageStart, "");
  }

  // book_nao_aceita_sessao: a obra virou "terminado" — aqui ou em outro
  // aparelho — depois que a sessão a escolheu, e o `createReadingSession` do
  // `syncDraft` só descobre isso na hora de criar. É comum aos três lugares
  // que chamam `syncDraft` (autosave, compilar, gerar preview): nenhum pode
  // tratar isso como falha de rede, senão o usuário fica preso tentando de
  // novo pra sempre. O estado local (selectedBookId apontando pra obra morta)
  // é o que precisa limpar; a mensagem pro usuário fica a cargo de quem chama.
  function limparSelecaoDeObraTerminada(): void {
    setSelectedBookId(null);
    void loadShelf();
  }

  // `updateReadingField` (não os setters crus) porque escolher/criar uma obra é
  // exatamente o tipo de "o usuário mexeu no formulário" que o restore() em
  // curso precisa enxergar — sem isso, uma escolha feita antes do restore()
  // terminar de conferir o servidor pode ser apagada em silêncio quando ele volta.
  function escolherObra(linha: LinhaEstante): void {
    setSelectedBookId(linha.id);
    updateReadingField(setBook, linha.titulo);
    // Sugestão, não imposição: pode ter lido no papel desde a última sessão.
    updateReadingField(setPageStart, linha.paginaInicialSugerida);
    updateReadingField(setPageEnd, "");
    setNewBookMode(false);
  }

  // Devolve a obra criada (não só marca state) porque quem chama em modo "novo
  // livro" — `beginSession`/`startSession` — precisa do id no mesmo tick, antes
  // que o state atualizado volte num novo render.
  async function criarObra(): Promise<{ id: number; titulo: string } | null> {
    const titulo = book.trim();
    if (!titulo) return null;
    try {
      const { book: criada } = await createBook(titulo);
      setSelectedBookId(criada.id);
      updateReadingField(setBook, criada.titulo);
      await loadShelf();
      return { id: criada.id, titulo: criada.titulo };
    } catch (error) {
      // Único código real que o POST devolve. Mapear em vez de repassar cru: é
      // o único lugar do arquivo que mostraria uma string de servidor ao Leo.
      setSpeechError(
        readingErrorDetail(error) === "titulo_invalido"
          ? "esse título não é válido — tente outro"
          : "não deu para registrar a obra",
      );
      return null;
    }
  }

  async function terminarObra(bookId: number, titulo: string): Promise<void> {
    setShelfBusyId(bookId);
    try {
      const { resumo_task_id } = await terminarBook(bookId);
      await loadShelf();
      // Terminar deixou de ser só sumir da lista: agora nasce uma tarefa. Dizer
      // onde ela foi parar é o que transforma o ✓ em algo que ele confere depois.
      Alert.alert(
        "Obra terminada",
        mensagemDeTermino({ titulo, resumoTaskId: resumo_task_id }),
      );
    } catch (error) {
      const detalhe = readingErrorDetail(error);
      if (detalhe === "book_ja_terminado") {
        // Já terminada em outro lugar: recarregar é a resposta certa, não um erro.
        await loadShelf();
      } else {
        // Recarrega ANTES de avisar: `book_resumao_indisponivel` deixou a obra
        // reservada, e ela precisa aparecer na lista de presas junto com o aviso.
        await loadShelf();
        // E SOLTA a seleção. Sem isto a obra continuava escolhida em estado
        // "terminando", e "Começar leitura" respondia "essa obra foi terminada —
        // reabra antes de ler": não foi terminada, e reabrir é impossível nesse
        // estado. Duas frases erradas em sequência a partir de um toque só.
        if (selectedBookId === bookId) {
          // Solta TAMBÉM o que a seleção preencheu. Zerar só o `selectedBookId` deixava
          // o título na caixa: o botão seguia habilitado, e a próxima sessão nascia com
          // `book_id` null — órfã da estante, que é o defeito que a fatia 1 existe para
          // matar. `voltarParaEstante` já faz as três coisas juntas.
          voltarParaEstante();
          setSelectedBookId(null);
        }
        setSpeechError(mensagemDeTerminoFalho(detalhe));
      }
    } finally {
      setShelfBusyId(null);
    }
  }

  async function resolverObraPresa(bookId: number, titulo: string): Promise<void> {
    setShelfBusyId(bookId);
    setPresaErro("");
    try {
      const { resultado } = await reconciliarTerminarBook(bookId);
      await loadShelf();
      Alert.alert("Obra que ficou fechando", mensagemDeReconciliacao(resultado, titulo));
    } catch (error) {
      // Continua presa de propósito QUANDO a causa é não saber o que houve no
      // ClickUp: isso não é prova de que nada foi criado, e liberar no escuro
      // duplicaria o resumão. Mas os 409 dizem o OPOSTO — a reserva já saiu — e
      // tratá-los como "segue reservada" mandava ele bater de novo num endpoint
      // que responderia 409 para sempre.
      const detalhe = readingErrorDetail(error);
      // Recarrega SEMPRE: é idempotente e barato, e nos desfechos em que o app não
      // sabe o que houve (timeout, queda) a estante é a única fonte de verdade.
      // Recarregar só nos casos conhecidos deixava a tela mostrando um estado que
      // podia já não existir. `loadShelf` limpa `presaErro`, então a frase vem depois.
      await loadShelf();
      setPresaErro(mensagemDeResolucaoFalha(detalhe));
    } finally {
      setShelfBusyId(null);
    }
  }

  function confirmarTerminar(bookId: number, titulo: string): void {
    Alert.alert("Terminar obra", `Terminar ${titulo}?`, [
      { text: "cancelar", style: "cancel" },
      { text: "terminar", onPress: () => void terminarObra(bookId, titulo) },
    ]);
  }

  async function reabrirObra(bookId: number): Promise<void> {
    setShelfBusyId(bookId);
    try {
      try {
        await reabrirBook(bookId);
      } catch (error) {
        // Espelha terminarObra: já reaberta em outro lugar não é erro, é a
        // resposta certa recarregar e seguir.
        if (readingErrorDetail(error) !== "book_ja_lendo") throw error;
      }
      await loadShelf();
      // Falha aqui é só a lista de terminadas ficar velha — o reabrir em si já
      // teve sucesso acima, então não pode virar "não deu para reabrir a obra".
      try {
        setFinished((await listBooks("terminado")).books);
      } catch {
        setFinished(null);
      }
    } catch {
      setSpeechError("não deu para reabrir a obra");
    } finally {
      setShelfBusyId(null);
    }
  }

  const speech = useReadingSpeech({
    onFinal: (transcript) => {
      if (modeRef.current === "captura") {
        setText((current) => `${current}${current.trim() ? " " : ""}${transcript}`);
        setStatus("fala capturada — revise antes de enviar");
        return;
      }
      appendTranscript(transcript);
    },
    onError: (code) => {
      const message = `transcrição indisponível (${code}) — entrada manual continua`;
      modeRef.current === "captura" ? setStatus(message) : setSpeechError(message);
    },
  });

  async function selectMode(next: Mode): Promise<void> {
    modeSelectionRef.current += 1;
    if (speech.recognizing || speech.starting) {
      try { await speech.stop(); } catch { /* O texto já confirmado permanece. */ }
    }
    modeRef.current = next;
    setMode(next);
    setStatus("");
  }

  useEffect(() => {
    const wasActive = activeRef.current;
    activeRef.current = active;

    if (!active) {
      if (wasActive) {
        speech.stop().catch(() => {
          setStatus("audio encerrado; o texto ja confirmado foi preservado");
        });
      }
      return;
    }

    if (modeRequestId !== handledModeRequestRef.current) {
      handledModeRequestRef.current = modeRequestId;
      selectMode(initialMode).catch(() => undefined);
    }
  }, [active, initialMode, modeRequestId]);

  async function toggleQuickSpeech(): Promise<void> {
    if (speech.starting) return;
    if (speech.recognizing) {
      await speech.stop();
      setStatus("áudio pausado — revise e envie");
      return;
    }
    const started = await speech.start();
    if (started) setStatus("ouvindo — fale como se estivesse mandando uma mensagem");
  }

  // O flush global fica em App; esta tela só atualiza o badge local no foco.
  useEffect(() => {
    let alive = true;
    const refreshPending = async () => {
      const [count, recusados] = await Promise.all([pendingCount(), rejectedCount()]);
      if (!alive) return;
      setPending(count);
      setRejected(recusados);
      // Best-effort: sem rede isto simplesmente não atualiza, e a fila local acima
      // continua sendo a informação que importa.
      try {
        const n = await contarCapturasFalhadas();
        if (alive) setFalhadasNoServidor(n);
      } catch {
        /* sem servidor não há o que dizer sobre a fila dele */
      }
    };
    refreshPending();
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") refreshPending();
    });
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const modeSelectionAtStart = modeSelectionRef.current;

    const applyRestoredDraft = (draft: ReadingDraft, message: string): void => {
      replaceDraft(draft);
      setBook(draft.book);
      setPageStart(draft.pageStart);
      setPageEnd(draft.pageEnd);
      setItems(draft.items);
      elapsedSecondsRef.current = draft.activeSeconds;
      setElapsedSeconds(draft.activeSeconds);
      setSessionStart(draft.startedAt);
      if (modeSelectionRef.current === modeSelectionAtStart) {
        modeRef.current = "leitura";
        setMode("leitura");
        setStatus(message);
      }
    };

    const restore = async () => {
      let draft: ReadingDraft | null = null;
      try {
        draft = await loadReadingDraft();
      } catch {
        // Storage corrompido nao bloqueia uma nova sessao.
      }
      if (!alive) return;

      if (draft) {
        applyRestoredDraft(
          draft,
          "sessão recuperada do aparelho — conferindo servidor",
        );
      }
      setReadingDraftReady(true);

      const draftRevisionBeforeRemote = draftRevisionRef.current;
      const formRevisionBeforeRemote = readingFormRevisionRef.current;
      let reconciled = false;
      // Se a sessão retomada estiver staged, o servidor devolve draft_md: mostramos
      // o preview em vez do editor e NÃO re-sincronizamos (buffer congelado → 409).
      let stagedPreview: string | null = null;
      try {
        const pendingRemote = await listPendingReadingSessions();
        if (!alive) return;
        if (
          draftRevisionRef.current !== draftRevisionBeforeRemote ||
          readingFormRevisionRef.current !== formRevisionBeforeRemote
        ) return;
        setServerPending(pendingRemote.sessions);
        if (draft) {
          const remote = pendingRemote.sessions.find(
            (session) => session.client_key === draft?.sessionKey,
          );
          if (remote) {
            const remoteDraft = draftFromRemote(remote);
            const remoteLast = remote.last_seq ?? remoteDraft.syncedSeq;
            const unsynced = draft.items.filter(
              (item) => item.seq > remoteLast && item.seq > draft!.syncedSeq,
            );
            draft = {
              ...draft,
              remoteId: remote.id,
              items: [...remoteDraft.items, ...unsynced],
              syncedSeq: remoteLast,
              updatedAt: Math.max(draft.updatedAt, Math.round(remote.updated * 1000)),
            };
            reconciled = true;
            stagedPreview = readingPreviewFromSession(remote);
          }
        }
        if (!draft && pendingRemote.sessions.length === 1) {
          draft = draftFromRemote(pendingRemote.sessions[0]);
          stagedPreview = readingPreviewFromSession(pendingRemote.sessions[0]);
        } else if (!draft && pendingRemote.sessions.length > 1) {
          if (modeSelectionRef.current === modeSelectionAtStart) {
            modeRef.current = "leitura";
            setMode("leitura");
            setStatus(
              `${pendingRemote.sessions.length} sessões pendentes — escolha uma para retomar`,
            );
          }
        }
      } catch {
        if (
          draft &&
          draftRef.current?.sessionKey === draft.sessionKey &&
          draftRevisionRef.current === draftRevisionBeforeRemote &&
          readingFormRevisionRef.current === formRevisionBeforeRemote
        ) {
          queueDraftSync(draft);
          if (modeSelectionRef.current === modeSelectionAtStart) {
            setStatus("sessão salva no aparelho — sincronização pendente");
          }
        }
        return;
      }
      if (!alive || !draft) return;
      // A resposta de restore nunca pode substituir uma sessao iniciada pelo usuario.
      if (
        draftRevisionRef.current !== draftRevisionBeforeRemote ||
        readingFormRevisionRef.current !== formRevisionBeforeRemote
      ) return;

      applyRestoredDraft(
        draft,
        stagedPreview !== null
          ? "preview recuperado — salve no vault ou rejeite para editar"
          : "sessão de leitura recuperada — revise e retome ou feche a nota",
      );
      if (stagedPreview !== null) setPreview(stagedPreview);
      try {
        if (reconciled) await mutateReadingDraft(draft);
        else await saveReadingDraft(draft);
      } catch {
        if (modeSelectionRef.current === modeSelectionAtStart) {
          setStatus("sessão recuperada do servidor — mantenha o app aberto enquanto salvo novamente");
        }
      }
      // Buffer staged fica congelado no servidor; re-sincronizar devolveria 409.
      if (stagedPreview === null) queueDraftSync(draft);
    };

    restore();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const draft = draftRef.current;
    if (!draft) return;
    const timer = setTimeout(() => {
      const current = draftRef.current;
      if (!current) return;
      if (
        current.book === book &&
        current.pageStart === pageStart &&
        current.pageEnd === pageEnd
      ) return;
      const next = {
        ...current,
        book,
        pageStart,
        pageEnd,
        updatedAt: Date.now(),
      };
      replaceDraft(next);
      saveReadingDraft(next).catch(() => {
        setStatus("não consegui atualizar o buffer local");
      });
    }, 250);
    return () => clearTimeout(timer);
  }, [book, pageStart, pageEnd]);

  useEffect(() => {
    if (sessionStart === null) {
      elapsedSecondsRef.current = 0;
      setElapsedSeconds(0);
      return;
    }
    const restored = draftRef.current?.activeSeconds ?? 0;
    elapsedSecondsRef.current = restored;
    setElapsedSeconds(restored);
  }, [sessionStart]);

  useEffect(() => {
    if (sessionStart === null || !active || mode !== "leitura") return;
    const timer = setInterval(() => {
      if (AppState.currentState !== "active" || compileLockRef.current) return;
      const nextSeconds = elapsedSecondsRef.current + 1;
      elapsedSecondsRef.current = nextSeconds;
      setElapsedSeconds(nextSeconds);
      if (nextSeconds % 5 !== 0) return;
      const current = draftRef.current;
      if (!current) return;
      const next = {
        ...current,
        activeSeconds: nextSeconds,
        updatedAt: Date.now(),
      };
      replaceDraft(next);
      saveReadingDraft(next).catch(() => {
        if (draftRef.current?.sessionKey === next.sessionKey) {
          setStatus("não consegui atualizar o tempo local");
        }
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [active, mode, sessionStart]);

  // O escaninho precisa de saída: um badge vermelho que nunca volta a zero é ruído,
  // e conteúdo guardado que ninguém consegue ler é perda com outro nome.
  async function verRecusados() {
    const recusados = await listRejected();
    if (!recusados.length) {
      setRejected(0);
      return;
    }
    const ids = recusados.map((r) => r.id);
    const previa = recusados
      .slice(0, 3)
      .map((r) => `• ${String(r.item.payload?.text ?? r.item.kind).slice(0, 60)}`)
      .join("\n");
    const resto = recusados.length > 3 ? `\n… e mais ${recusados.length - 3}` : "";
    Alert.alert(
      `${recusados.length} não saíram`,
      `O servidor recusou estes. Nenhum reenvio automático resolve.\n\n${previa}${resto}`,
      [
        { text: "Deixar aí", style: "cancel" },
        {
          text: "Tentar de novo",
          onPress: async () => {
            // `flush()` logo em seguida, senão "tentar de novo" não tentava nada:
            // trocava o badge vermelho por um azul e prometia um reenvio que só
            // aconteceria no próximo foco da tela. O flush é serializado, então
            // chamá-lo aqui é seguro.
            const devolvidos = await retryRejected(ids);
            const { restantes } = await flush();
            setPending(await pendingCount());
            setRejected(await rejectedCount());
            setStatus(
              `${devolvidos} devolvido(s) à fila · ${devolvidos - restantes > 0 ? devolvidos - restantes : 0} saíram`,
            );
          },
        },
        {
          text: "Descartar",
          style: "destructive",
          onPress: async () => {
            // Só os ids que o alerta mostrou: um item que caísse no escaninho entre
            // abrir o alerta e tocar aqui seria apagado sem nunca ter sido visto.
            await discardRejected(ids);
            setRejected(await rejectedCount());
          },
        },
      ],
    );
  }

  async function onSend() {
    const t = text.trim();
    if (!t) return;

    const ts = Date.now();
    const clientKey = createCaptureClientKey(ts);

    setBusy(true);
    setStatus("");
    // O toast anterior sai de cena antes do envio novo. Sem isto ele ficava na tela
    // pelo resto da sessão — junto com o literal "agora", que envelhecia mentindo.
    setReply("");

    const guardarNaFila = async (motivo: "rede" | "login" = "rede") => {
      // A mesma client_key usada no primeiro POST acompanha o retry. Se o BFF
      // recebeu a captura e só a resposta se perdeu, ele devolve o id existente.
      await enqueue({
        kind: "capture",
        payload: { text: t, client_key: clientKey, sensivel: sensitive },
        ts,
      });
      setText("");
      setSensitive(false);
      setPending(await pendingCount());
      // O texto nunca se perde nos dois casos, mas a frase muda: no 401 nenhum
      // reenvio automático vai acontecer enquanto ele não entrar de novo, e dizer
      // "sem conexão" ali seria prometer um reenvio que não vem.
      setStatus(
        motivo === "login"
          ? "sessão expirada — guardado no aparelho; entre de novo pra enviar"
          : "sem conexão — guardado no aparelho, reenvio automático",
      );
    };

    try {
      // Drena antes pra manter a ordem: uma captura nova não pode passar na frente
      // do que já estava esperando. Mas o desvio pra fila agora depende de `semSaida`,
      // não de `restantes > 0` — a fila também pode ter sobra com a rede boa (itens
      // que o servidor recusou), e nesse caso mandar a captura nova pra fila era
      // enterrá-la atrás de um item que nunca sai, mentindo "sem conexão".
      const { parou, rejeitados } = await flush();
      if (rejeitados > 0) {
        // O badge vermelho so era recalculado no foco da tela: sem isto, um item
        // abandonado AGORA sumia do contador de pendentes e nada aparecia no lugar,
        // e a queda do numero se lia como entrega.
        setRejected(await rejectedCount());
      }
      if (parou) {
        await guardarNaFila(parou);
        return;
      }

      const r = await capture(t, undefined, clientKey, sensitive);
      setReply(r);
      // E some sozinho: um recibo é um instante, não um estado da tela.
      if (replyTimer.current) clearTimeout(replyTimer.current);
      replyTimer.current = setTimeout(() => setReply(""), 6000);
      setText("");
      setSensitive(false);
      setPending(await pendingCount());
    } catch (error) {
      if (ehFalhaDeRede(error)) {
        await guardarNaFila();
        return;
      }
      // O servidor RESPONDEU e recusou. Enfileirar aqui era o defeito: 401 e 404
      // nunca melhoram sozinhos, e o 500 pode ter gravado do outro lado — reenviar
      // às cegas duplica. O texto fica na caixa, que é o único lugar onde ele não
      // se perde sem o Leo saber.
      setStatus(mensagemDaRecusa(error));
    } finally {
      setBusy(false);
    }
  }

  function queueDraftSync(
    draft: ReadingDraft,
    localSave: Promise<void> = Promise.resolve(),
  ): void {
    syncChain.current = syncChain.current
      .then(async () => {
        await localSave;
        await syncDraft(draft);
      })
      .catch((error) => {
        if (draftRef.current?.sessionKey !== draft.sessionKey) return;
        // O createReadingSession deste sync pode achar a obra terminada (409)
        // entre a escolha na estante e o autosave — a obra some da estante nesse
        // meio-tempo, ou foi terminada em outro lugar. Não é falha de rede.
        if (readingErrorDetail(error) === "book_nao_aceita_sessao") {
          limparSelecaoDeObraTerminada();
          setSpeechError("essa obra foi terminada — reabra antes de ler");
          return;
        }
        setStatus("sessão salva no aparelho — autosave no servidor pendente");
      });
  }

  async function restoreRemote(session: ReadingSession): Promise<void> {
    if (draftRef.current) return;
    const draftRevision = draftRevisionRef.current;
    const formRevision = readingFormRevisionRef.current;
    setStatus("confirmando sessão no servidor…");
    let fresh: ReadingSession;
    try {
      fresh = (await getReadingSession(session.id)).session;
    } catch {
      setStatus("não consegui confirmar esta sessão — tente novamente");
      return;
    }
    if (
      draftRef.current ||
      draftRevisionRef.current !== draftRevision ||
      readingFormRevisionRef.current !== formRevision
    ) return;
    if (fresh.status !== "pending") {
      setServerPending((previous) =>
        previous.filter((candidate) => candidate.id !== session.id),
      );
      setStatus(
        fresh.status === "compiled"
          ? "esta nota já foi fechada"
          : fresh.status === "discarded"
            ? "esta sessão já foi descartada"
            : "esta sessão está sendo processada no servidor",
      );
      return;
    }
    const draft = draftFromRemote(fresh);
    replaceDraft(draft);
    setBook(draft.book);
    setPageStart(draft.pageStart);
    setPageEnd(draft.pageEnd);
    setItems(draft.items);
    elapsedSecondsRef.current = draft.activeSeconds;
    setElapsedSeconds(draft.activeSeconds);
    setSessionStart(draft.startedAt);
    const stagedPreview = readingPreviewFromSession(fresh);
    if (stagedPreview !== null) {
      setPreview(stagedPreview);
      setStatus("preview recuperado — salve no vault ou rejeite para editar");
    } else {
      setStatus("sessão pendente aberta — retome ou feche a nota");
    }
    await saveReadingDraft(draft);
  }

  async function syncDraft(snapshot: ReadingDraft): Promise<number> {
    let remoteId = snapshot.remoteId;
    if (remoteId === null) {
      const created = await createReadingSession({
        client_key: snapshot.sessionKey,
        livro: snapshot.book,
        book_id: snapshot.bookId,
        pagina_inicial: numericPage(snapshot.pageStart),
        inicio: snapshot.startedAt / 1000,
      });
      remoteId = created.session.id;
      const current = draftRef.current;
      if (current?.sessionKey === snapshot.sessionKey) {
        const withRemote = { ...current, remoteId };
        replaceDraft(withRemote);
        await saveReadingDraft(withRemote);
      }
    }

    const currentConfirmed =
      draftRef.current?.sessionKey === snapshot.sessionKey
        ? draftRef.current.syncedSeq
        : snapshot.syncedSeq;
    let confirmedSeq = currentConfirmed;
    for (const item of snapshot.items) {
      if (item.seq <= currentConfirmed) continue;
      await appendReadingBuffer(remoteId, {
        seq: item.seq,
        hook: kindToHook(item.kind),
        texto: item.text,
        ts: snapshot.updatedAt / 1000,
      });
      confirmedSeq = item.seq;
    }
    const current = draftRef.current;
    if (
      current?.sessionKey === snapshot.sessionKey &&
      confirmedSeq > current.syncedSeq
    ) {
      const synced = { ...current, remoteId, syncedSeq: confirmedSeq };
      replaceDraft(synced);
      await saveReadingDraft(synced);
    }
    return remoteId;
  }

  function appendTranscript(raw: string): void {
    if (compileLockRef.current) {
      setSpeechError("aguarde a nota terminar de fechar — a fala não foi adicionada");
      return;
    }
    const parsed = parseReadingEntry(raw);
    if (parsed.book) {
      if (draftRef.current) {
        setSpeechError("o livro não muda depois que a sessão começou");
        return;
      }
      setBook(parsed.book);
      return;
    }
    if (!parsed.text) return;

    const current = draftRef.current;
    if (!current) {
      setEntry(raw);
      setSpeechError("inicie a sessão antes de registrar uma fala");
      return;
    }
    const seq = (current.items.at(-1)?.seq ?? 0) + 1;
    const item: Item = {
      id: `${current.sessionKey}:${seq}`,
      kind: parsed.kind ?? "comentário",
      text: parsed.text,
      seq,
    };
    const next: ReadingDraft = {
      ...current,
      book,
      pageStart,
      pageEnd,
      items: [...current.items, item],
      updatedAt: Date.now(),
      status: "active",
    };
    replaceDraft(next);
    setItems(next.items);
    const localSave = saveReadingDraft(next);
    queueDraftSync(next, localSave);
    localSave.catch(() =>
      setStatus("não consegui gravar o buffer local"),
    );
  }

  async function onAdd() {
    if (compileLockRef.current) return;
    const raw = entry.trim();
    if (!raw) return;
    if (editingSeq !== null) {
      const parsed = parseReadingEntry(raw);
      if (!parsed.text || parsed.book) {
        setStatus("escreva o conteúdo corrigido do registro");
        return;
      }
      const current = draftRef.current;
      const last = current?.items.at(-1);
      if (!current || !last || last.seq !== editingSeq) {
        setEditingSeq(null);
        setStatus("o buffer mudou — abra a correção novamente");
        return;
      }
      setEditingBusy(true);
      try {
        if (speech.starting) {
          setStatus("aguarde o microfone iniciar antes de corrigir");
          return;
        }
        if (speech.recognizing) await speech.stop();
        compileLockRef.current = true;
        await syncChain.current;
        const fresh = draftRef.current;
        const remoteId = fresh?.remoteId;
        if (!fresh || remoteId == null || fresh.items.at(-1)?.seq !== editingSeq) {
          throw new Error("sessão ainda não sincronizada");
        }
        const remote = (await getReadingSession(remoteId)).session;
        const remoteTail = (remote.buffer ?? []).at(-1);
        if (!remoteTail || remoteTail.seq !== editingSeq) {
          throw new Error("cauda remota mudou");
        }
        await updateLastReadingBuffer(remoteId, editingSeq, {
          expected_chunk_id: remoteTail.chunk_id,
          hook: kindToHook(parsed.kind ?? "comentário"),
          texto: parsed.text,
        });
        const next: ReadingDraft = {
          ...fresh,
          items: fresh.items.map((item) => item.seq === editingSeq
            ? { ...item, kind: parsed.kind ?? "comentário", text: parsed.text }
            : item),
          updatedAt: Date.now(),
        };
        try {
          await mutateReadingDraft(next);
        } catch {
          replaceDraft(next);
          setItems(next.items);
          setStatus("servidor confirmou; a cópia local será reconciliada ao reabrir");
          return;
        }
        replaceDraft(next);
        setItems(next.items);
        setEntry("");
        setEditingSeq(null);
        setStatus("último registro corrigido");
      } catch {
        setStatus("não confirmei a correção — toque em adicionar para tentar novamente");
      } finally {
        compileLockRef.current = false;
        setEditingBusy(false);
      }
      return;
    }
    appendTranscript(raw);
    setEntry("");
  }

  function editLast(item: Item): void {
    if (compileLockRef.current || item.seq !== items.at(-1)?.seq) return;
    setEditingSeq(item.seq);
    setEntry(`${item.kind}: ${item.text}`);
    setStatus("corrigindo o último registro");
  }

  async function removeLast(item: Item): Promise<void> {
    if (compileLockRef.current || item.seq !== items.at(-1)?.seq) return;
    setEditingBusy(true);
    try {
      if (speech.starting) {
        setStatus("aguarde o microfone iniciar antes de remover");
        return;
      }
      if (speech.recognizing) await speech.stop();
      compileLockRef.current = true;
      await syncChain.current;
      const fresh = draftRef.current;
      const remoteId = fresh?.remoteId;
      if (!fresh || remoteId == null || fresh.items.at(-1)?.seq !== item.seq) {
        throw new Error("sessão ainda não sincronizada");
      }
      const remote = (await getReadingSession(remoteId)).session;
      const remoteTail = (remote.buffer ?? []).at(-1);
      if (remoteTail?.seq === item.seq) {
        await deleteLastReadingBuffer(remoteId, item.seq, remoteTail.chunk_id);
      } else if (remote.last_seq !== item.seq - 1) {
        throw new Error("cauda remota mudou");
      }
      const next: ReadingDraft = {
        ...fresh,
        items: fresh.items.slice(0, -1),
        syncedSeq: Math.min(fresh.syncedSeq, item.seq - 1),
        updatedAt: Date.now(),
      };
      try {
        await mutateReadingDraft(next);
      } catch {
        replaceDraft(next);
        setItems(next.items);
        setStatus("servidor confirmou; a cópia local será reconciliada ao reabrir");
        return;
      }
      replaceDraft(next);
      setItems(next.items);
      setEditingSeq(null);
      setRemoveConfirmSeq(null);
      setEntry("");
      setStatus("último registro removido");
    } catch {
      setStatus("não confirmei a remoção — use remover para tentar novamente");
    } finally {
      compileLockRef.current = false;
      setEditingBusy(false);
    }
  }

  function numericPage(value: string): number | null {
    if (!value.trim()) return null;
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 0 ? parsed : null;
  }

  // `novaObra` chega de `criarObra` quando a sessão nasce em modo "novo livro".
  // `book`/`selectedBookId` só refletem essa criação depois de um novo render, e
  // esta função roda no mesmo tick — por isso o valor entra por parâmetro, não
  // por state, e não corre atrás de uma obra que a tela ainda não sabe que existe.
  async function ensureSession(
    novaObra?: { id: number; titulo: string },
  ): Promise<ReadingDraft | null> {
    if (speech.starting || compileLockRef.current) return null;
    setSpeechError("");
    let draft = draftRef.current;
    if (!draft) {
      const titulo = novaObra?.titulo ?? book;
      if (!titulo.trim()) {
        setSpeechError("informe o livro antes de iniciar a sessão");
        return null;
      }
      const now = Date.now();
      draft = {
        sessionKey: createSessionKey(now),
        remoteId: null,
        book: titulo,
        bookId: novaObra ? novaObra.id : selectedBookId,
        pageStart,
        pageEnd,
        startedAt: now,
        activeSeconds: 0,
        updatedAt: now,
        items: [],
        syncedSeq: 0,
        status: "active",
      };
      replaceDraft(draft);
      setSessionStart(now);
      await saveReadingDraft(draft);
      queueDraftSync(draft);
    }
    return draft;
  }

  async function beginSession(): Promise<void> {
    // Em modo "novo livro" a obra precisa existir no servidor antes da sessão —
    // senão a sessão nasce sem `book_id` e a estante nunca aprende sobre ela.
    // Só falta criar enquanto NÃO há sessão ainda: uma vez que `ensureSession`
    // gerou o draft, ele é quem decide se recria (não decide, reusa). Sem o
    // `!draftRef.current`, `newBookMode` fica true a sessão inteira e cada
    // toque no microfone (`startSession` de novo) chamaria `criarObra` outra
    // vez — round-trip à toa e, offline, `criarObra` falha e o microfone
    // simplesmente não liga, sem pista do porquê.
    const novaObra =
      newBookMode && !draftRef.current ? await criarObra() : undefined;
    if (novaObra === null) return; // criarObra falhou; o erro já está em speechError
    const draft = await ensureSession(novaObra ?? undefined);
    if (draft) setStatus("sessão iniciada — escreva ou ative o microfone quando quiser");
  }

  async function startSession(): Promise<void> {
    const novaObra =
      newBookMode && !draftRef.current ? await criarObra() : undefined;
    if (novaObra === null) return;
    const draft = await ensureSession(novaObra ?? undefined);
    if (!draft) return;
    const started = await speech.start();
    if (started) setStatus("ouvindo — diga ‘citação’, ‘comentário’, ‘ideia’ ou ‘lista’");
  }

  async function stopSpeech(): Promise<void> {
    try {
      await speech.stop();
      setStatus("áudio pausado — o buffer continua salvo");
    } catch {
      setStatus("o microfone não confirmou a pausa — buffer preservado");
    }
  }

  function resetSessionUi(): void {
    replaceDraft(null);
    setSessionStart(null);
    elapsedSecondsRef.current = 0;
    setElapsedSeconds(0);
    setItems([]);
    setBook("");
    setSelectedBookId(null);
    setPageStart("");
    setPageEnd("");
    setEntry("");
    setEditingSeq(null);
    setRemoveConfirmSeq(null);
    setSpeechError("");
    setPreview(null);
    setNewBookMode(false);
    // A sessão que acabou de compilar pode ter mudado a página/data da obra no
    // servidor; sem isto a estante ficaria mostrando o estado de antes da leitura.
    void loadShelf();
  }

  function readingSnapshot(draft: ReadingDraft): ReadingSnapshot {
    return {
      client_key: draft.sessionKey,
      livro: draft.book,
      pagina_inicial: numericPage(draft.pageStart),
      pagina_final: numericPage(draft.pageEnd),
      buffer: draft.items.map((item) => ({
        seq: item.seq,
        hook: kindToHook(item.kind),
        texto: item.text,
      })),
    };
  }

  function draftMatchesSnapshot(
    draft: ReadingDraft | null,
    snapshot: ReadingSnapshot,
  ): boolean {
    if (
      !draft ||
      draft.sessionKey !== snapshot.client_key ||
      draft.book !== snapshot.livro ||
      numericPage(draft.pageStart) !== snapshot.pagina_inicial ||
      numericPage(draft.pageEnd) !== snapshot.pagina_final ||
      draft.items.length !== snapshot.buffer.length
    ) {
      return false;
    }
    return draft.items.every((item, index) => {
      const expected = snapshot.buffer[index];
      return (
        item.seq === expected.seq &&
        kindToHook(item.kind) === expected.hook &&
        item.text === expected.texto
      );
    });
  }

  function confirmLegacyCleanup(session: ReadingSession): Promise<boolean> {
    return new Promise((resolve) => {
      const ref = session.vault_path
        ? `Nota confirmada no vault: ${session.vault_path}.`
        : "O servidor confirma que a nota já foi fechada.";
      Alert.alert(
        "Nota já fechada",
        `${ref} Esta sessão é anterior à verificação automática por hash. Remover apenas a cópia local?`,
        [
          { text: "Manter local", style: "cancel", onPress: () => resolve(false) },
          { text: "Remover cópia local", onPress: () => resolve(true) },
        ],
        { cancelable: false },
      );
    });
  }

  async function finishLocalCompile(
    snapshot: ReadingSnapshot,
    remoteId: number,
    ankiCards: unknown[],
    ankiStatus: "pending" | "done",
    legacy = false,
  ): Promise<boolean> {
    if (!draftMatchesSnapshot(draftRef.current, snapshot)) {
      Alert.alert(
        "Resultado salvo",
        "O rascunho local mudou durante a operação e foi preservado para revisão.",
      );
      return false;
    }
    if (!legacy && ankiStatus === "pending") {
      setStatus("nota gravada — sugestão Anki pendente, toque em Salvar no vault para tentar novamente");
      Alert.alert(
        "Nota gravada",
        "O vault confirmou a nota, mas a sugestão Anki ficou pendente. O rascunho foi preservado para um retry seguro.",
      );
      return false;
    }
    await clearReadingDraft();
    setServerPending((previous) =>
      previous.filter((session) => session.id !== remoteId),
    );
    resetSessionUi();
    Alert.alert(
      legacy ? "Cópia local removida" : "Nota fechada",
      legacy
        ? "A nota já estava gravada no servidor; nada foi refeito."
        : ankiCards.length > 0
          ? `${ankiCards.length} candidato(s) Anki aguardam revisão.`
          : "Nota gravada. Nenhum candidato Anki foi sugerido.",
    );
    return true;
  }

  async function reconcileExisting(
    snapshot: ReadingSnapshot,
    remoteId: number,
  ): Promise<"pending" | "handled"> {
    const { session } = await getReadingSession(remoteId);
    if (session.status === "pending") return "pending";
    if (session.status === "compiling") {
      throw new ReadingApiError(409, "reading_compile_em_andamento");
    }
    if (session.status === "discarded") {
      throw new ReadingApiError(409, "reading_session_descartada");
    }
    if (!session.source_digest) {
      const lastSeq = snapshot.buffer.at(-1)?.seq ?? 0;
      if (
        session.client_key !== snapshot.client_key ||
        session.livro !== snapshot.livro ||
        session.pagina_inicial !== snapshot.pagina_inicial ||
        session.pagina_final !== snapshot.pagina_final ||
        session.last_seq !== lastSeq
      ) {
        throw new ReadingApiError(409, "reading_compiled_snapshot_divergente");
      }
      const confirmed = await confirmLegacyCleanup(session);
      if (confirmed) {
        await finishLocalCompile(snapshot, remoteId, [], "done", true);
      } else {
        setStatus("nota já fechada — cópia local mantida por sua escolha");
      }
      return "handled";
    }

    const reconciled: ReadingReconcileResult = await reconcileReadingSession(
      remoteId,
      snapshot,
    );
    if (!reconciled.matched) {
      throw new ReadingApiError(409, "reading_compiled_snapshot_divergente");
    }
    const result = await compileReadingSession(remoteId, {
      pagina_final: snapshot.pagina_final,
      fim: Date.now() / 1000,
      duracao_s: elapsedSecondsRef.current,
    });
    await finishLocalCompile(
      snapshot,
      remoteId,
      result.anki_cards,
      result.anki_status,
    );
    return "handled";
  }

  async function approveNow(): Promise<void> {
    const draft = draftRef.current;
    if (!draft || compileLockRef.current || draft.items.length === 0) return;
    compileLockRef.current = true;
    setCompiling(true);
    setStatus("salvando no vault — o buffer só será limpo após o vault confirmar");
    try {
      const pendingDraft = {
        ...draft,
        book,
        pageStart,
        pageEnd,
        status: "pending" as const,
        updatedAt: Date.now(),
      };
      const snapshot = readingSnapshot(pendingDraft);
      replaceDraft(pendingDraft);
      await saveReadingDraft(pendingDraft);
      if (
        pendingDraft.remoteId !== null &&
        await reconcileExisting(snapshot, pendingDraft.remoteId) === "handled"
      ) {
        return;
      }
      let remoteId: number;
      try {
        remoteId = await syncDraft(pendingDraft);
      } catch (error) {
        if (
          (draftRef.current?.remoteId ?? pendingDraft.remoteId) !== null &&
          readingErrorDetail(error) === "reading_session_nao_editavel"
        ) {
          const recoveredRemoteId = draftRef.current?.remoteId ?? pendingDraft.remoteId;
          if (recoveredRemoteId === null) throw error;
          if (
            await reconcileExisting(snapshot, recoveredRemoteId) === "handled"
          ) {
            return;
          }
          throw error;
        } else {
          throw error;
        }
      }
      const result = await compileReadingSession(remoteId, {
        pagina_final: numericPage(pageEnd),
        fim: Date.now() / 1000,
        duracao_s: elapsedSecondsRef.current,
      });
      const reconciled = await reconcileReadingSession(remoteId, snapshot);
      if (!reconciled.matched) {
        throw new ReadingApiError(409, "reading_compiled_snapshot_divergente");
      }
      await finishLocalCompile(
        snapshot,
        remoteId,
        result.anki_cards,
        result.anki_status,
      );
    } catch (error) {
      const current = draftRef.current;
      if (current) {
        const pendingDraft = {
          ...current,
          status: "pending" as const,
          updatedAt: Date.now(),
        };
        replaceDraft(pendingDraft);
        await saveReadingDraft(pendingDraft);
      }
      const detail = readingErrorDetail(error);
      if (detail === "reading_draft_ausente") {
        // O rascunho sumiu no servidor (rejeitado/expirado): o buffer voltou a
        // ser editável. Fecha o preview e devolve o editor cru para re-gerar.
        setPreview(null);
        setStatus("o preview expirou no servidor — feche a nota de novo para gerar outro");
        Alert.alert(
          "Preview indisponível",
          "O servidor não tem mais o rascunho desta sessão. Ele foi liberado para edição; toque em Fechar a nota para gerar um novo preview.",
        );
        return;
      }
      if (detail === "reading_draft_desatualizado") {
        // O preview ficou aberto no aparelho de um formato antigo (sem
        // frontmatter) até este deploy subir. O digest ainda bate, mas publicar
        // assim sairia sem frontmatter — por isso o servidor recusa. Mesma saída
        // do draft ausente: soltar o preview e compilar de novo regenera via
        // /draft já no formato atual.
        setPreview(null);
        setStatus("o preview ficou desatualizado — feche a nota de novo para gerar outro");
        Alert.alert(
          "Preview desatualizado",
          "Este preview foi gerado num formato antigo. Ele foi liberado para edição; toque em Fechar a nota para gerar um novo preview.",
        );
        return;
      }
      if (detail === "book_nao_aceita_sessao") {
        // syncDraft() só tenta criar a sessão no servidor aqui se ela nunca foi
        // criada antes (sessão inteira feita offline, por ex.) — e a esta altura
        // a obra já foi terminada. O buffer local com tudo que foi registrado
        // continua intacto; reabrir a obra é o que destrava o retry.
        limparSelecaoDeObraTerminada();
        setStatus("essa obra foi terminada — reabra na estante antes de salvar esta sessão");
        Alert.alert(
          "Obra terminada",
          "A obra desta sessão foi marcada como terminada. Reabra-a na estante e toque em Salvar no vault de novo — nada do que você registrou foi perdido.",
        );
        return;
      }
      const message =
        detail === "reading_compile_em_andamento"
          ? "A nota ainda está sendo fechada no servidor. A sessão foi preservada."
          : detail === "reading_compiled_snapshot_divergente"
            ? "O resultado salvo não corresponde ao rascunho deste aparelho. A cópia local foi preservada para revisão."
          : detail === "reading_session_descartada"
            ? "O servidor informa que esta sessão já foi descartada. O rascunho local foi preservado."
            : "A sessão foi preservada para tentar novamente.";
      setStatus("não consegui salvar no vault — sessão preservada, nada foi apagado");
      Alert.alert(
        "Não foi possível salvar no vault",
        message,
      );
    } finally {
      compileLockRef.current = false;
      setCompiling(false);
    }
  }

  // "Compilar" agora gera o preview (staged) em vez de gravar. Espelha o prelúdio
  // de approveNow, mas troca compileReadingSession por draftReadingSession e para
  // no preview — sem finishLocalCompile, mantendo o rascunho local.
  async function stageNow(): Promise<void> {
    const draft = draftRef.current;
    if (!draft || compileLockRef.current || draft.items.length === 0) return;
    compileLockRef.current = true;
    setCompiling(true);
    setStatus("gerando preview — nada será gravado no vault ainda");
    try {
      const pendingDraft = {
        ...draft,
        book,
        pageStart,
        pageEnd,
        status: "pending" as const,
        updatedAt: Date.now(),
      };
      const snapshot = readingSnapshot(pendingDraft);
      replaceDraft(pendingDraft);
      await saveReadingDraft(pendingDraft);
      if (
        pendingDraft.remoteId !== null &&
        await reconcileExisting(snapshot, pendingDraft.remoteId) === "handled"
      ) {
        return;
      }
      let remoteId: number;
      try {
        remoteId = await syncDraft(pendingDraft);
      } catch (error) {
        if (
          (draftRef.current?.remoteId ?? pendingDraft.remoteId) !== null &&
          readingErrorDetail(error) === "reading_session_nao_editavel"
        ) {
          const recoveredRemoteId = draftRef.current?.remoteId ?? pendingDraft.remoteId;
          if (recoveredRemoteId === null) throw error;
          if (
            await reconcileExisting(snapshot, recoveredRemoteId) === "handled"
          ) {
            return;
          }
          throw error;
        } else {
          throw error;
        }
      }
      const result = await draftReadingSession(remoteId, {
        pagina_final: numericPage(pageEnd),
      });
      setPreview(result.draft_md);
      setStatus("preview pronto — revise e salve no vault, ou rejeite para editar");
    } catch (error) {
      const current = draftRef.current;
      if (current) {
        const pendingDraft = {
          ...current,
          status: "pending" as const,
          updatedAt: Date.now(),
        };
        replaceDraft(pendingDraft);
        await saveReadingDraft(pendingDraft);
      }
      const detail = readingErrorDetail(error);
      if (detail === "reading_draft_desatualizado") {
        // Mesmo caso de approveNow — ver o comentário lá. Aqui só por simetria:
        // /draft sempre regenera no formato atual, então esta rota não é
        // alcançável pelo servidor hoje, mas tratar do mesmo jeito custa nada.
        setPreview(null);
        setStatus("o preview ficou desatualizado — feche a nota de novo para gerar outro");
        Alert.alert(
          "Preview desatualizado",
          "Este preview foi gerado num formato antigo. Ele foi liberado para edição; toque em Fechar a nota para gerar um novo preview.",
        );
        return;
      }
      if (detail === "book_nao_aceita_sessao") {
        // Mesmo caso de approveNow: a obra terminou antes da primeira sessão
        // no servidor existir. O buffer local segue intacto.
        limparSelecaoDeObraTerminada();
        setStatus("essa obra foi terminada — reabra na estante antes de gerar o preview");
        Alert.alert(
          "Obra terminada",
          "A obra desta sessão foi marcada como terminada. Reabra-a na estante e toque em Fechar a nota de novo — nada do que você registrou foi perdido.",
        );
        return;
      }
      const message =
        detail === "reading_compile_indisponivel"
          ? "O gerador da nota está indisponível agora. Nada foi gravado; tente novamente em instantes."
          : detail === "pagina_final_invalida"
            ? "A página final precisa ser maior ou igual à inicial."
          : detail === "reading_compile_em_andamento"
            ? "A nota ainda está sendo fechada no servidor. A sessão foi preservada."
          : detail === "reading_session_descartada"
            ? "O servidor informa que esta sessão já foi descartada. O rascunho local foi preservado."
            : "A sessão foi preservada para tentar novamente.";
      setStatus("não consegui gerar o preview — sessão preservada, nada foi gravado");
      Alert.alert(
        "Não foi possível gerar o preview",
        message,
      );
    } finally {
      compileLockRef.current = false;
      setCompiling(false);
    }
  }

  // "Rejeitar": limpa o rascunho no servidor e devolve o buffer à edição.
  async function rejectNow(): Promise<void> {
    if (compileLockRef.current) {
      setStatus("aguarde a operação atual terminar antes de rejeitar");
      return;
    }
    const remoteId = draftRef.current?.remoteId ?? null;
    compileLockRef.current = true;
    setCompiling(true);
    try {
      if (remoteId !== null) {
        await rejectReadingDraft(remoteId);
      }
      setPreview(null);
      const current = draftRef.current;
      if (current) {
        const editable = {
          ...current,
          status: "active" as const,
          updatedAt: Date.now(),
        };
        replaceDraft(editable);
        await saveReadingDraft(editable);
      }
      setStatus("rascunho rejeitado — edite e feche a nota de novo");
    } catch (error) {
      const detail = readingErrorDetail(error);
      const message =
        detail === "reading_compile_em_andamento"
          ? "A nota está sendo processada no servidor agora. Aguarde e tente rejeitar de novo."
          : detail === "reading_session_compiled"
            ? "Esta sessão já foi salva no vault; não há mais rascunho para rejeitar."
            : "O rascunho foi preservado; tente rejeitar novamente.";
      setStatus("não consegui rejeitar o rascunho — nada foi alterado");
      Alert.alert(
        "Não foi possível rejeitar",
        message,
      );
    } finally {
      compileLockRef.current = false;
      setCompiling(false);
    }
  }

  async function compilar(): Promise<void> {
    if (speech.starting) {
      setStatus("aguarde o microfone iniciar antes de fechar a nota");
      return;
    }
    if (speech.recognizing) {
      setStatus("finalizando a última fala…");
      try {
        await speech.stop();
      } catch {
        setStatus("não confirmei o fim do áudio — buffer preservado");
        return;
      }
    }
    await syncChain.current;
    await stageNow();
  }

  function descartar(): void {
    if (compileLockRef.current) {
      setStatus("aguarde a operação atual terminar antes de descartar");
      return;
    }
    const draft = draftRef.current;
    if (!draft) return;
    Alert.alert(
      "Descartar sessão?",
      "O buffer local e a sessão pendente serão removidos.",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Descartar",
          style: "destructive",
          onPress: async () => {
            if (compileLockRef.current) {
              setStatus("aguarde a operação atual terminar");
              return;
            }
            compileLockRef.current = true;
            setCompiling(true);
            let detachedDraft: ReadingDraft | null = null;
            try {
              if (speech.starting) {
                setStatus("aguarde o microfone iniciar antes de descartar");
                return;
              }
              if (speech.recognizing) await speech.stop();
              // O descarte explicito supera autosaves antigos. Create e append
              // sao idempotentes/serializados no servidor; uma cauda atrasada
              // recebe o estado discarded e nao ressuscita a sessao local.
              syncChain.current = Promise.resolve();
              const current = draftRef.current;
              if (!current) return;
              detachedDraft = current;
              // Invalida a geracao antes de qualquer await remoto. Autosaves que
              // terminarem atrasados nao encontram mais esta sessao para regravar.
              replaceDraft(null);
              let remoteId = current.remoteId;
              if (remoteId === null) {
                try {
                  const recovered = await createReadingSession({
                    client_key: current.sessionKey,
                    livro: current.book,
                    book_id: current.bookId,
                    pagina_inicial: numericPage(current.pageStart),
                    inicio: current.startedAt / 1000,
                  });
                  remoteId = recovered.session.id;
                } catch (error) {
                  // O servidor recusou criar a sessão (ex.: a obra terminou antes
                  // do primeiro sync) — uma sessão que ele nunca teve é uma sessão
                  // que ele não precisa descartar. remoteId fica null, o guard
                  // abaixo pula o discard, e o descarte vira só local.
                  if (!canClearLocalAfterDiscardFailure(readingErrorDetail(error))) {
                    throw error;
                  }
                }
              }
              if (remoteId !== null) {
                try {
                  await discardReadingSession(remoteId);
                } catch (error) {
                  // Se a nota ja foi compilada ou a sessao ja terminou no servidor,
                  // a confirmacao explicita remove somente a copia local obsoleta.
                  if (!canClearLocalAfterDiscardFailure(readingErrorDetail(error))) {
                    throw error;
                  }
                }
                setServerPending((previous) =>
                  previous.filter((session) => session.id !== remoteId),
                );
              }
              await clearReadingDraft();
              resetSessionUi();
              setStatus("sessão removida deste aparelho");
            } catch {
              if (detachedDraft && draftRef.current === null) {
                replaceDraft(detachedDraft);
              }
              setStatus("não confirmei o descarte no servidor — sessão preservada");
            } finally {
              compileLockRef.current = false;
              setCompiling(false);
            }
          },
        },
      ],
    );
  }

  const readingKinds = [
    ["citação", "book-open", colors.primary],
    ["comentário", "message-square", colors.textMuted],
    ["ideia", "zap", colors.lilac],
    ["lista", "list", colors.success],
  ] as const;

  // Enquanto há preview staged (ou uma operação em curso) a edição fica congelada,
  // batendo com o congelamento do buffer no servidor.
  const frozen = compiling || preview !== null;

  return (
    <View style={styles.screen}>
      <View style={styles.modebar}>
        {(["captura", "leitura"] as Mode[]).map((itemMode) => {
          const active = mode === itemMode;
          return (
            <Pressable
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              key={itemMode}
              onPress={() => selectMode(itemMode)}
              style={[styles.mode, active && styles.modeOn]}
            >
              <Feather
                name={itemMode === "captura" ? "inbox" : "book-open"}
                size={15}
                color={active ? colors.text : colors.textMuted}
              />
              <Text style={[styles.modeTxt, active && styles.modeTxtOn]}>
                {itemMode === "captura" ? "Captura rápida" : "Leitura"}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {mode === "captura" ? (
        <ScrollView
          contentContainerStyle={styles.captureContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.crumb}>captura universal</Text>

          <Card style={styles.captureCard}>
            <Field
              style={styles.input}
              value={text}
              onChangeText={setText}
              placeholder="Ex.: cobrar a Ana pelo relatório na sexta"
              multiline
              autoFocus={false}
            />
            {speech.interim ? <Text style={styles.interim}>“{speech.interim}”</Text> : null}
            <View style={styles.captureActions}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={speech.recognizing ? "Pausar ditado" : "Iniciar ditado"}
                onPress={toggleQuickSpeech}
                disabled={speech.starting || busy}
                style={[styles.micButton, speech.recognizing && styles.micButtonOn]}
              >
                <Feather
                  name={speech.recognizing ? "pause" : "mic"}
                  size={15}
                  color={speech.recognizing ? colors.primaryText : colors.textMuted}
                />
                <Text style={[styles.micText, speech.recognizing && styles.micTextOn]}>
                  {speech.starting ? "preparando" : speech.recognizing ? "pausar" : "ditar"}
                </Text>
              </Pressable>
              {/* O cadeado da C: o toggle de sensível sai da fileira própria e
                  vira ghost dentro do cartão. */}
              <Pressable
                accessibilityRole="checkbox"
                accessibilityState={{ checked: sensitive }}
                accessibilityLabel="Conteúdo sensível"
                onPress={() => setSensitive((value) => !value)}
                hitSlop={6}
                style={[styles.lockButton, sensitive && styles.lockButtonOn]}
              >
                {/* Glifo DIFERENTE por estado, não só tom diferente: o de antes era
                    "lock" nos dois casos, e distinguir ligado de desligado só pela cor
                    falha no relance, no sol e para quem confunde as duas. Errar aqui
                    manda uma captura privada pro preview da tela de bloqueio. */}
                <Feather
                  name={sensitive ? "lock" : "unlock"}
                  size={14}
                  color={sensitive ? colors.primary : colors.textMuted}
                />
                <Text numberOfLines={1} style={[styles.lockText, sensitive && styles.lockTextOn]}>
                  {sensitive ? "sensível" : "normal"}
                </Text>
              </Pressable>
              <View style={{ flex: 1 }} />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Enviar captura"
                onPress={onSend}
                disabled={busy || !text.trim()}
                style={[styles.sendButton, (busy || !text.trim()) && styles.sendButtonDisabled]}
              >
                <Text style={styles.sendText}>{busy ? "enviando" : "Enviar"}</Text>
              </Pressable>
            </View>
          </Card>

          {pending > 0 ? (
            <View style={styles.queueRow}>
              <Feather name="cloud-off" size={13} color={colors.info} />
              <Text style={styles.queueText}>{pending} captura(s) seguras no aparelho</Text>
            </View>
          ) : null}
          {/* A fila do SERVIDOR. O digest manda "abrir o app" quando há capturas
              paradas, e até aqui abrir o app não oferecia nada — a rota de reenvio
              existia e nenhuma tela a conhecia. Falha de credencial do Hermes nunca
              sai sozinha da fila, então sem este botão ela nagava todo dia. */}
          {falhadasNoServidor > 0 ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Reprocessar ${falhadasNoServidor} capturas paradas`}
              hitSlop={8}
              style={styles.queueRow}
              disabled={reprocessando}
              onPress={async () => {
                // Trava contra toque duplo: sem ela, dois toques disparavam dois POST
                // e a linha sumia debaixo do dedo entre um e outro.
                if (reprocessando) return;
                setReprocessando(true);
                try {
                  const n = await reprocessarCapturasFalhadas();
                  const restam = await contarCapturasFalhadas();
                  setFalhadasNoServidor(restam);
                  // Só escreve na tela se ele ainda estiver na Capturar: o `status` é
                  // compartilhado com o modo leitura, e um recado sobre a fila do
                  // servidor aparecendo no meio de uma sessão de leitura é ruído.
                  if (modeRef.current === "captura") {
                    setStatus(
                      n > 0
                        ? `${n} captura(s) voltaram para a fila do servidor`
                        : "nada para reprocessar",
                    );
                  }
                } catch (erro) {
                  if (modeRef.current === "captura") {
                    // Distingue "não saiu do aparelho" de "o servidor recusou", em vez
                    // de culpar o servidor pelas duas.
                    setStatus(
                      ehFalhaDeRede(erro)
                        ? "sem conexão — não deu para falar com o servidor"
                        : mensagemDaRecusa(erro),
                    );
                  }
                } finally {
                  setReprocessando(false);
                }
              }}
            >
              <Feather name="rotate-ccw" size={13} color={colors.amber} />
              <Text style={[styles.queueText, { color: colors.amber }]}>
                {falhadasNoServidor} paradas no servidor · {reprocessando ? "reenviando…" : "reprocessar"}
              </Text>
            </Pressable>
          ) : null}
          {/* Recusados: saíram da fila pra não travá-la, mas NÃO foram apagados.
              Nenhum reenvio automático resolve — é o único estado da fila que
              precisa do Leo, então é o único que vale interromper a tela. */}
          {rejected > 0 ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Ver ${rejected} capturas recusadas`}
              onPress={verRecusados}
              hitSlop={8}
              style={styles.queueRow}
            >
              <Feather name="alert-triangle" size={13} color={colors.danger} />
              <Text style={[styles.queueText, { color: colors.danger }]}>
                {rejected} não saíram — o servidor recusou · ver
              </Text>
            </Pressable>
          ) : null}
          {status ? <Text style={styles.status}>{status}</Text> : null}
          {/* Toast sálvia da C. Sem "desfazer": o /capture é fire-and-forget e o
              BFF não expõe undo — botão sem ação atrás é mentira. */}
          {reply ? (
            <View style={styles.toast}>
              <View style={styles.toastIcon}>
                <Feather name="check" size={14} color={colors.success} />
              </View>
              <View style={{ flex: 1 }}>
                {/* Dizia "Caiu na triagem" duas linhas acima de uma dica que anuncia
                    `hack:` e `melhoria:` — prefixos que o capture_pipeline manda pra
                    edificação e pra fila de melhorias, não pra triagem. A tela não sabe
                    o destino (o /capture é fire-and-forget e responde antes de
                    classificar), então ela para de afirmar um. */}
                {/* Frase própria, não o literal do BFF: ele responde "✅ anotado", e o
                    emoji desenhava um segundo tique a 8px do Feather do toastIcon. */}
                <Text style={styles.toastTitle}>Anotado. Organiza depois.</Text>
                <Text style={styles.toastMeta}>vale +{tarifas.captura} quando materializar</Text>
              </View>
            </View>
          ) : null}

          {/* Os prefixos existiam desde o P2 item 10; a C os condensa numa linha
              mono só. Atalho que o Leo não vê é atalho que ele não usa. */}
          <Text style={styles.atalhos}>
            atalhos: <Text style={styles.atalhoCode}>melhoria:</Text> → melhorias
            {"  ·  "}<Text style={styles.atalhoCode}>hack:</Text> → edificação
            {"  ·  "}<Text style={styles.atalhoCode}>sensivel:</Text> = o cadeado
          </Text>
        </ScrollView>
      ) : sessionStart === null ? (
        <ScrollView
          contentContainerStyle={styles.readingSetup}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <LinearGradient
            colors={["rgba(222,184,120,0.18)", "rgba(111,181,140,0.05)"]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.readingHero}
          >
            <View style={styles.heroIcon}>
              <Feather name="book-open" size={23} color={colors.primary} />
            </View>
            <Text style={styles.eyebrow}>LEITURA SEM ATRITO</Text>
            <Text style={styles.readingTitle}>Leia primeiro. Organize depois.</Text>
            <Text style={styles.readingSubtitle}>
              Fale ou anote trechos durante a leitura. Ao final, tudo vira uma nota limpa e candidatos Anki.
            </Text>
          </LinearGradient>

          {serverPending.length > 0 ? (
            <View style={styles.pendingSessions}>
              <View style={styles.pendingHead}>
                <Feather name="rotate-ccw" size={14} color={colors.info} />
                <Text style={styles.pendingTitle}>RETOMAR SESSÃO</Text>
              </View>
              {serverPending.map((session) => (
                <Pressable key={session.id} style={styles.pendingSession} onPress={() => restoreRemote(session)}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.pendingBook} numberOfLines={1}>{session.livro || "Leitura sem título"}</Text>
                    <Text style={styles.pendingSessionText}>{session.buffer?.length ?? 0} registro(s) preservados</Text>
                  </View>
                  <Feather name="arrow-right" size={17} color={colors.primary} />
                </Pressable>
              ))}
            </View>
          ) : null}

          <Card style={styles.setupCard}>
            <Text style={styles.setupLabel}>O QUE VOCÊ VAI LER?</Text>

            {shelf && !newBookMode ? (
              <>
                {montarEstante(shelf, Date.now()).map((linha) => (
                  <Pressable
                    key={linha.id}
                    style={[
                      styles.shelfRow,
                      selectedBookId === linha.id && styles.shelfRowActive,
                    ]}
                    onPress={() => escolherObra(linha)}
                    disabled={shelfBusyId !== null}
                  >
                    <View style={{ flex: 1 }}>
                      <Text style={styles.shelfTitle} numberOfLines={1}>
                        {linha.titulo}
                      </Text>
                      <Text style={styles.shelfDetail}>{linha.detalhe}</Text>
                      {/* Onde ele parou, escrito no fim da sessão anterior. Só a obra
                          selecionada mostra: na lista inteira, três linhas de texto por
                          obra viram parede e a estante deixa de ser escaneável. */}
                      {selectedBookId === linha.id && linha.recap ? (
                        <Text style={styles.shelfRecap}>{linha.recap}</Text>
                      ) : null}
                    </View>
                    <Pressable
                      onPress={() => confirmarTerminar(linha.id, linha.titulo)}
                      hitSlop={10}
                      disabled={shelfBusyId !== null}
                      style={styles.shelfTerminar}
                      accessibilityRole="button"
                      accessibilityLabel={`Terminar ${linha.titulo}`}
                    >
                      {shelfBusyId === linha.id ? (
                        <ActivityIndicator size="small" color={colors.primary} />
                      ) : (
                        <Text style={styles.shelfTerminarText}>terminar</Text>
                      )}
                    </Pressable>
                  </Pressable>
                ))}
                <Pressable
                  onPress={() => {
                    setNewBookMode(true);
                    setSelectedBookId(null);
                    updateReadingField(setBook, "");
                    updateReadingField(setPageStart, "");
                  }}
                  style={styles.shelfAdd}
                >
                  <Feather name="plus" size={14} color={colors.primary} />
                  <Text style={styles.shelfAddText}>novo livro</Text>
                </Pressable>
              </>
            ) : null}

            {/* `|| presaErro`: o bloco tem que sobreviver ao próprio desfecho. Quando o
                resolver muda o estado da obra, `loadShelf` esvazia `presas` — e com o
                gate só em `presas.length` o bloco desmontava levando junto a explicação
                que acabou de nascer. No caso normal (UMA obra presa, que é o caso real)
                o conserto ficava invisível: só apareceria com duas ou mais. */}
            {presas.length > 0 || presaErro ? (
              <View style={styles.presasBloco}>
                {presas.length > 0 ? (
                  <Text style={styles.presasAviso}>{avisoDeObrasPresas(presas.length)}</Text>
                ) : null}
                {presas.map((obra) => (
                  <Pressable
                    key={obra.id}
                    style={styles.presaRow}
                    onPress={() => void resolverObraPresa(obra.id, obra.titulo)}
                    disabled={shelfBusyId !== null}
                  >
                    <Text style={styles.presaTitulo} numberOfLines={1}>{obra.titulo}</Text>
                    {shelfBusyId === obra.id ? (
                      <ActivityIndicator size="small" color={colors.primary} />
                    ) : (
                      <Text style={styles.presaAcao}>resolver</Text>
                    )}
                  </Pressable>
                ))}
                {presaErro ? (
                  // Aqui, e não no `speechError` lá embaixo: aquele renderiza depois
                  // do Card e depois do guideBlock, ou seja, fora da tela. Um resolver
                  // que falhava não produzia MUDANÇA VISÍVEL nenhuma — mesma linha,
                  // mesmo "resolver", explicação fora de vista.
                  <Text style={styles.presaErro}>{presaErro}</Text>
                ) : null}
              </View>
            ) : null}

            {shelf && !newBookMode ? null : (
              // shelf === null (não carregou) cai aqui também — degradação para o
              // campo livre de sempre, nunca uma estante vazia lida como "sem livro".
              <>
                {shelfError ? (
                  // A degradação em si é a escolha certa (ler sem estante é melhor
                  // que não conseguir ler), mas ela não pode ficar muda: sem isto a
                  // sessão nasce sem book_id e some da estante sem que nada avise.
                  <Pressable onPress={() => void loadShelf()}>
                    <Text style={styles.shelfWarning}>
                      estante indisponível — esta leitura não vai ser agrupada por
                      obra · toque para tentar de novo
                    </Text>
                  </Pressable>
                ) : null}
                <Field
                  value={book}
                  onChangeText={editarTitulo}
                  placeholder="Livro, artigo ou capítulo"
                  editable={readingDraftReady}
                />
                {newBookMode && shelf ? (
                  <Pressable onPress={voltarParaEstante}>
                    <Text style={styles.shelfLink}>‹ voltar à estante</Text>
                  </Pressable>
                ) : null}
              </>
            )}

            <Pressable
              onPress={async () => {
                const proximo = !showFinished;
                setShowFinished(proximo);
                if (proximo) {
                  try {
                    setFinished((await listBooks("terminado")).books);
                  } catch {
                    setFinished(null);
                  }
                }
              }}
            >
              <Text style={styles.shelfLink}>
                {showFinished ? "esconder terminadas" : "ver obras terminadas"}
              </Text>
            </Pressable>
            {showFinished && finished
              ? finished.map((obra) => (
                  <View key={obra.id} style={styles.shelfRow}>
                    <Text style={styles.shelfTitle} numberOfLines={1}>
                      {obra.titulo}
                    </Text>
                    <Pressable
                      onPress={() => void reabrirObra(obra.id)}
                      disabled={shelfBusyId !== null}
                    >
                      <Text style={styles.shelfLink}>reabrir</Text>
                    </Pressable>
                  </View>
                ))
              : null}

            <View style={styles.pagesRow}>
              <Field
                style={styles.pageField}
                value={pageStart}
                onChangeText={(value) => updateReadingField(setPageStart, value)}
                placeholder="Pág. inicial"
                keyboardType="number-pad"
                editable={readingDraftReady}
              />
              <Field
                style={styles.pageField}
                value={pageEnd}
                onChangeText={(value) => updateReadingField(setPageEnd, value)}
                placeholder="Pág. final"
                keyboardType="number-pad"
                editable={readingDraftReady}
              />
            </View>
            <AppButton
              title={readingDraftReady ? "Começar leitura" : "Verificando rascunho"}
              onPress={beginSession}
              loading={!readingDraftReady}
              disabled={!readingDraftReady || !book.trim()}
            />
            <Pressable
              onPress={startSession}
              disabled={!readingDraftReady || speech.starting || !book.trim()}
              style={styles.startWithAudio}
            >
              <Feather name="mic" size={14} color={colors.primary} />
              <Text style={styles.startWithAudioText}>começar já com o microfone</Text>
            </Pressable>
          </Card>

          <View style={styles.guideBlock}>
            <Text style={styles.guideTitle}>Durante a leitura, comece a fala assim:</Text>
            <View style={styles.kindGrid}>
              {readingKinds.map(([label, icon, color]) => (
                <View key={label} style={styles.kindGuide}>
                  <Feather name={icon} size={14} color={color} />
                  <Text style={[styles.kindGuideText, { color }]}>{label}</Text>
                </View>
              ))}
            </View>
          </View>
          {speechError ? <Text style={styles.status}>{speechError}</Text> : null}
          {status ? <Text style={styles.status}>{status}</Text> : null}
        </ScrollView>
      ) : (
        <View style={styles.liveScreen}>
          <View style={styles.liveHead}>
            <View style={styles.liveBookIcon}>
              <Feather name="book-open" size={18} color={colors.primary} />
            </View>
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={styles.liveEyebrow}>SESSÃO EM ANDAMENTO</Text>
              <Text style={styles.bookTitle} numberOfLines={1}>{book}</Text>
            </View>
            <View style={styles.timerPill}>
              <View style={[styles.recordingDot, speech.recognizing && styles.recordingDotOn]} />
              <Text style={styles.timerText}>{formatReadingElapsed(elapsedSeconds)}</Text>
            </View>
          </View>

          <View style={styles.liveControls}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={speech.recognizing ? "Pausar microfone" : "Ativar microfone"}
              onPress={speech.recognizing ? stopSpeech : startSession}
              disabled={speech.starting || frozen}
              style={[styles.audioControl, speech.recognizing && styles.audioControlOn]}
            >
              <Feather
                name={speech.recognizing ? "pause-circle" : "mic"}
                size={17}
                color={speech.recognizing ? colors.primaryText : colors.primary}
              />
              <Text style={[styles.audioControlText, speech.recognizing && styles.audioControlTextOn]}>
                {speech.starting ? "preparando" : speech.recognizing ? "pausar áudio" : "ativar áudio"}
              </Text>
            </Pressable>
            <Field
              style={styles.pageEndField}
              value={pageEnd}
              onChangeText={(value) => updateReadingField(setPageEnd, value)}
              placeholder="Pág. final"
              keyboardType="number-pad"
              editable={!frozen}
            />
          </View>

          {speech.interim ? <Text style={styles.interim}>“{speech.interim}”</Text> : null}
          {speechError ? <Text style={styles.status}>{speechError}</Text> : null}

          <ScrollView
            style={styles.itemsScroll}
            contentContainerStyle={items.length === 0 ? styles.emptyItems : styles.itemsContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {items.length === 0 ? (
              <View style={styles.emptyReading}>
                <Feather name="feather" size={24} color={colors.textMuted} />
                <Text style={styles.emptyTitle}>Seu buffer está pronto.</Text>
                <Text style={styles.emptyText}>Fale livremente ou escreva o primeiro registro abaixo. Nada se perde se você sair do app.</Text>
              </View>
            ) : items.map((item) => {
              const kind = KIND[item.kind] ?? KIND["comentário"];
              return (
                <View key={item.id} style={[styles.item, { borderLeftColor: kind.color }]}>
                  <View style={styles.itemHead}>
                    <Feather name={kind.icon} size={12} color={kind.color} />
                    <Text style={[styles.itemKind, { color: kind.color }]}>{item.kind}</Text>
                    <Text style={styles.itemNumber}>#{item.seq}</Text>
                    {item.seq === items.at(-1)?.seq ? (
                      <View style={styles.itemActions}>
                        <Pressable accessibilityLabel="Corrigir último registro" onPress={() => editLast(item)} hitSlop={8}>
                          <Feather name="edit-2" size={13} color={colors.textMuted} />
                        </Pressable>
                        <Pressable accessibilityLabel="Remover último registro" onPress={() => setRemoveConfirmSeq(item.seq)} hitSlop={8}>
                          <Feather name="trash-2" size={13} color={colors.textMuted} />
                        </Pressable>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.itemText}>{item.text}</Text>
                  {removeConfirmSeq === item.seq ? (
                    <View style={styles.removeConfirm}>
                      <Text style={styles.removeQuestion}>Remover este registro?</Text>
                      <Pressable accessibilityRole="button" onPress={() => removeLast(item)} disabled={editingBusy}>
                        <Text style={styles.removeYes}>remover</Text>
                      </Pressable>
                      <Pressable accessibilityRole="button" onPress={() => setRemoveConfirmSeq(null)} disabled={editingBusy}>
                        <Text style={styles.editingCancel}>cancelar</Text>
                      </Pressable>
                    </View>
                  ) : null}
                </View>
              );
            })}
          </ScrollView>

          <View style={styles.composer}>
            {editingSeq !== null ? (
              <View style={styles.editingBanner}>
                <Feather name="edit-2" size={12} color={colors.primary} />
                <Text style={styles.editingText}>corrigindo o registro #{editingSeq}</Text>
                <Pressable onPress={() => { setEditingSeq(null); setEntry(""); }} hitSlop={8}>
                  <Text style={styles.editingCancel}>cancelar</Text>
                </Pressable>
              </View>
            ) : null}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.kindChips}>
              {readingKinds.map(([label, icon, color]) => (
                <Pressable
                  key={label}
                  onPress={() => setEntry(`${label}: `)}
                  disabled={frozen}
                  style={[styles.kindChip, frozen && styles.kindChipDisabled]}
                >
                  <Feather name={icon} size={12} color={color} />
                  <Text style={styles.kindChipText}>{label}</Text>
                </Pressable>
              ))}
            </ScrollView>
            <View style={styles.addRow}>
              <Field
                style={styles.entryField}
                value={entry}
                onChangeText={setEntry}
                placeholder="Anote um trecho ou pensamento"
                editable={!frozen && !editingBusy}
                onSubmitEditing={onAdd}
              />
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Adicionar registro"
                onPress={onAdd}
                disabled={frozen || editingBusy || !entry.trim()}
                style={[styles.addBtn, !entry.trim() && styles.addBtnDisabled]}
              >
                <Feather name="arrow-up" size={20} color={colors.primaryText} />
              </Pressable>
            </View>
            {preview !== null ? (
              <View style={styles.previewBlock}>
                <View style={styles.previewHead}>
                  <Feather name="file-text" size={13} color={colors.primary} />
                  <Text style={styles.previewTitle}>PREVIEW DA NOTA — REVISE ANTES DO VAULT</Text>
                </View>
                <ScrollView
                  style={styles.previewScroll}
                  contentContainerStyle={styles.previewContent}
                  nestedScrollEnabled
                  showsVerticalScrollIndicator
                >
                  <Text style={styles.previewText} selectable>{preview}</Text>
                </ScrollView>
                <AppButton
                  title="Salvar no vault"
                  onPress={approveNow}
                  loading={compiling}
                  disabled={compiling}
                />
                <View style={styles.compileMeta}>
                  <Text style={styles.compileHint}>Nada foi gravado ainda. Salvar grava a nota e sugere Anki.</Text>
                  <Pressable onPress={rejectNow} hitSlop={8} disabled={compiling}>
                    <Text style={styles.discardText}>rejeitar</Text>
                  </Pressable>
                </View>
              </View>
            ) : (
              <>
                <AppButton
                  title={items.length === 0 ? "Adicione algo para fechar a nota" : `Fechar a nota · ${items.length} registro${items.length === 1 ? "" : "s"}`}
                  variant="ghost"
                  onPress={compilar}
                  loading={compiling}
                  disabled={speech.starting || items.length === 0 || editingSeq !== null || editingBusy}
                />
                <View style={styles.compileMeta}>
                  <Text style={styles.compileHint}>Preview read-only antes de gravar no vault.</Text>
                  <Pressable onPress={descartar} hitSlop={8} disabled={compiling}>
                    <Text style={styles.discardText}>descartar</Text>
                  </Pressable>
                </View>
              </>
            )}
            {status ? <Text style={styles.status}>{status}</Text> : null}
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, paddingTop: spacing.xs },
  modebar: {
    flexDirection: "row",
    gap: 5,
    backgroundColor: colors.card2,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: 4,
  },
  mode: {
    flex: 1,
    minHeight: 40,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    borderRadius: radius.sm,
  },
  modeOn: { backgroundColor: colors.card, borderWidth: 1, borderColor: "rgba(235,222,202,0.20)" },
  modeTxt: { fontFamily: fonts.uiSemi, fontSize: 12.5, color: colors.textMuted },
  modeTxtOn: { color: colors.text },
  captureContent: { paddingTop: spacing.xl, paddingBottom: spacing.xxxl, gap: spacing.md },
  crumb: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted, letterSpacing: 1.5, textTransform: "uppercase", paddingHorizontal: spacing.xs },
  eyebrow: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.primary, letterSpacing: 1.7 },
  captureCard: { padding: 0, overflow: "hidden", borderColor: "rgba(235,222,202,0.20)" },
  input: { minHeight: 150, textAlignVertical: "top", borderWidth: 0, backgroundColor: "transparent", padding: spacing.lg },
  captureActions: { minHeight: 58, flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border },
  micButton: { flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: spacing.md, height: 38, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border },
  micButtonOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  micText: { fontFamily: fonts.uiSemi, fontSize: 12, color: colors.textMuted },
  micTextOn: { color: colors.primaryText },
  // Deixa de ser quadrado fixo: agora carrega o rótulo ao lado do glifo.
  lockButton: { flexDirection: "row", alignItems: "center", gap: 5, height: 38, paddingHorizontal: 10, borderRadius: 11, justifyContent: "center", borderWidth: 1, borderColor: colors.border },
  lockButtonOn: { borderColor: "rgba(222,184,120,0.45)", backgroundColor: colors.primarySoft },
  // flexShrink: a fileira não tem wrap e o cartão tem overflow hidden — sem isto o
  // rótulo novo empurrava o botão Enviar pra fora em tela estreita.
  lockText: { fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted, letterSpacing: 0.6, flexShrink: 1 },
  lockTextOn: { color: colors.primary },
  sendButton: { flexDirection: "row", alignItems: "center", gap: 5, height: 40, paddingHorizontal: spacing.lg, borderRadius: radius.md, backgroundColor: colors.primary, borderBottomWidth: 2, borderBottomColor: "#B6935C" },
  sendButtonDisabled: { opacity: 0.4 },
  sendText: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.primaryText },
  toast: { flexDirection: "row", gap: 10, alignItems: "center", backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingVertical: 11, paddingHorizontal: 13 },
  toastIcon: { width: 30, height: 30, borderRadius: 10, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(113,180,154,0.12)", borderWidth: 1, borderColor: "rgba(113,180,154,0.35)" },
  toastTitle: { fontFamily: fonts.uiMedium, fontSize: 13, color: colors.text },
  toastMeta: { fontFamily: fonts.mono, fontSize: 8.5, color: colors.success, letterSpacing: 0.6, marginTop: 2 },
  queueRow: { flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: spacing.xs },
  queueText: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.info },
  status: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 17, color: colors.textMuted, paddingHorizontal: spacing.xs },
  atalhos: { fontFamily: fonts.mono, fontSize: 8.5, letterSpacing: 0.3, color: colors.faint, lineHeight: 17, marginTop: spacing.sm, paddingHorizontal: spacing.xs },
  atalhoCode: { color: colors.textMuted },
  readingSetup: { paddingTop: spacing.md, paddingBottom: spacing.xxxl, gap: spacing.md },
  readingHero: { borderRadius: radius.xl, borderWidth: 1, borderColor: "rgba(222,184,120,0.18)", padding: spacing.xl, gap: 9, overflow: "hidden" },
  heroIcon: { width: 46, height: 46, borderRadius: 15, alignItems: "center", justifyContent: "center", backgroundColor: colors.primarySoft, marginBottom: spacing.sm },
  readingTitle: { fontFamily: fonts.display, fontSize: 27, lineHeight: 32, color: colors.text, letterSpacing: -0.3 },
  readingSubtitle: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textMuted },
  pendingSessions: { gap: spacing.sm, padding: spacing.md, borderWidth: 1, borderColor: "rgba(104,162,205,0.35)", borderRadius: radius.lg, backgroundColor: "rgba(104,162,205,0.06)" },
  pendingHead: { flexDirection: "row", alignItems: "center", gap: 7 },
  pendingTitle: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1.2, color: colors.info },
  pendingSession: { minHeight: 56, flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.card },
  pendingBook: { fontFamily: fonts.uiSemi, fontSize: 13, color: colors.text },
  pendingSessionText: { fontFamily: fonts.ui, fontSize: 11, color: colors.textMuted, marginTop: 3 },
  setupCard: { gap: spacing.md },
  setupLabel: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1.3, color: colors.textMuted },
  // colors.surfaceAlt e colors.muted não existem em theme.ts (Task 11) — troquei
  // pelo par que os estilos vizinhos deste arquivo já usam para o mesmo papel:
  // card2 (fundo de destaque) e textMuted (texto secundário).
  shelfRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  shelfRowActive: { backgroundColor: colors.card2 },
  shelfTitle: { fontFamily: fonts.uiSemi, color: colors.text, fontSize: 15, flex: 1 },
  shelfDetail: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 12, marginTop: 2 },
  shelfRecap: { fontFamily: fonts.ui, color: colors.text, fontSize: 12.5, lineHeight: 17, marginTop: 6 },
  shelfTerminar: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  shelfTerminarText: { fontFamily: fonts.ui, color: colors.textMuted, fontSize: 11 },
  shelfAdd: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 12 },
  presasBloco: { marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.border },
  presasAviso: { fontFamily: fonts.ui, color: colors.amber, fontSize: 11.5, marginBottom: 6 },
  presaErro: { fontFamily: fonts.ui, color: colors.danger, fontSize: 11.5, marginTop: 6 },
  presaRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8 },
  presaTitulo: { fontFamily: fonts.ui, color: colors.text, fontSize: 13.5, flex: 1 },
  presaAcao: { fontFamily: fonts.uiSemi, color: colors.primary, fontSize: 12 },
  shelfAddText: { fontFamily: fonts.uiSemi, color: colors.primary, fontSize: 13 },
  shelfLink: { fontFamily: fonts.ui, color: colors.primary, fontSize: 12, paddingVertical: 8 },
  shelfWarning: { fontFamily: fonts.ui, color: colors.danger, fontSize: 11.5, lineHeight: 16, paddingBottom: spacing.xs },
  pagesRow: { flexDirection: "row", gap: spacing.sm },
  pageField: { flex: 1, minWidth: 0 },
  startWithAudio: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7, paddingVertical: 5 },
  startWithAudioText: { fontFamily: fonts.uiSemi, fontSize: 12, color: colors.primary },
  guideBlock: { gap: spacing.sm, paddingHorizontal: spacing.xs },
  guideTitle: { fontFamily: fonts.ui, fontSize: 12, color: colors.textMuted },
  kindGrid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  kindGuide: { flexDirection: "row", alignItems: "center", gap: 7, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 8 },
  kindGuideText: { fontFamily: fonts.mono, fontSize: 10.5 },
  liveScreen: { flex: 1, paddingTop: spacing.md },
  liveHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, paddingBottom: spacing.md },
  liveBookIcon: { width: 42, height: 42, borderRadius: 13, alignItems: "center", justifyContent: "center", backgroundColor: colors.primarySoft },
  liveEyebrow: { fontFamily: fonts.mono, fontSize: 8.5, color: colors.success, letterSpacing: 1.1, marginBottom: 3 },
  bookTitle: { fontFamily: fonts.uiSemi, fontSize: 18, color: colors.text },
  timerPill: { flexDirection: "row", alignItems: "center", gap: 7, backgroundColor: colors.card2, borderRadius: radius.pill, paddingHorizontal: 11, height: 34, borderWidth: 1, borderColor: colors.border },
  timerText: { fontFamily: fonts.mono, fontSize: 12, color: colors.text },
  recordingDot: { width: 7, height: 7, borderRadius: 7, backgroundColor: colors.textMuted },
  recordingDotOn: { backgroundColor: "#DE8A7A" },
  liveControls: { flexDirection: "row", gap: spacing.sm, alignItems: "center", marginBottom: spacing.sm },
  audioControl: { flex: 1, height: 43, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 7, borderRadius: radius.md, borderWidth: 1, borderColor: colors.primary, backgroundColor: colors.primarySoft },
  audioControlOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  audioControlText: { fontFamily: fonts.uiSemi, fontSize: 12, color: colors.primary },
  audioControlTextOn: { color: colors.primaryText },
  pageEndField: { width: 112, height: 43, paddingVertical: 8, fontSize: 13 },
  interim: { fontFamily: fonts.ui, fontSize: 12.5, lineHeight: 18, color: colors.textMuted, fontStyle: "italic", paddingHorizontal: spacing.sm, paddingVertical: 5 },
  itemsScroll: { flex: 1, marginTop: spacing.xs },
  itemsContent: { paddingTop: spacing.xs, paddingBottom: spacing.md },
  emptyItems: { flexGrow: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.xl },
  emptyReading: { alignItems: "center", gap: 8, maxWidth: 280 },
  emptyTitle: { fontFamily: fonts.uiSemi, fontSize: 18, color: colors.text, marginTop: 4 },
  emptyText: { fontFamily: fonts.ui, fontSize: 12.5, lineHeight: 18, textAlign: "center", color: colors.textMuted },
  item: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 3, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm },
  itemHead: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 5 },
  itemKind: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1, textTransform: "uppercase" },
  itemNumber: { marginLeft: "auto", fontFamily: fonts.mono, fontSize: 9, color: colors.textMuted },
  itemActions: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginLeft: 4 },
  itemText: { fontFamily: fonts.ui, fontSize: 14, color: colors.text, lineHeight: 20 },
  removeConfirm: { flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border },
  removeQuestion: { flex: 1, fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  removeYes: { fontFamily: fonts.uiSemi, fontSize: 11, color: colors.danger },
  composer: { gap: spacing.sm, paddingTop: spacing.sm, paddingBottom: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border },
  editingBanner: { flexDirection: "row", alignItems: "center", gap: 7, minHeight: 28, paddingHorizontal: spacing.xs },
  editingText: { flex: 1, fontFamily: fonts.mono, fontSize: 9.5, color: colors.primary },
  editingCancel: { fontFamily: fonts.uiSemi, fontSize: 10.5, color: colors.textMuted },
  kindChips: { gap: 7 },
  kindChip: { flexDirection: "row", alignItems: "center", gap: 6, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 10, height: 30, backgroundColor: colors.card2 },
  kindChipDisabled: { opacity: 0.4 },
  kindChipText: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted },
  addRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center" },
  entryField: { flex: 1, minWidth: 0 },
  addBtn: { width: 48, height: 48, borderRadius: radius.md, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  addBtnDisabled: { opacity: 0.35 },
  compileMeta: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  compileHint: { flex: 1, fontFamily: fonts.ui, fontSize: 10.5, color: colors.textMuted },
  discardText: { fontFamily: fonts.mono, fontSize: 10.5, color: "#DE8A7A" },
  previewBlock: { gap: spacing.sm },
  previewHead: { flexDirection: "row", alignItems: "center", gap: 7, paddingHorizontal: spacing.xs },
  previewTitle: { fontFamily: fonts.mono, fontSize: 9.5, letterSpacing: 1.1, color: colors.primary },
  previewScroll: { maxHeight: 220, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: colors.card2 },
  previewContent: { padding: spacing.md },
  previewText: { fontFamily: fonts.mono, fontSize: 12.5, lineHeight: 19, color: colors.text },
});
