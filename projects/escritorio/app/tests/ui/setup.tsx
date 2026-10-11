// Infra dos testes de tela. Portado do ramo local-2026-09 (12/09/2026), só o que a
// arquitetura da nuvem usa: SecureStore em memória (a fila offline e o token moram
// nele), fetch proibido por padrão (cada teste diz o que o servidor responde) e
// parâmetros do app sem servidor.

const mockMemoria = new Map<string, string>();

jest.mock("expo-secure-store", () => ({
  getItemAsync: async (k: string) => mockMemoria.get(k) ?? null,
  setItemAsync: async (k: string, v: string) => {
    mockMemoria.set(k, v);
  },
  deleteItemAsync: async (k: string) => {
    mockMemoria.delete(k);
  },
}));

jest.mock("expo-linear-gradient", () => {
  const { View } = jest.requireActual("react-native");
  return { LinearGradient: View };
});

jest.mock("@expo/vector-icons/Feather", () => {
  const { Text } = jest.requireActual("react-native");
  return (props: { name: string }) => <Text>{`icon:${props.name}`}</Text>;
});

jest.mock("react-native-safe-area-context", () =>
  jest.requireActual("react-native-safe-area-context/jest/mock").default,
);

// Sem servidor: a tarifa e os ritos vêm do default embutido.
jest.mock("../../src/parametros", () => {
  const { DEFAULT_PARAMS } = jest.requireActual("../../src/parametrosCore");
  return { useParams: () => DEFAULT_PARAMS };
});

beforeEach(() => {
  mockMemoria.clear();
  jest.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    throw new Error(`fetch não configurado neste teste: ${String(url)}`);
  });
});

export const secureStoreEmMemoria = mockMemoria;
