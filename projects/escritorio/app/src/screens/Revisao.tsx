import Feather from "@expo/vector-icons/Feather";
import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";
import { ComponentProps, useCallback, useEffect, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  Digest,
  AnkiCard,
  Objetivo,
  Pontos,
  ReviewMonthly,
  ReviewWeekly,
  Task,
  completeTask,
  createObjetivo,
  deleteObjetivo,
  getDigest,
  getPontos,
  getReviewMonthly,
  approveWeeklyReview,
  getReviewWeekly,
  exportAnki,
  listAnkiCards,
  listObjetivos,
  setObjetivoHoje,
  updateAnkiCard,
} from "../api";
import { TaskDetailModal } from "../TaskDetailModal";
import { ReadingSession, listPendingReadingSessions } from "../readingApi";
import { milhar } from "../format";
import { areaColor, colors, fonts, radius, spacing } from "../theme";
import { AppButton, Card, ErrorState, Field, SegmentBar, Skeleton } from "../ui";

// Exibição pura: a severidade vem pronta do back (Task.severity). O front só mapeia
// nível -> cor/ícone; não parseia mais a string `due` (fonte única no BFF, P0.2).
type FeatherName = ComponentProps<typeof Feather>["name"];
const LAST_ANKI_FILE = Platform.OS === "web"
  ? null
  : new File(Paths.document, "anki-ultimo.tsv");

const SEVERITY_STYLE: Record<string, { color: string; icon: FeatherName }> = {
  urgente: { color: colors.danger, icon: "alert-octagon" },
  firme: { color: colors.danger, icon: "alert-circle" },
  leve: { color: colors.amber, icon: "alert-triangle" },
  no_prazo: { color: colors.amber, icon: "clock" },
};

const styleFor = (t: Task) => SEVERITY_STYLE[t.severity ?? "no_prazo"];

// ------------------------------------------------------------------- Placar
// Lei nº4: 100% factual. O placar informa, não julga. Ganho em cor de sucesso;
// desconto NUNCA em danger — desconto não é erro, é fato. A onda 4 desceu de muted
// para `faint`, um degrau mais quieto, que é o token criado pela proposta C2 para
// metadado em repouso. Sem streak-reset, sem elogio: se não houve padrão na semana,
// a seção some (não escrevemos "nenhum furo!", isso seria elogio).
const NIVEIS = [1, 2, 3, 4];

function Diamantes({ nivel }: { nivel: number }) {
  return (
    <View style={styles.diamonds}>
      {NIVEIS.map((n) => (
        <View key={n} style={[styles.diamond, n <= nivel && styles.diamondOn]} />
      ))}
    </View>
  );
}

function Placar({ p }: { p: Pontos }) {
  const { ciclo, semana, proximo_nivel } = p;
  const pct = ciclo.meta > 0 ? Math.max(0, Math.min(1, ciclo.pontos / ciclo.meta)) : 0;

  return (
    <>
      {/* Herói no fundo nu: o tamanho é a ênfase, não a cor. Sem lineHeight
          declarado — no Android um lineHeight menor que a altura natural da
          Syne corta glifo; o RN calcula. */}
      <View style={styles.hero}>
        <Text style={styles.heroSaldo}>{milhar(p.saldo_total)}</Text>
        <Text style={styles.heroLabel}>PONTOS ACUMULADOS</Text>
        <View style={styles.nivelRow}>
          <Text style={styles.nivelTag}>{p.nivel > 0 ? `N${p.nivel}` : "—"}</Text>
          <Diamantes nivel={p.nivel} />
          <Text style={styles.nivelHint}>
            {p.nivel > 0 ? "vitalício · não regride" : "a caminho do N1"}
          </Text>
        </View>
      </View>

      <Card style={styles.conqCard}>
        <View style={styles.cicloRow}>
          <Text style={styles.cicloLabel}>
            CICLO {ciclo.indice} · SEMANA {ciclo.semana}/{ciclo.de}
          </Text>
          <Text style={styles.cicloPontos}>
            {milhar(ciclo.pontos)}/{milhar(ciclo.meta)}
          </Text>
        </View>
        {/* 10 segmentos padrão: a barra é alimentada por pontos, não por
            semanas — 12 sob o rótulo "SEMANA x/12" mentiria (decisão nº 2). */}
        <View style={{ marginTop: 10 }}>
          <SegmentBar value={pct} />
        </View>
        <View style={styles.semanaRow}>
          <Text style={styles.ganho}>semana +{milhar(semana.ganho)}</Text>
          {semana.desconto > 0 ? (
            <Text style={styles.desconto}>−{milhar(semana.desconto)} descontos</Text>
          ) : null}
          <Text style={styles.proximoNivel}>
            {proximo_nivel
              ? `N${proximo_nivel.n} em ${milhar(proximo_nivel.faltam)}`
              : "N4 — topo"}
          </Text>
        </View>
        {semana.padroes.length > 0 ? (
          <View style={styles.padroes}>
            {semana.padroes.map((pd) => (
              <Text key={pd.slug} style={styles.padrao}>
                {pd.nome} · {pd.furos} furos em 7d · −{milhar(pd.delta)}
              </Text>
            ))}
          </View>
        ) : null}
      </Card>
    </>
  );
}

