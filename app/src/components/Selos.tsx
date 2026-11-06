import type { Prioridade, StatusRelato } from '../api/tipos';
import { infoPrioridade, infoStatus } from '../lib/dominio';

/** Prioridade sempre com símbolo + texto, nunca só cor. */
export function SeloPrioridade({ prioridade }: { prioridade: Prioridade | null | undefined }) {
  const info = infoPrioridade(prioridade);
  return (
    <span className={`selo selo-prioridade-${prioridade ?? 'nenhuma'}`}>
      <span aria-hidden="true">{info.simbolo}</span> {info.rotulo}
    </span>
  );
}

const SIMBOLO_STATUS: Record<StatusRelato, string> = {
  novo: '✉',
  revisao_humana: '🔍',
  validado: '✔',
  encaminhado: '➜',
  resolvido: '✔',
  rejeitado: '✖',
};

export function SeloStatus({ status }: { status: StatusRelato }) {
  const info = infoStatus(status);
  return (
    <span className={`selo selo-status-${status}`}>
      <span aria-hidden="true">{SIMBOLO_STATUS[status] ?? '•'}</span> {info.selo}
    </span>
  );
}
