export type MotivoFalhaLocalizacao = 'negado' | 'indisponivel' | 'tempo_esgotado' | 'sem_suporte';

export class ErroLocalizacao extends Error {
  readonly motivo: MotivoFalhaLocalizacao;

  constructor(motivo: MotivoFalhaLocalizacao) {
    super(motivo);
    this.name = 'ErroLocalizacao';
    this.motivo = motivo;
  }
}

export interface Ponto {
  lat: number;
  lon: number;
}

/** Posição por GPS. Em HTTP pela rede local o navegador nega: a tela cai no toque no mapa. */
export function obterLocalizacao(tempoMs = 12000): Promise<Ponto> {
  return new Promise((resolve, reject) => {
    if (!('geolocation' in navigator)) {
      reject(new ErroLocalizacao('sem_suporte'));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (posicao) => resolve({ lat: posicao.coords.latitude, lon: posicao.coords.longitude }),
      (erro) => {
        if (erro.code === erro.PERMISSION_DENIED) reject(new ErroLocalizacao('negado'));
        else if (erro.code === erro.TIMEOUT) reject(new ErroLocalizacao('tempo_esgotado'));
        else reject(new ErroLocalizacao('indisponivel'));
      },
      { enableHighAccuracy: true, timeout: tempoMs, maximumAge: 30000 },
    );
  });
}

export const CENTRO_PADRAO: Ponto = { lat: -23.5505, lon: -46.6333 }; // Praça da Sé
