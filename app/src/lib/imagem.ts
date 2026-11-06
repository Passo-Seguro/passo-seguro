// Compressão da foto no celular antes do envio: lado maior ~1280 px, JPEG, ~300 KB.
export const LADO_MAXIMO = 1280;
export const ALVO_BYTES = 300 * 1024;
const QUALIDADE_MAXIMA = 0.9;
const QUALIDADE_MINIMA = 0.4;
const PASSOS_BUSCA = 5;
const ESCALAS = [1, 0.85, 0.7, 0.55];

export class ErroImagem extends Error {
  constructor(mensagem: string) {
    super(mensagem);
    this.name = 'ErroImagem';
  }
}

/** Reduz mantendo a proporção, sem ampliar. */
export function dimensoesAlvo(largura: number, altura: number, ladoMaximo = LADO_MAXIMO): { largura: number; altura: number } {
  const maior = Math.max(largura, altura);
  if (maior <= ladoMaximo) return { largura, altura };
  const fator = ladoMaximo / maior;
  return { largura: Math.max(1, Math.round(largura * fator)), altura: Math.max(1, Math.round(altura * fator)) };
}

/**
 * Busca binária da maior qualidade JPEG que ainda cabe em `alvo` bytes.
 * Devolve `null` se nem a qualidade mínima couber.
 */
export async function melhorQualidade(
  codificar: (qualidade: number) => Promise<Blob>,
  alvo = ALVO_BYTES,
): Promise<Blob | null> {
  let baixa = QUALIDADE_MINIMA;
  let alta = QUALIDADE_MAXIMA;
  let melhor: Blob | null = null;

  const maxima = await codificar(alta);
  if (maxima.size <= alvo) return maxima;

  const minima = await codificar(baixa);
  if (minima.size > alvo) return null;
  melhor = minima;

  for (let i = 0; i < PASSOS_BUSCA; i++) {
    const meio = (baixa + alta) / 2;
    const tentativa = await codificar(meio);
    if (tentativa.size <= alvo) {
      melhor = tentativa;
      baixa = meio;
    } else {
      alta = meio;
    }
  }
  return melhor;
}

interface Origem {
  fonte: CanvasImageSource;
  largura: number;
  altura: number;
  liberar: () => void;
}

async function abrirImagem(arquivo: Blob): Promise<Origem> {
  if (typeof createImageBitmap === 'function') {
    try {
      // "from-image": respeita a rotação do EXIF (foto em pé não pode sair deitada).
      const bitmap = await createImageBitmap(arquivo, { imageOrientation: 'from-image' });
      return { fonte: bitmap, largura: bitmap.width, altura: bitmap.height, liberar: () => bitmap.close() };
    } catch {
      /* tenta pelo elemento <img> */
    }
  }
  const url = URL.createObjectURL(arquivo);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return { fonte: img, largura: img.naturalWidth, altura: img.naturalHeight, liberar: () => URL.revokeObjectURL(url) };
  } catch {
    URL.revokeObjectURL(url);
    throw new ErroImagem('Não consegui ler essa foto. Tente outra.');
  }
}

function paraBlob(canvas: HTMLCanvasElement, qualidade: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new ErroImagem('Não consegui preparar a foto.'))),
      'image/jpeg',
      qualidade,
    );
  });
}

export interface FotoComprimida {
  blob: Blob;
  largura: number;
  altura: number;
}

/** Redimensiona e recomprime a foto para JPEG de ~300 KB (lado maior até 1280 px). */
export async function comprimirImagem(arquivo: Blob, alvo = ALVO_BYTES): Promise<FotoComprimida> {
  if (arquivo.type && !arquivo.type.startsWith('image/')) {
    throw new ErroImagem('Esse arquivo não é uma foto.');
  }
  const origem = await abrirImagem(arquivo);
  try {
    let menor: FotoComprimida | null = null;
    for (const escala of ESCALAS) {
      const base = dimensoesAlvo(origem.largura, origem.altura);
      const largura = Math.max(1, Math.round(base.largura * escala));
      const altura = Math.max(1, Math.round(base.altura * escala));
      const canvas = document.createElement('canvas');
      canvas.width = largura;
      canvas.height = altura;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new ErroImagem('Seu navegador não conseguiu preparar a foto.');
      ctx.fillStyle = '#ffffff'; // PNG com transparência viraria preto no JPEG
      ctx.fillRect(0, 0, largura, altura);
      ctx.drawImage(origem.fonte, 0, 0, largura, altura);

      const dentroDoAlvo = await melhorQualidade((q) => paraBlob(canvas, q), alvo);
      if (dentroDoAlvo) return { blob: dentroDoAlvo, largura, altura };
      // Nem a qualidade mínima coube: guarda a menor tentativa e reduz mais as dimensões.
      const minima = await paraBlob(canvas, QUALIDADE_MINIMA);
      if (!menor || minima.size < menor.blob.size) menor = { blob: minima, largura, altura };
    }
    return menor as FotoComprimida;
  } finally {
    origem.liberar();
  }
}
