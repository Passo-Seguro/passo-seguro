import { useRef, type ChangeEvent } from 'react';

export interface FotoPronta {
  blob: Blob;
  url: string;
  kb: number;
}

interface Props {
  foto: FotoPronta | null;
  preparando: boolean;
  onArquivo: (arquivo: File) => void;
  onContinuar: () => void;
}

export function EtapaFoto({ foto, preparando, onArquivo, onContinuar }: Props) {
  const camera = useRef<HTMLInputElement>(null);
  const galeria = useRef<HTMLInputElement>(null);

  function escolheu(e: ChangeEvent<HTMLInputElement>) {
    const arquivo = e.target.files?.[0];
    e.target.value = ''; // permite escolher a mesma foto de novo
    if (arquivo) onArquivo(arquivo);
  }

  return (
    <>
      <p>Fotografe o problema de perto. Evite mostrar rostos e placas de carros.</p>

      {foto && (
        <figure className="previa">
          <img src={foto.url} alt="Foto do problema que você escolheu" />
          <figcaption>Foto pronta ({foto.kb} KB)</figcaption>
        </figure>
      )}
      <p role="status" className="status-linha">
        {preparando ? 'Preparando a foto…' : ''}
      </p>

      <div className="acoes">
        <button
          type="button"
          className={foto ? 'botao botao-secundario' : 'botao botao-primario'}
          onClick={() => camera.current?.click()}
          disabled={preparando}
        >
          <span aria-hidden="true">📷</span> {foto ? 'Tirar outra foto' : 'Tirar foto'}
        </button>
        <button type="button" className="botao botao-secundario" onClick={() => galeria.current?.click()} disabled={preparando}>
          <span aria-hidden="true">🖼</span> Escolher da galeria
        </button>
        {foto && (
          <button type="button" className="botao botao-primario" onClick={onContinuar} disabled={preparando}>
            Continuar
          </button>
        )}
      </div>

      <input ref={camera} type="file" accept="image/*" capture="environment" hidden aria-label="Tirar foto com a câmera" onChange={escolheu} />
      <input ref={galeria} type="file" accept="image/*" hidden aria-label="Escolher foto da galeria" onChange={escolheu} />
    </>
  );
}
