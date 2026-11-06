import { useState } from 'react';
import type { Categoria } from '../../api/tipos';
import { CATEGORIAS, DICA_CATEGORIA, ROTULO_CATEGORIA } from '../../lib/dominio';
import type { FotoPronta } from './EtapaFoto';

interface Props {
  foto: FotoPronta;
  /** Classe detectada pela IA; `null` quando ela não identificou nada. */
  detectada: Categoria | null;
  salvando: boolean;
  onEscolher: (categoria: Categoria) => void;
  onNaoSei: () => void;
}

/** "É um buraco?" → Sim / Não, é outro. Quando a IA não identificou, mostra direto as 4 opções. */
export function EtapaClasse({ foto, detectada, salvando, onEscolher, onNaoSei }: Props) {
  const [corrigindo, setCorrigindo] = useState(detectada === null);
  const [escolhida, setEscolhida] = useState<Categoria | null>(null);

  return (
    <>
      <img src={foto.url} alt="Foto que você enviou" className="miniatura miniatura-grande" />

      {detectada && !corrigindo && (
        <>
          <p>
            Pelo que vi na foto, parece ser: <strong>{ROTULO_CATEGORIA[detectada]}</strong>. Sua resposta ajuda a
            encaminhar o caso certo.
          </p>
          <div className="acoes">
            <button type="button" className="botao botao-primario" onClick={() => onEscolher(detectada)} disabled={salvando}>
              {salvando ? 'Salvando…' : 'Sim, é isso'}
            </button>
            <button type="button" className="botao botao-secundario" onClick={() => setCorrigindo(true)} disabled={salvando}>
              Não, é outro problema
            </button>
          </div>
        </>
      )}

      {corrigindo && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (escolhida) onEscolher(escolhida);
          }}
        >
          <fieldset className="opcoes">
            <legend>{detectada ? 'Qual é o problema?' : 'Não consegui identificar, qual é o problema?'}</legend>
            {CATEGORIAS.map((c) => (
              <label key={c} className="opcao">
                <input
                  type="radio"
                  name="categoria"
                  value={c}
                  checked={escolhida === c}
                  onChange={() => setEscolhida(c)}
                />
                <span>
                  <strong>{ROTULO_CATEGORIA[c]}</strong>
                  <span className="dica">{DICA_CATEGORIA[c]}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <div className="acoes acoes-navegacao">
            {detectada ? (
              <button type="button" className="botao botao-secundario" onClick={() => setCorrigindo(false)} disabled={salvando}>
                Voltar
              </button>
            ) : (
              <button type="button" className="botao botao-secundario" onClick={onNaoSei} disabled={salvando}>
                Não sei dizer
              </button>
            )}
            <button type="submit" className="botao botao-primario" disabled={!escolhida || salvando}>
              {salvando ? 'Salvando…' : 'Confirmar'}
            </button>
          </div>
        </form>
      )}
    </>
  );
}
