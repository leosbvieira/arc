// Design tokens do escritório — direção "midnight desk" (premium mono).
// Dark é o tema principal (Leo é noturno); light fica pronto pro toggle.

type Palette = {
  bg: string;
  surface: string;
  card: string;
  card2: string;
  border: string;
  text: string;
  textMuted: string;
  primary: string; // accent bronze
  primaryText: string;
  primarySoft: string;
  amber: string; // alias do accent (compat)
  danger: string;
  success: string;
  userBubble: string;
};

export const dark: Palette = {
  bg: "#0A0A0C",
  surface: "#121214",
  card: "#1A1A1D",
  card2: "#151518",
  border: "rgba(255,255,255,0.08)",
  text: "#F4F4F5",
  textMuted: "#9A9AA2",
  primary: "#C9A97E",
  primaryText: "#1A130A",
  primarySoft: "rgba(201,169,126,0.12)",
  amber: "#C9A97E",
  danger: "#DE8A7A",
  success: "#6FB58C",
  userBubble: "#26262C",
};

export const light: Palette = {
  bg: "#FAFAF9",
  surface: "#FFFFFF",
  card: "#FFFFFF",
  card2: "#F4F4F5",
  border: "rgba(0,0,0,0.09)",
  text: "#18181B",
  textMuted: "#71717A",
  primary: "#A9834F",
  primaryText: "#FFFFFF",
  primarySoft: "rgba(169,131,79,0.12)",
  amber: "#A9834F",
  danger: "#C56A5A",
  success: "#4E9A72",
  userBubble: "#ECECEF",
};

// Padrão do escritório = dark. (O ThemeProvider da fundação troca isto por light quando o usuário quiser.)
export const colors = dark;

// Uma cor por área de vida (tom médio, dessaturado). As 10 áreas normativas (Task 6).
export const AREA_COLORS: Record<string, string> = {
  Trabalho: "#C9A97E", Staging: "#8A8A93", Corpo: "#7FA98E",
  "Saúde Mental": "#9B8EC4", Responsabilidade: "#A9A18C", Finance: "#6BA8A0",
  Carreira: "#7E9AC9", Estudo: "#C9BC7E", Relacionamentos: "#C98E9B", Lazer: "#D98A6E",
};

export function areaColor(area: string): string {
  return AREA_COLORS[area] ?? "#8A8A93";
}

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };

export const radius = { sm: 8, md: 12, lg: 16, xl: 20, pill: 999 };

export const shadow = {
  shadowColor: "#000000",
  shadowOpacity: 0.5,
  shadowRadius: 24,
  shadowOffset: { width: 0, height: 12 },
  elevation: 8,
};

// Famílias de fonte — carregadas via expo-font no App (próximo passo da fundação).
// Fallback pro system enquanto não carregam.
export const fonts = {
  ui: "SpaceGrotesk_500Medium",
  uiSemi: "SpaceGrotesk_600SemiBold",
  uiBold: "SpaceGrotesk_700Bold",
  serif: "Fraunces_500Medium",
  mono: "IBMPlexMono_500Medium",
};
