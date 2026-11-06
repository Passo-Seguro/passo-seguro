import { useState } from 'react';
import { Link } from 'react-router';
import { gravarLocal, lerLocal } from '../lib/armazenamento';

const CHAVE = 'passo-seguro.aviso-privacidade-visto';

/** Aviso curto na primeira abertura. Não bloqueia o uso: fica no topo da página até a pessoa dispensar. */
export function AvisoPrivacidade() {
  const [visivel, setVisivel] = useState(() => lerLocal(CHAVE) !== '1');
  if (!visivel) return null;

  return (
    <section className="aviso-privacidade" aria-labelledby="titulo-aviso-privacidade">
      <h2 id="titulo-aviso-privacidade">Sua privacidade</h2>
      <p>
        Para registrar um problema, guardamos a <strong>foto</strong>, o <strong>local</strong> (no mapa público ele
        aparece arredondado, a cerca de 100 m), o <strong>texto</strong> que você escrever e um{' '}
        <strong>número anônimo</strong> deste aparelho. Usamos só para identificar o problema, encaminhá-lo à
        subprefeitura e mostrar seus relatos para você. Não pedimos nome, e-mail nem login.
      </p>
      <div className="aviso-acoes">
        <button
          type="button"
          className="botao botao-primario"
          onClick={() => {
            gravarLocal(CHAVE, '1');
            setVisivel(false);
          }}
        >
          Entendi
        </button>
        <Link to="/privacidade" className="botao botao-secundario">
          Saiba mais
        </Link>
      </div>
    </section>
  );
}
