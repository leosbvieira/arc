// Uma sessão remota está "staged" quando o rascunho da nota já foi gerado
// (draft_md presente) mas ainda não foi para o vault — o status segue "pending"
// e o buffer está congelado no servidor. Nesse estado a Captura reabre em
// preview read-only em vez do editor cru, e NÃO deve re-sincronizar o buffer
// (um append devolveria 409 reading_draft_ja_gerado).
//
// Retorna o markdown do preview quando staged, ou null caso contrário — para
// ser usado direto como valor do estado `preview`.
export function readingPreviewFromSession(
  session: { status: string; draft_md?: string | null },
): string | null {
  if (session.status !== "pending") return null;
  const draft = session.draft_md;
  return typeof draft === "string" && draft.length > 0 ? draft : null;
}
