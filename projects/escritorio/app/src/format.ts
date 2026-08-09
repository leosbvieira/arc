// 1553 -> "1.553" (sem depender de Intl no Hermes).
// Math.abs é contrato: quem chama escreve o sinal (`−{milhar(semana.desconto)}`),
// e `desconto` já chega positivo do BFF.
export function milhar(n: number): string {
  return Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
