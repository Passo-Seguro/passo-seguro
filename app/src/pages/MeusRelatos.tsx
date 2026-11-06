import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { listarMeusRelatos } from '../api/cliente';
import type { RelatoResumo } from '../api/tipos';
import { IconeGaleria, IconeRelogio, IconeX } from '../components/Icones';
import { Pagina } from '../components/Pagina';
import { SeloStatus } from '../components/Selos';
import { useFila } from '../hooks/useFila';
import { useOnline } from '../hooks/useOnline';
import { obterAutorId } from '../lib/autor';
import { ETAPAS_ACOMPANHAMENTO, formatarData, infoStatus, rotuloCategoria } from '../lib/dominio';
import { descartar, fotoComoBlob, tentarAgora, type FotoGuardada as FotoNaFila, type ItemFila } from '../offline/fila';

type Carga = { fase: 'carregando' } | { fase: 'erro' } | { fase: 'ok'; itens: RelatoResumo[] };

function FotoRelato({ url }: { url: string }) {
  const [falhou, setFalhou] = useState(false);
  if (falhou) {
    return (
      <div className="foto-indisponivel" role="img" aria-label="Foto indisponível no momento">
        <IconeGaleria width="2em" height="2em" />
      </div>
    );
  }
  return <img src={url} alt="Foto do relato" className="foto-relato" loading="lazy" onError={() => setFalhou(true)} />;
}

/** Miniatura da foto guardada no aparelho (lida como data URL: não precisa liberar nada depois). */
function FotoGuardada({ foto }: { foto: FotoNaFila | null }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!foto) return;
    const blob = fotoComoBlob(foto);
    let ativo = true;
    const leitor = new FileReader();
    leitor.onload = () => ativo && setUrl(String(leitor.result));
    leitor.readAsDataURL(blob);
    return () => {
      ativo = false;
    };
  }, [foto]);
  if (!url) {
    return (
      <div className="foto-indisponivel" role="img" aria-label="Foto guardada neste aparelho">
        <IconeGaleria width="2em" height="2em" />
      </div>
    );
  }
  return <img src={url} alt="Foto guardada neste aparelho" className="foto-relato" />;
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

function CartaoAguardando({ item }: { item: ItemFila }) {
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const falhou = item.estado === 'falhou';

  async function tentar() {
    setOcupado(true);
    try {
      await tentarAgora(item.idLocal);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <li className="cartao cartao-relato">
      <FotoGuardada foto={item.foto} />
      <div className="cartao-corpo">
        <h3 className="cartao-titulo">Relato guardado neste aparelho</h3>
        <p className="cartao-detalhe">Feito em {formatarData(item.criadoEm)}</p>
        <p className="selos">
          {falhou ? (
            <span className="selo selo-status-rejeitado">
              <IconeX /> Não foi possível enviar
            </span>
          ) : (
            <span className="selo selo-fila">
              <IconeRelogio /> {item.estado === 'enviando' ? 'Enviando agora…' : 'Aguardando envio'}
            </span>
          )}
        </p>
        <p>
          {falhou
            ? 'O servidor não aceitou este relato. Você pode tentar de novo ou descartá-lo.'
            : item.tentativas > 0
              ? `Ainda sem conexão com o servidor (${item.tentativas} ${item.tentativas === 1 ? 'tentativa' : 'tentativas'}). Vamos tentar de novo sozinhos.`
              : 'Vamos enviar assim que a conexão voltar.'}
        </p>
        {confirmando ? (
          <div className="acoes">
            <button type="button" className="botao botao-perigo" onClick={() => void descartar(item.idLocal)}>
              Sim, descartar
            </button>
            <button type="button" className="botao botao-secundario" onClick={() => setConfirmando(false)}>
              Não, manter
            </button>
          </div>
        ) : (
          <div className="acoes">
            <button type="button" className="botao botao-secundario" onClick={() => void tentar()} disabled={ocupado}>
              {ocupado ? 'Enviando…' : 'Tentar agora'}
            </button>
            <button type="button" className="botao botao-secundario" onClick={() => setConfirmando(true)}>
              Descartar
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

export function MeusRelatos() {
  const [carga, setCarga] = useState<Carga>({ fase: 'carregando' });
  const [tentativa, setTentativa] = useState(0);
  const online = useOnline();
  const fila = useFila();

  // Recarrega a lista do servidor quando a conexão volta e quando algo da fila é enviado.
  const pendentes = fila.itens.length;
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
  }, [tentativa, online, pendentes]);

  function tentarDeNovo() {
    setCarga({ fase: 'carregando' });
    setTentativa((t) => t + 1);
  }

  const semNada = carga.fase === 'ok' && carga.itens.length === 0 && fila.itens.length === 0;

  return (
    <Pagina titulo="Meus relatos">
      {fila.itens.length > 0 && (
        <section aria-labelledby="titulo-fila">
          <h2 id="titulo-fila">Aguardando envio ({fila.itens.length})</h2>
          <ol className="cartoes">
            {fila.itens.map((item) => (
              <CartaoAguardando key={item.idLocal} item={item} />
            ))}
          </ol>
        </section>
      )}

      {carga.fase === 'carregando' && (
        <p role="status" className="carregando">
          Carregando seus relatos…
        </p>
      )}

      {carga.fase === 'erro' && (
        <div role="alert" className={online ? 'anuncio anuncio-erro' : 'anuncio anuncio-info'}>
          <p>
            {online
              ? 'Não consegui carregar seus relatos enviados agora. Tente de novo em instantes.'
              : 'Você está sem internet, por isso não consigo mostrar os relatos já enviados.'}
          </p>
          <button type="button" className="botao botao-secundario" onClick={tentarDeNovo}>
            Tentar de novo
          </button>
        </div>
      )}

      {semNada && (
        <div className="vazio">
          <p>Você ainda não fez nenhum relato neste aparelho.</p>
          <Link to="/reportar" className="botao botao-primario">
            Reportar um problema
          </Link>
        </div>
      )}

      {carga.fase === 'ok' && carga.itens.length > 0 && (
        <section aria-labelledby="titulo-enviados">
          <h2 id="titulo-enviados">{fila.itens.length > 0 ? 'Já enviados' : 'Relatos enviados'}</h2>
          <ol className="cartoes">
            {carga.itens.map((r) => {
              const info = infoStatus(r.status);
              return (
                <li key={r.id} className="cartao cartao-relato">
                  <FotoRelato url={r.foto_url} />
                  <div className="cartao-corpo">
                    <h3 className="cartao-titulo">{rotuloCategoria(r.categoria)}</h3>
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
        </section>
      )}
    </Pagina>
  );
}
