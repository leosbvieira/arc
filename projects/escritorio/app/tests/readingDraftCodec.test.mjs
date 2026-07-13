import assert from "node:assert/strict";
import test from "node:test";

import {
  joinSecureChunks,
  SECURE_CHUNK_CHARS,
  splitSecureChunks,
} from "../src/readingDraftCodec.ts";

test("chunk multibyte acima de 2 KB preserva texto e surrogate pairs", () => {
  const text = `quote: ${"漢".repeat(900)} ${"🧠".repeat(300)}`;
  const chunks = splitSecureChunks(text);

  assert.ok(Buffer.byteLength(text, "utf8") > 2048);
  assert.ok(chunks.length > 1);
  assert.ok(chunks.every((chunk) => chunk.length <= SECURE_CHUNK_CHARS));
  assert.ok(chunks.every((chunk) => Buffer.byteLength(chunk, "utf8") <= 1800));
  assert.equal(joinSecureChunks(chunks), text);
});
