// Regra de pontos do fechamento das 21h — o rótulo do BigAction do rito
// ("garante +80 · bônus até +140" no mockup aprovado). Módulo puro: sem
// react-native e sem imports de runtime, para rodar sob `node --test`
// (padrão do repo: os módulos testados não importam nada — o Node exigiria
// a extensão .ts que o tsconfig do app não permite). A tabela de pontos
// entra por parâmetro: quem chama passa `tarifas` de `DEFAULT_PARAMS`
// (parametrosCore), que é PROVISÓRIA e display-only — isto alimenta o
// rótulo do botão, não o saldo; quem pontua de verdade é o BFF no approve.
//
// As duas grandezas são a mesma família, em função do dia inteiro:
// - garantido = o que o toque registra AGORA: o fechamento, mais as rotinas
//   já marcadas, mais o bônus do despejo se já há texto escrito. Escrever
//   nunca é portão. O número SOBE conforme ele marca.
// - teto = o máximo do DIA, constante enquanto ele trabalha: o fechamento,
//   todas as rotinas do dia e o bônus do despejo. Não se move quando ele
//   marca nem quando escreve.
// - Quando teto === garantido (marcou tudo e escreveu), o rótulo colapsa
//   para "garante +N", sem prometer bônus que não existe.

import type { DEFAULT_PARAMS } from "./parametrosCore";

export type PointsTable = typeof DEFAULT_PARAMS.tarifas;

export function closingReward(
  rotinasMarcadas: number,
  totalRotinas: number,
  temTexto: boolean,
  points: PointsTable,
): { garantido: number; teto: number } {
  const garantido =
    points.fechamento +
    rotinasMarcadas * points.rotina +
    (temTexto ? points.despejo : 0);
  const teto = points.fechamento + totalRotinas * points.rotina + points.despejo;
  return { garantido, teto };
}

export function closingLabel(
  rotinasMarcadas: number,
  totalRotinas: number,
  temTexto: boolean,
  points: PointsTable,
): string {
  const { garantido, teto } = closingReward(rotinasMarcadas, totalRotinas, temTexto, points);
  if (teto === garantido) return `garante +${garantido}`;
  return `garante +${garantido} · bônus até +${teto}`;
}
