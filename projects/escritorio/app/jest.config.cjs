// Testes de TELA (React Native Testing Library) — só os `.test.tsx` em tests/ui/.
// Os módulos puros continuam no `node --test tests/*.test.mjs`, sem Jest, sem Babel:
// os dois convivem porque este config não enxerga `.mjs` e o node não enxerga `.tsx`.
module.exports = {
  preset: "jest-expo",
  testMatch: ["<rootDir>/tests/ui/**/*.test.tsx"],
  setupFilesAfterEnv: ["<rootDir>/tests/ui/setup.tsx"],
  clearMocks: true,
  restoreMocks: true,
};
