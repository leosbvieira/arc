import assert from "node:assert/strict";
import test from "node:test";

import {
  ReadingApiError,
  readingErrorDetail,
} from "../src/readingApiError.ts";

test("expõe somente o detail tipado para reconciliação", () => {
  const error = new ReadingApiError(409, "reading_session_nao_editavel");

  assert.equal(error.status, 409);
  assert.equal(readingErrorDetail(error), "reading_session_nao_editavel");
  assert.equal(readingErrorDetail(new Error("segredo")), null);
});
