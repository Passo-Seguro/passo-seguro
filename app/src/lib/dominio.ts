// Textos em linguagem simples para os valores do contrato.
// Os `Record<...>` são exaustivos de propósito: se o enum do openapi.yaml mudar, o build quebra aqui.
import type { Categoria, Prioridade, StatusRelato } from '../api/tipos';

/** Mesma ordem de contratos/classes.yaml. */
export const CATEGORIAS: readonly Categoria[] = ['buraco', 'piso_danificado', 'obstaculo', 'veiculo_na_calcada'];

export const ROTULO_CATEGORIA: Record<Categoria, string> = {
  buraco: 'Buraco',
  piso_danificado: 'Piso danificado',
  obstaculo: 'Obstáculo na calçada',
  veiculo_na_calcada: 'Veículo na calçada',
};

/** "É um buraco?" */
export const PERGUNTA_CATEGORIA: Record<Categoria, string> = {
  buraco: 'É um buraco?',
  piso_danificado: 'É um piso danificado?',
  obstaculo: 'É um obstáculo na calçada?',
  veiculo_na_calcada: 'É um veículo na calçada?',
};

/** Explicação curta de cada classe, para a pessoa escolher com segurança. */
export const DICA_CATEGORIA: Record<Categoria, string> = {
  buraco: 'Abertura no piso, com o chão ou a terra à mostra.',
  piso_danificado: 'Piso quebrado, solto ou desnivelado, sem abrir um buraco.',
  obstaculo: 'Algo que atrapalha a passagem: poste, entulho, lixeira, galhos.',
  veiculo_na_calcada: 'Carro, moto ou bicicleta parados em cima da calçada.',
};

export function rotuloCategoria(categoria: Categoria | null | undefined): string {
  return categoria ? (ROTULO_CATEGORIA[categoria] ?? 'Problema na calçada') : 'Problema ainda sem classificação';
}

export interface InfoStatus {
  /** Texto curto, no selo. */
  selo: string;
  /** Frase que explica o que acontece agora. */
  explicacao: string;
  /** Etapa da linha do tempo "recebido → encaminhado → resolvido" (0, 1 ou 2); -1 se não se aplica. */
  etapa: number;
}

export const INFO_STATUS: Record<StatusRelato, InfoStatus> = {
  novo: { selo: 'Recebido', explicacao: 'Recebemos seu relato. Em breve uma pessoa vai conferir.', etapa: 0 },
  revisao_humana: { selo: 'Em análise', explicacao: 'Uma pessoa está conferindo a foto e o local.', etapa: 0 },
  validado: { selo: 'Confirmado', explicacao: 'O problema foi confirmado e logo será encaminhado.', etapa: 0 },
  encaminhado: { selo: 'Encaminhado', explicacao: 'Já enviamos o caso para a subprefeitura responsável.', etapa: 1 },
  resolvido: { selo: 'Resolvido', explicacao: 'O problema foi resolvido. Obrigado por ajudar!', etapa: 2 },
  rejeitado: { selo: 'Não aceito', explicacao: 'Não foi possível aceitar este relato, por exemplo porque a foto não mostra o problema.', etapa: -1 },
};

export const ETAPAS_ACOMPANHAMENTO = ['Recebido', 'Encaminhado', 'Resolvido'] as const;

export function infoStatus(status: StatusRelato): InfoStatus {
  return INFO_STATUS[status] ?? { selo: 'Em andamento', explicacao: 'Seu relato está em andamento.', etapa: 0 };
}

export interface InfoPrioridade {
  /** Texto do rótulo (nunca só cor). */
  rotulo: string;
  /** Texto curto, dentro do marcador do mapa. */
  curto: string;
  /** Símbolo que acompanha a cor. */
  simbolo: string;
}

export const INFO_PRIORIDADE: Record<Prioridade, InfoPrioridade> = {
  alta: { rotulo: 'Prioridade alta', curto: 'Alta', simbolo: '▲' },
  media: { rotulo: 'Prioridade média', curto: 'Média', simbolo: '◆' },
  baixa: { rotulo: 'Prioridade baixa', curto: 'Baixa', simbolo: '●' },
};

export const SEM_PRIORIDADE: InfoPrioridade = { rotulo: 'Ainda sem prioridade', curto: 'Nova', simbolo: '○' };

export function infoPrioridade(prioridade: Prioridade | null | undefined): InfoPrioridade {
  return (prioridade && INFO_PRIORIDADE[prioridade]) || SEM_PRIORIDADE;
}

export function formatarData(iso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return '';
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(data);
}
