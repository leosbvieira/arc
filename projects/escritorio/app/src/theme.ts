// Design tokens do escritório — direção "midnight desk" (premium mono).
// Dark é o tema principal (Leo é noturno); light fica pronto pro toggle.

type Palette = {
  bg: string;
  bgRaised: string;
  surface: string;
  card: string;
  card2: string;
  border: string;
  text: string;
  textMuted: string;
  faint: string; // metadado: pontos em repouso, um degrau abaixo do muted
  primary: string; // accent bronze
  primaryText: string;
  primarySoft: string;
  amber: string; // alias do accent (compat)
  danger: string;
  success: string;
  info: string;
  lilac: string;
  userBubble: string;
};

export const dark: Palette = {
  bg: "#080A0D",
  bgRaised: "#0C0F13",
  surface: "#0E1116",
  card: "#15191F",
  card2: "#11151A",
  border: "rgba(235,222,202,0.11)",
  text: "#F4EFE7",
  textMuted: "#9A9BA3",
  faint: "#5F626B",
  primary: "#DEB878",
  primaryText: "#181108",
  primarySoft: "rgba(222,184,120,0.13)",
  amber: "#DEB878",
  danger: "#D77969",
  success: "#71B49A",
  info: "#7D9FD0",
  lilac: "#A99ACB",
  userBubble: "#222831",
};

export const light: Palette = {
  bg: "#FAFAF9",
  bgRaised: "#F2F0EC",
  surface: "#FFFFFF",
  card: "#FFFFFF",
  card2: "#F4F4F5",
  border: "rgba(0,0,0,0.09)",
  text: "#18181B",
  textMuted: "#71717A",
  faint: "#A1A1AA",
  primary: "#A9834F",
  primaryText: "#FFFFFF",
  primarySoft: "rgba(169,131,79,0.12)",
  amber: "#A9834F",
  danger: "#C56A5A",
  success: "#4E9A72",
  info: "#557DB7",
  lilac: "#8172AA",
  userBubble: "#ECECEF",
};

// Padrão do escritório = dark. (O ThemeProvider da fundação troca isto por light quando o usuário quiser.)
export const colors = dark;

// PROVISÓRIA e display-only: pontos por tipo de ação não existem no app nem no
// BFF. Esta tabela só alimenta rótulos ("vale +N", "garante +N") — o saldo
// oficial de getPontos() sempre vence. Valores da proposta C2 aprovada.
export const POINTS = {
  tarefa: 10,
  rotina: 20,
  captura: 5,
  fechamento: 80,
  shutdown: 30,
  despejoBonus: 40,
} as const;

// Uma cor por área de vida (tom médio, dessaturado). As 10 áreas normativas (Task 6).
export const AREA_COLORS: Record<string, string> = {
  Trabalho: "#C9A97E", Staging: "#8A8A93", Corpo: "#7FA98E",
  "Saúde Mental": "#9B8EC4", Responsabilidade: "#A9A18C", Finance: "#6BA8A0",
  Carreira: "#7E9AC9", Estudo: "#C9BC7E", Relacionamentos: "#C98E9B", Lazer: "#D98A6E",
};

export function areaColor(area: string): string {
  return AREA_COLORS[area] ?? "#8A8A93";
}

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 40 };

export const radius = { sm: 8, md: 12, lg: 16, xl: 20, pill: 999 };

export const shadow = {
  shadowColor: "#000000",
  shadowOpacity: 0.28,
  shadowRadius: 18,
  shadowOffset: { width: 0, height: 10 },
  elevation: 5,
};

// Famílias de fonte — carregadas via expo-font no App.
// Onda 2: Bricolage Grotesque assume o corpo/UI; Syne fica só no display
// (título de tela, saudação, herói, valor de stat). `serif` não existe mais de
// propósito: qualquer sítio esquecido vira erro de compilação no typecheck.
// Se o corpo em 400 ficar leve demais no aparelho, a correção é uma linha:
// ui: "BricolageGrotesque_500Medium".
export const fonts = {
  ui: "BricolageGrotesque_400Regular",
  uiMedium: "BricolageGrotesque_500Medium",
  uiSemi: "BricolageGrotesque_600SemiBold",
  uiBold: "BricolageGrotesque_700Bold",
  display: "Syne_600SemiBold",
  displayBold: "Syne_700Bold",
  mono: "IBMPlexMono_500Medium",
};