function Metrica({ valor, label }: { valor: string | number; label: string }) {
  return (
    <View style={styles.metrica}>
      <Text style={styles.metricaValor}>{valor}</Text>
      <Text style={styles.metricaLabel}>{label}</Text>
    </View>
  );
}

function Reviews({
  semanal,
  mensal,
  onOpenEdificacao,
  onOpenMelhorias,
  onFecharSemana,
  fechandoReview,
  reviewFeito,
}: {
  semanal: ReviewWeekly;
  mensal: ReviewMonthly;
  onOpenEdificacao?: () => void;
  onOpenMelhorias?: () => void;
  onFecharSemana: () => void;
  fechandoReview: boolean;
  reviewFeito: boolean;
}) {
  return (
    <>
      <Text style={styles.sectionLabel}>ciclo de revisão</Text>
      <Card style={styles.reviewCard}>
        <View style={styles.reviewHead}>
          <View>
            <Text style={styles.reviewEyebrow}>SEMANA {semanal.week}</Text>
            <Text style={styles.reviewTitle}>Execução corrente</Text>
          </View>
          <Text style={styles.reviewPct}>{semanal.scorecard.pct}%</Text>
        </View>
        <View style={styles.metricas}>
          <Metrica valor={semanal.dailies} label="dias fechados" />
          <Metrica valor={semanal.capturas} label="capturas" />
          <Metrica valor={`${semanal.sessoes_leitura.min_total}m`} label="leitura" />
          <Metrica valor={semanal.staging_pendentes ?? "—"} label="staging" />
        </View>
        {semanal.edificacao.pratica ? (
          <View style={styles.praticaResumo}>
            <Feather name="compass" size={14} color={colors.primary} />
            <Text style={styles.praticaResumoText} numberOfLines={2}>
              prática: {semanal.edificacao.pratica.texto}
            </Text>
          </View>
        ) : semanal.edificacao.novos > 0 ? (
          <Pressable onPress={onOpenEdificacao} style={styles.praticaLink}>
            <Text style={styles.reviewHint}>
              {semanal.edificacao.novos} aprendizados aguardam escolha de prática.
            </Text>
            <Feather name="arrow-right" size={13} color={colors.primary} />
          </Pressable>
        ) : null}
        {/* Melhoria não é tarefa: aparece no rito onde ele já para pra pensar em
            sistema, nunca na lista de execução. As de alvo `app` ficam fora da
            cobrança — dependem de uma sessão de programação, não dele sozinho.

            O `escolhida` do pack já vem filtrado pela semana corrente: sem isso,
            uma escolha de junho seguia exibida como a desta semana e, por ser um
            ternário encadeado, o convite abaixo nunca mais era renderizado. */}
        {semanal.melhorias?.escolhida ? (
          <View style={styles.praticaResumo}>
            <Feather name="zap" size={14} color={colors.primary} />
            <Text style={styles.praticaResumoText} numberOfLines={2}>
              melhoria: {semanal.melhorias.escolhida.texto}
            </Text>
          </View>
        ) : semanal.melhorias?.escolhiveis ? (
          <Pressable onPress={onOpenMelhorias} style={styles.praticaLink}>
            <Text style={styles.reviewHint}>
              {semanal.melhorias.escolhiveis}{" "}
              {semanal.melhorias.escolhiveis === 1 ? "melhoria parada" : "melhorias paradas"}
              {" — escolher 1 para a semana."}
            </Text>
            <Feather name="arrow-right" size={13} color={colors.primary} />
          </Pressable>
        ) : null}
        {/* Separado de propósito: o card de "a triar" só tem os chips de alvo. Se
            o convite dissesse "escolher 1", ele iria procurar um botão que aquela
            seção não oferece. */}
        {semanal.melhorias?.a_triar ? (
          <Pressable onPress={onOpenMelhorias} style={styles.praticaLink}>
            <Text style={styles.reviewHint}>
              {semanal.melhorias.a_triar}{" "}
              {semanal.melhorias.a_triar === 1 ? "melhoria a triar" : "melhorias a triar"}
              {" — um toque cada."}
            </Text>
            <Feather name="arrow-right" size={13} color={colors.primary} />
          </Pressable>
        ) : null}
        {semanal.melhorias?.vencidas?.length ? (
          <Pressable onPress={onOpenMelhorias} style={styles.praticaLink}>
            <Text style={styles.reviewHint}>
              {semanal.melhorias.vencidas.length === 1
                ? `1 melhoria escolhida em ${semanal.melhorias.vencidas[0].escolhida_semana} segue em aberto.`
                : `${semanal.melhorias.vencidas.length} melhorias escolhidas antes seguem em aberto.`}
            </Text>
            <Feather name="arrow-right" size={13} color={colors.primary} />
          </Pressable>
        ) : null}
        {semanal.melhorias?.app ? (
          <Text style={styles.reviewHint}>
            {semanal.melhorias.app} de app aguardam uma sessão de programação.
          </Text>
        ) : null}
        {/* O review era um dashboard: rolava, acabava, e nada persistia. Sem
            artefato no vault e sem registro, "2 semanas puladas → Mentor" era
            impossível de responder. */}
        <AppButton
          title={reviewFeito ? "✓ semana fechada no vault" : "Fechar a semana no vault"}
          variant={reviewFeito ? "ghost" : undefined}
          loading={fechandoReview}
          disabled={reviewFeito || fechandoReview}
          onPress={onFecharSemana}
        />
      </Card>

      <Card style={styles.monthCard}>
        <View style={styles.reviewHead}>
          <View>
            <Text style={styles.reviewEyebrow}>MÊS {mensal.mes}</Text>
            <Text style={styles.reviewTitle}>Fechamento anterior</Text>
          </View>
          <Text style={styles.monthPct}>{mensal.scorecard.pct}%</Text>
        </View>
        <View style={styles.metricas}>
          <Metrica valor={mensal.dailies} label="dias fechados" />
          <Metrica valor={mensal.capturas} label="capturas" />
          <Metrica valor={`${mensal.sessoes_leitura.min_total}m`} label="leitura" />
          <Metrica valor={mensal.pontos.saldo} label="saldo pts" />
        </View>
        {mensal.objetivos.map((objetivo) => (
          <View key={objetivo.nome} style={styles.monthObjetivo}>
            <Text style={styles.monthObjetivoNome}>{objetivo.nome}</Text>
            <Text style={styles.monthObjetivoValor}>{objetivo.total_no_mes}</Text>
          </View>
        ))}
        <Text style={styles.reviewHint}>{mensal.patrimonio}</Text>
      </Card>
    </>
  );
}

