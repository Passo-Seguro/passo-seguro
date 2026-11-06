import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { obterPainel } from '../api/cliente';
import type { PrioridadeSubprefeitura } from '../api/tipos';
import { Pagina } from '../components/Pagina';
import { SeloPrioridade } from '../components/Selos';
import { CATEGORIAS, ROTULO_CATEGORIA, formatarData } from '../lib/dominio';

type Carga =
  | { fase: 'carregando' }
  | { fase: 'erro' }
  | { fase: 'vazio' }
  | { fase: 'ok'; linhas: PrioridadeSubprefeitura[] };

const numero = new Intl.NumberFormat('pt-BR');
const decimal = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 });

function Cartao({ linha }: { linha: PrioridadeSubprefeitura }) {
  const maior = Math.max(1, ...CATEGORIAS.map((c) => linha.relatos_por_categoria[c] ?? 0));
  return (
    <li className="cartao cartao-painel">
      <h2 className="cartao-titulo">{linha.subprefeitura}</h2>
      <p className="selos">
        <SeloPrioridade prioridade={linha.prioridade} />
      </p>

      <p className="painel-total">
        <span className="painel-numero">{numero.format(linha.relatos_abertos)}</span>{' '}
        {linha.relatos_abertos === 1 ? 'relato aberto' : 'relatos abertos'}
      </p>

      <table className="tabela-categorias">
        <caption className="so-leitor">Relatos abertos por tipo de problema em {linha.subprefeitura}</caption>
        <thead>
          <tr>
            <th scope="col">Tipo de problema</th>
            <th scope="col">Relatos</th>
          </tr>
        </thead>
        <tbody>
          {CATEGORIAS.map((c) => {
            const n = linha.relatos_por_categoria[c] ?? 0;
            return (
              <tr key={c}>
                <th scope="row">{ROTULO_CATEGORIA[c]}</th>
                <td>
                  <div className="celula-barra">
                    <span className="barra" aria-hidden="true">
                      <span className="barra-preenchida" style={{ width: `${(n / maior) * 100}%` }} />
                    </span>
                    <span className="barra-valor">{numero.format(n)}</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <p className="cartao-detalhe">
        Tempo médio até o reparo:{' '}
        <strong>
          {linha.tempo_medio_ate_reparo_dias == null
            ? 'ainda sem reparos registrados'
            : `${decimal.format(linha.tempo_medio_ate_reparo_dias)} dias`}
        </strong>
      </p>
    </li>
  );
}

export function Painel() {
  const [carga, setCarga] = useState<Carga>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    const controlador = new AbortController();
    obterPainel(controlador.signal)
      .then((linhas) => setCarga(linhas === null || linhas.length === 0 ? { fase: 'vazio' } : { fase: 'ok', linhas }))
      .catch((e) => {
        if (controlador.signal.aborted) return;
        console.warn('Falha ao carregar o painel', e);
        setCarga({ fase: 'erro' });
      });
    return () => controlador.abort();
  }, [tentativa]);

  const atualizadoEm =
    carga.fase === 'ok'
      ? carga.linhas.map((l) => l.atualizado_em).sort().at(-1)
      : undefined;

  return (
    <Pagina titulo="Painel de prioridades" tituloDocumento="Painel" className="pagina-painel">
      <p>Onde há mais relatos de calçadas abertos, por subprefeitura. As mais prioritárias aparecem primeiro.</p>

      {carga.fase === 'carregando' && (
        <p role="status" className="carregando">
          Carregando o painel…
        </p>
      )}

      {carga.fase === 'vazio' && (
        <div className="vazio" role="status">
          <p className="vazio-titulo">Ainda não há dados no painel</p>
          <p>Os números aparecem aqui assim que o pipeline de dados enviar a primeira atualização.</p>
          <Link to="/" className="botao botao-secundario">
            Voltar ao mapa
          </Link>
        </div>
      )}

      {carga.fase === 'erro' && (
        <div role="alert" className="anuncio anuncio-erro">
          <p>Não consegui carregar o painel agora. O resto do app continua funcionando.</p>
          <button type="button" className="botao botao-secundario" onClick={() => {
            setCarga({ fase: 'carregando' });
            setTentativa((t) => t + 1);
          }}>
            Tentar de novo
          </button>
        </div>
      )}

      {carga.fase === 'ok' && (
        <>
          {atualizadoEm && <p className="cartao-detalhe">Dados atualizados em {formatarData(atualizadoEm)}.</p>}
          <ol className="cartoes cartoes-painel">
            {carga.linhas.map((linha) => (
              <Cartao key={linha.subprefeitura} linha={linha} />
            ))}
          </ol>
        </>
      )}
    </Pagina>
  );
}
