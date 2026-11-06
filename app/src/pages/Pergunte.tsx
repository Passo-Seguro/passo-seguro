import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { perguntarAoAssistente } from '../api/cliente';
import type { FonteCitada } from '../api/tipos';
import { Pagina } from '../components/Pagina';

const LIMITE = 500;

const SUGESTOES = [
  'Quem conserta uma calçada quebrada em frente ao meu prédio?',
  'Como reclamar de um carro estacionado na calçada?',
  'Como peço o conserto de um buraco na calçada?',
];

interface Mensagem {
  id: number;
  de: 'pessoa' | 'assistente';
  texto: string;
  fontes?: FonteCitada[];
  /** Falha de rede/API (não é a recusa do assistente). */
  falha?: boolean;
}

/** Só abre links http(s): nunca `javascript:` ou outros esquemas vindos da resposta. */
export function urlSegura(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
}

function Fontes({ fontes }: { fontes: FonteCitada[] }) {
  if (fontes.length === 0) return null;
  return (
    <div className="fontes">
      <p className="fontes-titulo">Fontes</p>
      <ul>
        {fontes.map((f, i) => {
          const href = urlSegura(f.url);
          return (
            <li key={`${f.titulo}-${i}`}>
              {href ? (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {f.titulo}
                  <span aria-hidden="true"> ↗</span>
                  <span className="so-leitor"> (abre em uma nova aba)</span>
                </a>
              ) : (
                f.titulo
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function Pergunte() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const proximoId = useRef(1);
  const fim = useRef<HTMLDivElement>(null);
  const controlador = useRef<AbortController>(undefined);

  useEffect(() => () => controlador.current?.abort(), []);
  useEffect(() => {
    fim.current?.scrollIntoView?.({ block: 'nearest' });
  }, [mensagens, enviando]);

  async function perguntar(pergunta: string) {
    const limpa = pergunta.trim();
    if (!limpa || enviando) return;
    setTexto('');
    setMensagens((m) => [...m, { id: proximoId.current++, de: 'pessoa', texto: limpa }]);
    setEnviando(true);
    controlador.current = new AbortController();
    try {
      const r = await perguntarAoAssistente(limpa, controlador.current.signal);
      // Resposta normal e recusa têm o mesmo destaque: a recusa também é uma resposta útil.
      setMensagens((m) => [...m, { id: proximoId.current++, de: 'assistente', texto: r.resposta, fontes: r.fontes }]);
    } catch (e) {
      if (controlador.current.signal.aborted) return;
      console.warn('Falha ao falar com o assistente', e);
      setMensagens((m) => [
        ...m,
        {
          id: proximoId.current++,
          de: 'assistente',
          falha: true,
          texto:
            'Não consegui falar com o assistente agora. O resto do app continua funcionando. Se for urgente, ligue 156 (Prefeitura de São Paulo).',
        },
      ]);
    } finally {
      setEnviando(false);
    }
  }

  function enviar(e: FormEvent) {
    e.preventDefault();
    void perguntar(texto);
  }

  return (
    <Pagina titulo="Pergunte ao assistente" tituloDocumento="Pergunte">
      <p>
        Tire dúvidas sobre quem conserta uma calçada e como reclamar. O assistente mostra as fontes da resposta e pode
        errar: confira os links.
      </p>

      {mensagens.length === 0 && (
        <section aria-labelledby="titulo-sugestoes">
          <h2 id="titulo-sugestoes">Por onde começar</h2>
          <ul className="sugestoes">
            {SUGESTOES.map((s) => (
              <li key={s}>
                <button type="button" className="botao botao-secundario" onClick={() => void perguntar(s)} disabled={enviando}>
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversa com o assistente" className="conversa">
        {mensagens.map((m) => (
          <article
            key={m.id}
            className={`balao ${m.de === 'pessoa' ? 'balao-pessoa' : 'balao-assistente'}${m.falha ? ' balao-falha' : ''}`}
          >
            <p className="balao-autor">{m.de === 'pessoa' ? 'Você' : 'Assistente'}</p>
            <p className="balao-texto">{m.texto}</p>
            {m.fontes && <Fontes fontes={m.fontes} />}
            {m.falha && (
              <p>
                <Link to="/reportar">Registrar um problema agora</Link>
              </p>
            )}
          </article>
        ))}
        {enviando && (
          <p role="status" className="balao balao-assistente balao-espera">
            O assistente está pensando…
          </p>
        )}
        <div ref={fim} />
      </div>

      <form onSubmit={enviar} className="formulario-pergunta">
        <label htmlFor="pergunta" className="rotulo">
          Sua pergunta
        </label>
        <div className="linha-pergunta">
          <input
            id="pergunta"
            name="pergunta"
            type="text"
            autoComplete="off"
            maxLength={LIMITE}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            aria-describedby="limite-pergunta"
            placeholder="Escreva aqui"
          />
          <button type="submit" className="botao botao-primario" disabled={enviando || texto.trim() === ''}>
            Enviar
          </button>
        </div>
        <p id="limite-pergunta" className="dica">
          Até {LIMITE} caracteres. Não escreva dados pessoais.
        </p>
      </form>
    </Pagina>
  );
}
