// Design tokens do escritório — paleta, espaçamento, raios, sombra.

export const colors = {
  bg: "#F5F6F8",
  card: "#FFFFFF",
  border: "#E6E8EB",
  text: "#0F172A",
  textMuted: "#64748B",
  primary: "#4F46E5",
  primaryText: "#FFFFFF",
  danger: "#EF4444",
  amber: "#F59E0B",
  success: "#10B981",
};

// Uma cor por área de vida (D-2).
export const AREA_COLORS: Record<string, string> = {
  Trabalho: "#3B82F6",
  "Finanças": "#10B981",
  "Saúde": "#EF4444",
  Pessoal: "#8B5CF6",
};

export function areaColor(area: string): string {
  return AREA_COLORS[area] ?? "#94A3B8";
}

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };

export const radius = { sm: 8, md: 12, lg: 16, pill: 999 };

export const shadow = {
  shadowColor: "#0F172A",
  shadowOpacity: 0.06,
  shadowRadius: 8,
  shadowOffset: { width: 0, height: 2 },
  elevation: 2,
};
