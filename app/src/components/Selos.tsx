import type { ReactNode } from 'react';
import type { Prioridade, StatusRelato } from '../api/tipos';
import { infoPrioridade, infoStatus } from '../lib/dominio';
import { IconeCheck, IconeEnvelope, IconeLupa, IconeSeta, IconeX } from './Icones';

/** Prioridade sempre com símbolo + texto, nunca só cor. */
export function SeloPrioridade({ prioridade }: { prioridade: Prioridade | null | undefined }) {
  const info = infoPrioridade(prioridade);
  return (
    <span className={`selo selo-prioridade-${prioridade ?? 'nenhuma'}`}>
      <span aria-hidden="true" className="selo-simbolo">
        {info.simbolo}
      </span>{' '}
      {info.rotulo}
    </span>
  );
}

const ICONE_STATUS: Record<StatusRelato, ReactNode> = {
  novo: <IconeEnvelope />,
  revisao_humana: <IconeLupa />,
  validado: <IconeCheck />,
  encaminhado: <IconeSeta />,
  resolvido: <IconeCheck />,
  rejeitado: <IconeX />,
};

export function SeloStatus({ status }: { status: StatusRelato }) {
  const info = infoStatus(status);
  return (
    <span className={`selo selo-status-${status}`}>
      {ICONE_STATUS[status]} {info.selo}
    </span>
  );
}
