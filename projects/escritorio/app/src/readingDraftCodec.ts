export const SECURE_CHUNK_CHARS = 600;

export function splitSecureChunks(value: string): string[] {
  const chunks: string[] = [];
  let start = 0;
  while (start < value.length) {
    let end = Math.min(start + SECURE_CHUNK_CHARS, value.length);
    if (end < value.length) {
      const code = value.charCodeAt(end - 1);
      if (code >= 0xd800 && code <= 0xdbff) end -= 1;
    }
    chunks.push(value.slice(start, end));
    start = end;
  }
  return chunks.length ? chunks : [""];
}

export function joinSecureChunks(chunks: string[]): string {
  return chunks.join("");
}

export function safeSessionKey(sessionKey: string): string {
  return sessionKey.replace(/[^A-Za-z0-9._-]/g, "_");
}
