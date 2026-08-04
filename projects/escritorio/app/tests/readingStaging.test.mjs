import assert from "node:assert/strict";
import test from "node:test";

import { readingPreviewFromSession } from "../src/readingStaging.ts";

test("sessão pending com draft_md vira preview read-only", () => {
  assert.equal(
    readingPreviewFromSession({ status: "pending", draft_md: "# Nota\n- ideia" }),
    "# Nota\n- ideia",
  );
});

test("pending sem rascunho segue no editor cru (null)", () => {
  assert.equal(readingPreviewFromSession({ status: "pending", draft_md: null }), null);
  assert.equal(readingPreviewFromSession({ status: "pending", draft_md: "" }), null);
  assert.equal(readingPreviewFromSession({ status: "pending" }), null);
});

test("estados não-pending nunca abrem preview, mesmo com draft_md", () => {
  for (const status of ["compiling", "compiled", "discarded"]) {
    assert.equal(
      readingPreviewFromSession({ status, draft_md: "# resto de rascunho" }),
      null,
    );
  }
});
