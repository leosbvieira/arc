#!/usr/bin/env bash
# Dispara UM rito do escritório no BFF local: o que o `nudge.ps1` e o `run-digest.ps1`
# faziam pelo Agendador do Windows quando o BFF morava no PC.
#
# Quem chama: `escritorio-rito@<script>-<slug>.service`, acordado pelo timer
# `escritorio-rito-<slug>.timer`. Os timers NÃO são escritos à mão: saem de
# `bff/ritos.json` (`python -m app.ritos`, chamado pelo vps-install.sh).
#
# O que fica com o BFF, e não aqui: a janela do rito (`ritos.atrasado`), o dedupe do dia
# e a reserva atômica do slot. Este script só bate na porta — chamar duas vezes é seguro,
# e fora da hora o nudge responde `skipped: atrasado` sem avisar ninguém.
set -euo pipefail

ALVO="${1:?uso: escritorio-rito <nudge|digest>-<slug>}"
TIPO="${ALVO%%-*}"
SLUG="${ALVO#*-}"
BFF="${RITO_BFF:-http://127.0.0.1:8000}"
ENV_BFF="${RITO_ENV_BFF:-/etc/escritorio/bff.env}"
TENTATIVAS="${RITO_TENTATIVAS:-12}"   # de 5s em 5s pelo /health

[[ "$SLUG" =~ ^[a-z0-9_]+$ ]] || { echo "rito $ALVO: slug inválido"; exit 2; }
case "$TIPO" in
  nudge)  CAMINHO=/internal/nudge;      CORPO="{\"kind\":\"$SLUG\"}"; PRAZO=120 ;;
  digest) CAMINHO=/internal/run-digest; CORPO="";                     PRAZO=300 ;;
  *) echo "rito $ALVO: tipo desconhecido (nudge-<slug> ou digest-<slug>)"; exit 2 ;;
esac

[ -r "$ENV_BFF" ] || { echo "rito $ALVO: não consigo ler $ENV_BFF"; exit 1; }
token="$(sed -n 's/^INTERNAL_TOKEN=//p' "$ENV_BFF" | head -1 | tr -d '"\r')"
[ -n "$token" ] || { echo "rito $ALVO: INTERNAL_TOKEN vazio em $ENV_BFF"; exit 1; }

# Um restart de deploy na hora do rito não pode custar o aviso do dia: espera o BFF
# voltar (o `nudge.ps1` fazia o mesmo). Se não voltar, sai != 0 e aparece em
# `systemctl --failed` — BFF fora do ar é falha, não silêncio.
n=0
until curl -fsS -m 5 -o /dev/null "$BFF/health" 2>/dev/null; do
  n=$((n + 1))
  [ "$n" -lt "$TENTATIVAS" ] || { echo "rito $ALVO: o BFF não respondeu ao /health"; exit 1; }
  sleep 5
done

# O token vai por stdin (-K -) pra não aparecer na lista de processos.
resp="$(printf 'header = "X-Internal-Token: %s"\n' "$token" \
  | curl -sS -m "$PRAZO" -K - -X POST -H 'Content-Type: application/json' \
      ${CORPO:+--data "$CORPO"} -w '\n%{http_code}' "$BFF$CAMINHO")" \
  || { echo "rito $ALVO: a chamada ao BFF falhou"; exit 1; }
codigo="${resp##*$'\n'}"
corpo="${resp%$'\n'*}"

# Só o veredito vai pro journal, nunca o corpo inteiro: nada do que é do Leo entra em
# log (lei 7).
veredito="$(printf '%s' "$corpo" \
  | grep -oE '"(ok|push|telegram)": ?(true|false)|"skipped": ?(true|"[^"]*")|"count": ?[0-9]+' \
  | tr '\n' ' ' || true)"
echo "rito $ALVO: HTTP $codigo ${veredito:-(sem veredito)}"
[ "$codigo" = 200 ]