export default function Revisao({
  onOpenCapture,
  onOpenEdificacao,
  onOpenMelhorias,
}: {
  onOpenCapture?: () => void;
  onOpenEdificacao?: () => void;
  onOpenMelhorias?: () => void;
}) {
  const [d, setD] = useState<Digest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  // Pontos tem estado PRÓPRIO: /pontos cair não pode derrubar a Revisão (o digest
  // continua). O painel degrada sozinho numa linha muda; o pull-to-refresh retenta.
  const [pontos, setPontos] = useState<Pontos | null>(null);
  const [pontosErr, setPontosErr] = useState(false);
  const [pontosLoading, setPontosLoading] = useState(true);
  const [semanal, setSemanal] = useState<ReviewWeekly | null>(null);
  const [mensal, setMensal] = useState<ReviewMonthly | null>(null);
  const [objetivos, setObjetivos] = useState<Objetivo[]>([]);
  const [reflexaoLoading, setReflexaoLoading] = useState(true);
  const [reflexaoErr, setReflexaoErr] = useState(false);
  const [novoObjetivo, setNovoObjetivo] = useState("");
  const [novoAlvo, setNovoAlvo] = useState("");
  const [salvandoObjetivo, setSalvandoObjetivo] = useState(false);
  const [ankiCards, setAnkiCards] = useState<AnkiCard[]>([]);
  const [ankiLoading, setAnkiLoading] = useState(true);
  const [ankiError, setAnkiError] = useState(false);
  const [ankiBusy, setAnkiBusy] = useState<number | "export" | null>(null);
  const [lastAnkiExport, setLastAnkiExport] = useState(
    LAST_ANKI_FILE?.exists ?? false,
  );
  const [readingPending, setReadingPending] = useState<ReadingSession[]>([]);
  const [readingPendingError, setReadingPendingError] = useState(false);
  const [fechandoReview, setFechandoReview] = useState(false);
  const [reviewFeito, setReviewFeito] = useState(false);

  async function fecharSemana() {
    setFechandoReview(true);
    try {
      const r = await approveWeeklyReview();
      setReviewFeito(true);
      Alert.alert("Semana fechada", `Gravado em ${r.vault_path}`);
    } catch (e: any) {
      Alert.alert("Review", e?.message ?? "não consegui fechar a semana");
    } finally {
      setFechandoReview(false);
    }
  }

  const loadDigest = useCallback(async () => {
    setLoading(true);
    try {
      setD(await getDigest());
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPontos = useCallback(async () => {
    setPontosLoading(true);
    try {
      setPontos(await getPontos());
      setPontosErr(false);
    } catch {
      setPontosErr(true);
    } finally {
      setPontosLoading(false);
    }
  }, []);

  const loadReflexao = useCallback(async () => {
    setReflexaoLoading(true);
    try {
      const [s, m, os] = await Promise.all([
        getReviewWeekly(),
        getReviewMonthly(),
        listObjetivos(),
      ]);
      setSemanal(s);
      setMensal(m);
      setObjetivos(os);
      setReflexaoErr(false);
    } catch {
      setReflexaoErr(true);
    } finally {
      setReflexaoLoading(false);
    }
  }, []);

  const loadAnki = useCallback(async () => {
    setAnkiLoading(true);
    try {
      setAnkiCards(await listAnkiCards());
      setAnkiError(false);
    } catch {
      setAnkiError(true);
    } finally {
      setAnkiLoading(false);
    }
  }, []);

  const loadReadingPending = useCallback(async () => {
    try {
      const resultado = await listPendingReadingSessions();
      setReadingPending(resultado.sessions);
      setReadingPendingError(false);
    } catch {
      setReadingPendingError(true);
    }
  }, []);

  const load = useCallback(async () => {
    await Promise.all([
      loadDigest(),
      loadPontos(),
      loadReflexao(),
      loadAnki(),
      loadReadingPending(),
    ]);
  }, [loadAnki, loadDigest, loadPontos, loadReadingPending, loadReflexao]);

  useEffect(() => {
    load();
  }, [load]);

  async function completeById(id: string) {
    try {
      await completeTask(id);
      await load();
    } catch (e: any) {
      Alert.alert("Concluir", e?.message ?? "falhou");
    }
  }

  async function adicionarObjetivo() {
    const nome = novoObjetivo.trim();
    if (!nome) return;
    const alvo = novoAlvo.trim() ? Number(novoAlvo) : null;
    if (alvo !== null && (!Number.isInteger(alvo) || alvo < 1 || alvo > 7)) {
      Alert.alert("Objetivo", "O alvo semanal precisa estar entre 1 e 7.");
      return;
    }
    setSalvandoObjetivo(true);
    try {
      await createObjetivo({ nome, alvo_semana: alvo });
      setNovoObjetivo("");
      setNovoAlvo("");
      await loadReflexao();
    } catch (e: any) {
      Alert.alert("Objetivo", e?.message ?? "não consegui salvar");
    } finally {
      setSalvandoObjetivo(false);
    }
  }

  async function marcarObjetivo(id: number, marcado: boolean) {
    try {
      await setObjetivoHoje(id, marcado);
      await loadReflexao();
    } catch (e: any) {
      Alert.alert("Objetivo", e?.message ?? "não consegui atualizar");
    }
  }

  function removerObjetivo(objetivo: Objetivo) {
    Alert.alert(
      "Arquivar objetivo",
      objetivo.nome,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Arquivar",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteObjetivo(objetivo.id);
              await loadReflexao();
            } catch (e: any) {
              Alert.alert("Objetivo", e?.message ?? "não consegui arquivar");
            }
          },
        },
      ],
    );
  }

  function editarAnki(
    id: number,
    campo: "frente" | "meaning" | "example" | "hook" | "deck",
    valor: string,
  ) {
    setAnkiCards((atuais) =>
      atuais.map((card) => (card.id === id ? { ...card, [campo]: valor } : card)),
    );
  }

  async function decidirAnki(card: AnkiCard, status?: "aprovado" | "descartado") {
    if (ankiBusy !== null) return;
    setAnkiBusy(card.id);
    try {
      const atualizado = await updateAnkiCard(card.id, {
        frente: card.frente,
        meaning: card.meaning,
        example: card.example,
        hook: card.hook,
        deck: card.deck ?? "",
        ...(status ? { status } : {}),
      });
      setAnkiCards((atuais) =>
        atuais.map((item) => (item.id === atualizado.id ? atualizado : item)),
      );
    } catch (e: any) {
      Alert.alert("Anki", e?.message ?? "não consegui atualizar o card");
    } finally {
      setAnkiBusy(null);
    }
  }

  async function exportarAnki() {
    if (ankiBusy !== null) return;
    setAnkiBusy("export");
    let resultado: Awaited<ReturnType<typeof exportAnki>> | null = null;
    try {
      if (!(await Sharing.isAvailableAsync())) {
        Alert.alert("Anki", "Compartilhamento de arquivo indisponível neste aparelho.");
        return;
      }
      resultado = await exportAnki();
      if (resultado.n === 0 || !resultado.tsv) {
        Alert.alert("Exportação Anki", "Não há cards aprovados pendentes.");
      } else {
        if (!LAST_ANKI_FILE) throw new Error("compartilhamento_indisponivel");
        LAST_ANKI_FILE.create({ overwrite: true });
        LAST_ANKI_FILE.write(resultado.tsv);
        setLastAnkiExport(true);
        await Sharing.shareAsync(LAST_ANKI_FILE.uri, {
          dialogTitle: "Salvar cards Anki",
          mimeType: "text/tab-separated-values",
          UTI: "public.tab-separated-values-text",
        });
      }
      await loadAnki();
    } catch (e: any) {
      Alert.alert(
        "Anki",
        resultado?.n
          ? `O lote foi exportado no servidor (${resultado.path ?? "TSV"}), mas não consegui compartilhar. Use “compartilhar último” se o arquivo local foi criado.`
          : e?.message ?? "não consegui exportar",
      );
    } finally {
      setAnkiBusy(null);
    }
  }

  async function compartilharUltimoAnki() {
    if (!LAST_ANKI_FILE?.exists || !(await Sharing.isAvailableAsync())) {
      setLastAnkiExport(false);
      Alert.alert("Anki", "Nenhum TSV local disponível para compartilhar.");
      return;
    }
    await Sharing.shareAsync(LAST_ANKI_FILE.uri, {
      dialogTitle: "Salvar cards Anki",
      mimeType: "text/tab-separated-values",
      UTI: "public.tab-separated-values-text",
    });
  }

  const tasks = d?.tasks ?? [];
  const cardsAtivos = ankiCards.filter(
    (card) => card.status === "sugerido" || card.status === "aprovado",
  );

  return (
    <View style={{ flex: 1, paddingTop: spacing.sm }}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
      >
        {pontosLoading && !pontos ? (
          <Skeleton height={150} style={{ marginBottom: spacing.md }} />
        ) : pontos ? (
          <Placar p={pontos} />
        ) : pontosErr ? (
          <Card style={styles.conqOff}>
            <Text style={styles.conqOffText}>placar · sem dados agora</Text>
          </Card>
        ) : null}

        {reflexaoLoading && (!semanal || !mensal) ? (
          <>
            <Skeleton height={180} />
            <Skeleton height={150} />
          </>
        ) : semanal && mensal ? (
          <Reviews
            semanal={semanal}
            mensal={mensal}
            onOpenEdificacao={onOpenEdificacao}
            onOpenMelhorias={onOpenMelhorias}
            onFecharSemana={fecharSemana}
            fechandoReview={fechandoReview}
            reviewFeito={reviewFeito}
          />
        ) : reflexaoErr ? (
          <Card style={styles.conqOff}>
            <Text style={styles.conqOffText}>review · sem dados agora</Text>
          </Card>
        ) : null}

        <Text style={styles.sectionLabel}>objetivos acumulativos</Text>
        <Card style={styles.objetivoNovo}>
          <Field
            value={novoObjetivo}
            onChangeText={setNovoObjetivo}
            placeholder="ex.: academia no ano"
          />
          <View style={styles.alvoRow}>
            <Field
              value={novoAlvo}
              onChangeText={setNovoAlvo}
              placeholder="alvo/semana"
              keyboardType="number-pad"
              style={{ flex: 1 }}
            />
            <AppButton
              title="Adicionar"
              onPress={adicionarObjetivo}
              loading={salvandoObjetivo}
              disabled={!novoObjetivo.trim()}
            />
          </View>
        </Card>

        {objetivos.map((objetivo) => {
          const atual = objetivo.progresso.semana_atual;
          const pct = atual.alvo ? Math.min(100, Math.round((atual.n / atual.alvo) * 100)) : 0;
          return (
            <Card key={objetivo.id} style={styles.objetivoCard}>
              <View style={styles.objetivoHead}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.objetivoNome}>{objetivo.nome}</Text>
                  <Text style={styles.objetivoMeta}>
                    semana {atual.n}{atual.alvo ? `/${atual.alvo}` : ""} · total {objetivo.progresso.total}
                  </Text>
                </View>
                <Pressable onPress={() => removerObjetivo(objetivo)} hitSlop={8}>
                  <Feather name="archive" size={15} color={colors.textMuted} />
                </Pressable>
              </View>
              {atual.alvo ? (
                <View style={styles.objetivoTrack}>
                  <View style={[styles.objetivoFill, { width: `${pct}%` }]} />
                </View>
              ) : null}
              {objetivo.rotina_slug ? (
                <Text style={styles.objetivoFonte}>derivado de {objetivo.rotina_slug}</Text>
              ) : (
                <View style={styles.objetivoAcoes}>
                  <Pressable style={styles.miniAction} onPress={() => marcarObjetivo(objetivo.id, true)}>
                    <Feather name="check" size={13} color={colors.primary} />
                    <Text style={styles.miniActionText}>marcar hoje</Text>
                  </Pressable>
                  <Pressable style={styles.miniAction} onPress={() => marcarObjetivo(objetivo.id, false)}>
                    <Feather name="rotate-ccw" size={12} color={colors.textMuted} />
                    <Text style={styles.miniActionMuted}>desfazer hoje</Text>
                  </Pressable>
                </View>
              )}
            </Card>
          );
        })}

        {readingPendingError ? (
          <Card style={styles.conqOff}>
            <Text style={styles.conqOffText}>sessões pendentes · indisponível agora</Text>
          </Card>
        ) : readingPending.length > 0 ? (
          <>
            <View style={styles.pendingHead}>
              <Text style={[styles.sectionLabel, { marginTop: 0, marginBottom: 0 }]}>notas por fechar</Text>
              <View style={styles.pendingBadge}>
                <Text style={styles.pendingBadgeText}>{readingPending.length}</Text>
              </View>
            </View>
            <Card style={styles.pendingCard}>
              {readingPending.map((session) => (
                <View key={session.id} style={styles.pendingRow}>
                  <Feather name="book-open" size={15} color={colors.primary} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.pendingTitle}>{session.livro || "Sessão de leitura"}</Text>
                    <Text style={styles.pendingMeta}>
                      #{session.id} · {session.status}
                      {session.pagina_inicial !== null ? ` · desde p. ${session.pagina_inicial}` : ""}
                    </Text>
                  </View>
                </View>
              ))}
              <Text style={styles.reviewHint}>
                Abra Capturar para retomar ou fechar a nota. Nada será descartado automaticamente.
              </Text>
              <Pressable style={styles.miniAction} onPress={onOpenCapture}>
                <Feather name="arrow-right" size={13} color={colors.primary} />
                <Text style={styles.miniActionText}>abrir Capturar</Text>
              </Pressable>
            </Card>
          </>
        ) : null}

        <View style={styles.ankiSectionHead}>
          <Text style={[styles.sectionLabel, { marginTop: 0, marginBottom: 0 }]}>cards Anki</Text>
          <Pressable
            onPress={exportarAnki}
            disabled={ankiBusy !== null}
            style={styles.exportBtn}
          >
            <Feather name="download" size={13} color={colors.primary} />
            <Text style={styles.exportText}>exportar aprovados</Text>
          </Pressable>
          {lastAnkiExport ? (
            <Pressable
              onPress={compartilharUltimoAnki}
              disabled={ankiBusy !== null}
              style={styles.exportBtn}
            >
              <Feather name="share-2" size={13} color={colors.textMuted} />
              <Text style={styles.exportLastText}>compartilhar último</Text>
            </Pressable>
          ) : null}
        </View>
        {ankiLoading ? (
          <Skeleton height={120} />
        ) : ankiError ? (
          <Card style={styles.conqOff}>
            <Text style={styles.conqOffText}>cards Anki · indisponível agora</Text>
          </Card>
        ) : cardsAtivos.length === 0 ? (
          <Card style={styles.conqOff}>
            <Text style={styles.conqOffText}>nenhum candidato aguardando revisão</Text>
          </Card>
        ) : (
          cardsAtivos.map((card) => (
            <Card key={card.id} style={styles.ankiCard}>
              <View style={styles.ankiHead}>
                <Text style={styles.reviewEyebrow}>{card.status}</Text>
                <Text style={styles.ankiId}>#{card.id}</Text>
              </View>
              <Text style={styles.fieldLabel}>FRENTE</Text>
              <Field
                value={card.frente}
                onChangeText={(v) => editarAnki(card.id, "frente", v)}
                editable={ankiBusy === null}
              />
              <Text style={styles.fieldLabel}>MEANING</Text>
              <Field
                value={card.meaning}
                onChangeText={(v) => editarAnki(card.id, "meaning", v)}
                multiline
                editable={ankiBusy === null}
              />
              <Text style={styles.fieldLabel}>EXAMPLE</Text>
              <Field
                value={card.example}
                onChangeText={(v) => editarAnki(card.id, "example", v)}
                multiline
                editable={ankiBusy === null}
              />
              <Text style={styles.fieldLabel}>HOOK</Text>
              <Field
                value={card.hook}
                onChangeText={(v) => editarAnki(card.id, "hook", v)}
                multiline
                editable={ankiBusy === null}
              />
              <Text style={styles.fieldLabel}>DECK</Text>
              <Field
                value={card.deck ?? ""}
                onChangeText={(v) => editarAnki(card.id, "deck", v)}
                placeholder="opcional"
                editable={ankiBusy === null}
              />
              <View style={styles.ankiActions}>
                <Pressable disabled={ankiBusy !== null} style={styles.miniAction} onPress={() => decidirAnki(card)}>
                  <Feather name="save" size={13} color={colors.textMuted} />
                  <Text style={styles.miniActionMuted}>salvar</Text>
                </Pressable>
                <Pressable disabled={ankiBusy !== null} style={styles.approveAction} onPress={() => decidirAnki(card, "aprovado")}>
                  <Feather name="check" size={14} color={colors.primaryText} />
                  <Text style={styles.approveText}>aprovar</Text>
                </Pressable>
                <Pressable disabled={ankiBusy !== null} style={styles.miniAction} onPress={() => decidirAnki(card, "descartado")}>
                  <Feather name="x" size={13} color={colors.textMuted} />
                  <Text style={styles.miniActionMuted}>descartar</Text>
                </Pressable>
              </View>
            </Card>
          ))
        )}

        <View style={styles.sectionHead}>
          <Text style={[styles.sectionLabel, { marginTop: 0, marginBottom: 0 }]}>cobranças de hoje</Text>
          <Text style={styles.sectionCount}>{d?.count ?? 0}</Text>
        </View>

        {loading ? (
          <View>
            <Skeleton height={64} />
            <Skeleton height={64} />
            <Skeleton height={64} />
          </View>
        ) : error ? (
          <ErrorState
            message="Não consegui falar com o servidor."
            hint="O BFF (backend) está rodando na rede? Toque pra tentar de novo."
            onRetry={load}
          />
        ) : tasks.length > 0 ? (
          tasks.map((t) => {
            const s = styleFor(t);
            return (
              <Pressable
                key={t.id}
                onPress={() => setDetailId(t.id)}
                style={[styles.row, { borderLeftColor: s.color }]}
              >
                <Feather name={s.icon} size={18} color={s.color} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{t.name}</Text>
                  <Text style={styles.meta}>
                    {t.due ?? t.last_done ?? ""}
                    {t.assignee ? ` · ${t.assignee}` : ""}
                  </Text>
                </View>
                <View style={[styles.areaTag, { backgroundColor: areaColor(t.area) + "22" }]}>
                  <Text style={[styles.areaTagText, { color: areaColor(t.area) }]}>{t.area}</Text>
                </View>
              </Pressable>
            );
          })
        ) : (
          <Card style={styles.emptyCard}>
            <Feather name="check-circle" size={32} color={colors.success} />
            <Text style={styles.emptyText}>tudo em dia</Text>
          </Card>
        )}
      </ScrollView>

      <TaskDetailModal
        taskId={detailId}
        onClose={() => setDetailId(null)}
        onComplete={completeById}
        onAdiada={load}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  // ---- Placar ----
  hero: { alignItems: "center", paddingTop: spacing.sm, paddingBottom: spacing.lg },
  heroSaldo: {
    fontFamily: fonts.displayBold,
    fontSize: 54,
    color: colors.text,
    letterSpacing: -1.5,
  },
  heroLabel: {
    fontFamily: fonts.mono,
    fontSize: 9,
    letterSpacing: 2,
    color: colors.textMuted,
    marginTop: 8,
  },
  nivelRow: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 10,
    marginTop: 13,
  },
  nivelTag: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.text, letterSpacing: 1 },
  nivelHint: { fontFamily: fonts.mono, fontSize: 8.5, color: colors.faint },
  diamonds: { flexDirection: "row", gap: 6 },
  diamond: {
    width: 8,
    height: 8,
    borderRadius: 2,
    borderWidth: 1,
    borderColor: colors.textMuted,
    backgroundColor: "transparent",
    transform: [{ rotate: "45deg" }],
  },
  diamondOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  conqCard: { marginBottom: spacing.md, gap: spacing.sm },
  cicloRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  cicloLabel: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 1.4, color: colors.textMuted },
  cicloPontos: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.text },
  semanaRow: { flexDirection: "row", justifyContent: "space-between", marginTop: 12 },
  ganho: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.success, flexShrink: 1 },
  desconto: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.faint, flexShrink: 1 },
  proximoNivel: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, flexShrink: 1 },
  padroes: {
    gap: 3,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  padrao: { fontFamily: fonts.mono, fontSize: 11.5, color: colors.textMuted },
  conqOff: { marginBottom: spacing.md, paddingVertical: spacing.md },
  conqOffText: { fontFamily: fonts.mono, fontSize: 11.5, color: colors.textMuted },

  sectionLabel: {
    fontFamily: fonts.mono,
    fontSize: 10.5,
    color: colors.textMuted,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  sectionHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  sectionCount: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.faint, letterSpacing: 1.4 },
  reviewCard: { gap: spacing.md, marginBottom: spacing.sm },
  monthCard: { gap: spacing.sm, marginBottom: spacing.md, backgroundColor: colors.card2 },
  reviewHead: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: spacing.md },
  reviewEyebrow: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, letterSpacing: 1 },
  reviewTitle: { fontFamily: fonts.uiSemi, fontSize: 18, color: colors.text, marginTop: 3 },
  reviewPct: { fontFamily: fonts.display, fontSize: 30, color: colors.text },
  monthPct: { fontFamily: fonts.display, fontSize: 26, color: colors.text },
  metricas: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  metrica: { minWidth: "21%", flexGrow: 1, backgroundColor: colors.card2, borderRadius: radius.md, padding: spacing.sm },
  metricaValor: { fontFamily: fonts.mono, fontSize: 15, color: colors.text },
  metricaLabel: { fontFamily: fonts.ui, fontSize: 10.5, color: colors.textMuted, marginTop: 3 },
  praticaResumo: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  praticaResumoText: { flex: 1, fontFamily: fonts.ui, fontSize: 13, color: colors.text },
  praticaLink: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  reviewHint: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted, lineHeight: 17 },
  monthObjetivo: { flexDirection: "row", justifyContent: "space-between", paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border },
  monthObjetivoNome: { flex: 1, fontFamily: fonts.ui, fontSize: 13, color: colors.text },
  monthObjetivoValor: { fontFamily: fonts.mono, fontSize: 12, color: colors.primary },

  objetivoNovo: { gap: spacing.sm, marginBottom: spacing.sm },
  alvoRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center" },
  objetivoCard: { gap: spacing.sm, marginBottom: spacing.sm },
  objetivoHead: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm },
  objetivoNome: { fontFamily: fonts.uiSemi, fontSize: 15, color: colors.text },
  objetivoMeta: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted, marginTop: 3 },
  objetivoTrack: { height: 5, borderRadius: radius.pill, backgroundColor: colors.card2, overflow: "hidden" },
  objetivoFill: { height: "100%", backgroundColor: colors.success },
  objetivoFonte: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.textMuted },
  objetivoAcoes: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  miniAction: { flexDirection: "row", alignItems: "center", gap: 5, borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 7 },
  miniActionText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.primary },
  miniActionMuted: { fontFamily: fonts.ui, fontSize: 11.5, color: colors.textMuted },
  pendingHead: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.lg, marginBottom: spacing.sm },
  pendingBadge: { minWidth: 22, height: 22, borderRadius: radius.pill, backgroundColor: colors.amber, alignItems: "center", justifyContent: "center", paddingHorizontal: 6 },
  pendingBadgeText: { fontFamily: fonts.mono, fontSize: 10.5, color: colors.primaryText },
  pendingCard: { gap: spacing.sm, borderColor: colors.amber },
  pendingRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  pendingTitle: { fontFamily: fonts.uiSemi, fontSize: 14, color: colors.text },
  pendingMeta: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, marginTop: 2 },

  ankiSectionHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.lg, marginBottom: spacing.sm },
  exportBtn: { flexDirection: "row", alignItems: "center", gap: 5, paddingVertical: 6 },
  exportText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.primary },
  exportLastText: { fontFamily: fonts.ui, fontSize: 10.5, color: colors.textMuted },
  ankiCard: { gap: spacing.sm, marginBottom: spacing.sm },
  ankiHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  ankiId: { fontFamily: fonts.mono, fontSize: 10, color: colors.textMuted },
  fieldLabel: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textMuted, letterSpacing: 1 },
  ankiActions: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: spacing.sm, marginTop: spacing.xs },
  approveAction: { flexDirection: "row", alignItems: "center", gap: 5, backgroundColor: colors.primary, borderRadius: radius.pill, paddingHorizontal: 12, paddingVertical: 8 },
  approveText: { fontFamily: fonts.uiSemi, fontSize: 11.5, color: colors.primaryText },

  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.card,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  name: { fontFamily: fonts.uiSemi, fontSize: 15.5, color: colors.text },
  meta: { fontFamily: fonts.ui, fontSize: 12.5, color: colors.textMuted, marginTop: 3 },
  areaTag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.sm },
  areaTagText: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 0.5, textTransform: "uppercase" },
  emptyCard: { alignItems: "center", paddingVertical: spacing.xl, gap: spacing.sm },
  emptyText: { fontFamily: fonts.ui, color: colors.textMuted },
});
