import assert from "node:assert/strict";
import test from "node:test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { conferirBffUrl, ehHttpsComHost } = require("../app.config.js");

test("https precisa de host: 'https://' sozinho não é servidor", () => {
  assert.equal(ehHttpsComHost("https://escritorio.exemplo.com"), true);
  assert.equal(ehHttpsComHost("https://"), false);
  assert.equal(ehHttpsComHost("http://192.168.0.2:8000"), false);
  assert.equal(ehHttpsComHost(""), false);
  assert.equal(ehHttpsComHost("HTTPS://x"), true);
});

test("produção recusa build sem https com host, salvo o escape explícito", () => {
  const config = { extra: { bffUrl: "http://192.168.0.2:8000" } };
  assert.throws(() => conferirBffUrl(config, { EXPO_PUBLIC_APP_ENV: "production" }), /exige BFF https/);
  assert.throws(
    () => conferirBffUrl(config, { EXPO_PUBLIC_APP_ENV: "production", EXPO_PUBLIC_BFF_URL: "https://" }),
    /exige BFF https/,
  );
  assert.doesNotThrow(() =>
    conferirBffUrl(config, { EXPO_PUBLIC_APP_ENV: "production", EXPO_PUBLIC_BFF_URL: "https://bff.exemplo.com" }),
  );
  assert.doesNotThrow(() => conferirBffUrl(config, { EXPO_PUBLIC_APP_ENV: "preview", EXPO_PUBLIC_ALLOW_HTTP: "1" }));
  assert.doesNotThrow(() => conferirBffUrl(config, { EXPO_PUBLIC_APP_ENV: "development" }));
});
