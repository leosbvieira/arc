export type ParsedReadingEntry = {
  kind?: string;
  book?: string;
  text: string;
};

function spokenPrefix(text: string): { command: string; rest: string } {
  const match = text.match(/^(\S+?)(?=\s|[:;,.!?]|$)/u);
  if (!match) return { command: "", rest: text };

  const command = match[1]
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("pt-BR");
  const rest = text
    .slice(match[1].length)
    .replace(/^\s*(?:[:;,.!?\-–—]\s*)?/u, "")
    .trim();

  return { command, rest };
}

export function parseReadingEntry(raw: string): ParsedReadingEntry {
  const text = raw.trim();
  const { command, rest } = spokenPrefix(text);

  if (command === "livro") return { book: rest, text: "" };
  if (command === "citacao" || command === "quote") {
    return { kind: "citação", text: rest };
  }
  if (command === "comentario") {
    return { kind: "comentário", text: rest };
  }
  if (["ideia", "coach", "lista"].includes(command)) {
    return { kind: command, text: rest };
  }

  return { kind: "comentário", text };
}
