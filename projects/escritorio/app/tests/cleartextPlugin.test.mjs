import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { httpPermitido } = require("../plugins/withCleartextTraffic.js");

test("manifesto só libera http em desenvolvimento ou com o escape explícito", () => {
  assert.equal(httpPermitido({}), true);
  assert.equal(httpPermitido({ EXPO_PUBLIC_APP_ENV: "development" }), true);
  assert.equal(httpPermitido({ EXPO_PUBLIC_APP_ENV: "preview" }), false);
  assert.equal(httpPermitido({ EXPO_PUBLIC_APP_ENV: "preview", EXPO_PUBLIC_ALLOW_HTTP: "1" }), true);
  assert.equal(httpPermitido({ EXPO_PUBLIC_APP_ENV: "production" }), false);
});
