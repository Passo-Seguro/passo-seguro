import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { listarMeusRelatos } from '../api/cliente';
import type { RelatoResumo } from '../api/tipos';
import { Pagina } from '../components/Pagina';
import { SeloStatus } from '../components/Selos';
import { obterAutorId } from '../lib/autor';
import { ETAPAS_ACOMPANHAMENTO, formatarData, infoStatus, rotuloCategoria } from '../lib/dominio';

type Carga = { fase: 'carregando' } | { fase: 'erro' } | { fase: 'ok'; itens: RelatoResumo[] };

function FotoRelato({ url }: { url: string }) {
  const [falhou, setFalhou] = useState(false);
  if (falhou) {
    return (
      <div className="foto-indisponivel" role="img" aria-label="Foto indisponível no momento">
        <span aria-hidden="true">🖼</span>
      </div>
    );
  }
  return <img src={url} alt="Foto do relato" className="foto-relato" loading="lazy" onError={() => setFalhou(true)} />;
}

function Acompanhamento({ etapa }: { etapa: number }) {
  if (etapa < 0) return null;
  return (
    <ol className="etapas" aria-label="Andamento do relato">
      {ETAPAS_ACOMPANHAMENTO.map((nome, i) => {
        const estado = i < etapa ? 'feita' : i === etapa ? 'atual' : 'futura';
        const simbolo = estado === 'feita' ? '✔' : estado === 'atual' ? '●' : '○';
        const leitor = estado === 'feita' ? 'concluída' : estado === 'atual' ? 'etapa atual' : 'ainda não chegou';
        return (
          <li key={nome} className={`etapa etapa-${estado}`}>
            <span aria-hidden="true">{simbolo}</span> {nome} <span className="so-leitor">({leitor})</span>
          </li>
        );
      })}
    </ol>
  );
}

export function MeusRelatos() {
  const [carga, setCarga] = useState<Carga>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);

  useEffect(() => {
    const controlador = new AbortController();
    listarMeusRelatos(obterAutorId(), controlador.signal)
      .then((itens) => setCarga({ fase: 'ok', itens }))
      .catch((e) => {
        if (controlador.signal.aborted) return;
        console.warn('Falha ao carregar meus relatos', e);
        setCarga({ fase: 'erro' });
      });
    return () => controlador.abort();
  }, [tentativa]);

  function tentarDeNovo() {
    setCarga({ fase: 'carregando' });
    setTentativa((t) => t + 1);
  }

  return (
    <Pagina titulo="Meus relatos">
      {carga.fase === 'carregando' && (
        <p role="status" className="carregando">
          Carregando seus relatos…
        </p>
      )}

      {carga.fase === 'erro' && (
        <div role="alert" className="anuncio anuncio-erro">
          <p>Não consegui carregar seus relatos agora. Confira a internet e tente de novo.</p>
          <button type="button" className="botao botao-secundario" onClick={tentarDeNovo}>
            Tentar de novo
          </button>
        </div>
      )}

      {carga.fase === 'ok' && carga.itens.length === 0 && (
        <div className="vazio">
          <p>Você ainda não fez nenhum relato neste aparelho.</p>
          <Link to="/reportar" className="botao botao-primario">
            Reportar um problema
          </Link>
        </div>
      )}

      {carga.fase === 'ok' && carga.itens.length > 0 && (
        <ol className="cartoes">
          {carga.itens.map((r) => {
            const info = infoStatus(r.status);
            return (
              <li key={r.id} className="cartao cartao-relato">
                <FotoRelato url={r.foto_url} />
                <div className="cartao-corpo">
                  <h2 className="cartao-titulo">{rotuloCategoria(r.categoria)}</h2>
                  <p className="cartao-detalhe">Enviado em {formatarData(r.criado_em)}</p>
                  <p className="selos">
                    <SeloStatus status={r.status} />
                  </p>
                  <p>{info.explicacao}</p>
                  <Acompanhamento etapa={info.etapa} />
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Pagina>
  );
}
