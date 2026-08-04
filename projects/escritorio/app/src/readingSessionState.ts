const LOCAL_CLEAR_SAFE_DETAILS = new Set([
  "reading_session_compiled",
  "reading_session_discarded",
  "reading_session_descartada",
  "reading_session_nao_encontrada",
]);

export function canClearLocalAfterDiscardFailure(detail: string | null): boolean {
  return detail !== null && LOCAL_CLEAR_SAFE_DETAILS.has(detail);
}

export function formatReadingElapsed(rawSeconds: number): string {
  const seconds = Number.isFinite(rawSeconds)
    ? Math.max(0, Math.floor(rawSeconds))
    : 0;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds % 60;

  if (hours > 0) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  return `${minutes}m ${String(remaining).padStart(2, "0")}s`;
}

export function normalizeReadingActiveSeconds(
  value: unknown,
  startedAt: number,
  updatedAt: number,
): number {
  const inferred = Math.floor((updatedAt - startedAt) / 1000);
  const candidate = typeof value === "number" && Number.isFinite(value)
    ? Math.floor(value)
    : inferred;
  return Math.min(24 * 60 * 60, Math.max(0, candidate));
}
