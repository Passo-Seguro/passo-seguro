import { useState } from 'react';
import { Link } from 'react-router';
import { Anuncio } from '../components/Anuncio';
import { IconeMais, IconePino } from '../components/Icones';
import { MapaRelatos, type ComandoMapa } from '../components/MapaRelatos';
import { Pagina } from '../components/Pagina';
import { SeloPrioridade, SeloStatus } from '../components/Selos';
import { usePainelDoMapa } from '../hooks/usePainelDoMapa';
import { useRelatosProximos } from '../hooks/useRelatosProximos';
import { INFO_PRIORIDADE, SEM_PRIORIDADE, infoPrioridade, rotuloCategoria } from '../lib/dominio';
import { CENTRO_PADRAO, ErroLocalizacao, obterLocalizacao } from '../lib/localizacao';
import { ATRIBUICAO_GEOSAMPA, OPACIDADE_FAIXA } from '../lib/subprefeituras';

const POR_PAGINA = 20;

const LEGENDA = [
  { chave: 'alta', info: INFO_PRIORIDADE.alta, explicacao: 'prioridade alta' },
  { chave: 'media', info: INFO_PRIORIDADE.media, explicacao: 'prioridade média' },
  { chave: 'baixa', info: INFO_PRIORIDADE.baixa, explicacao: 'prioridade baixa' },
  { chave: 'nenhuma', info: SEM_PRIORIDADE, explicacao: 'ainda sem prioridade' },
];

const FAIXAS = [
  { chave: 'alta', texto: 'mais prioritárias' },
  { chave: 'media', texto: 'intermediárias' },
  { chave: 'baixa', texto: 'menos prioritárias' },
] as const;

export function Mapa() {
  const { itens, carregando, erro, buscar, tentarDeNovo } = useRelatosProximos();
  const [camadaLigada, setCamadaLigada] = useState(false);
  const { painel, tentarDeNovo: recarregarPainel } = usePainelDoMapa(camadaLigada);
  const [comando, setComando] = useState<ComandoMapa | null>(null);
  // Objeto novo a cada clique: pedir o mesmo relato duas vezes reabre o balão.
  const [abrir, setAbrir] = useState<{ id: string } | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [procurando, setProcurando] = useState(false);
  const [visiveis, setVisiveis] = useState(POR_PAGINA);

  async function irParaMim() {
    setAviso(null);
    setProcurando(true);
    try {
      const p = await obterLocalizacao();
      setComando((c) => ({ ...p, id: (c?.id ?? 0) + 1 }));
    } catch (e) {
      const motivo = e instanceof ErroLocalizacao ? e.motivo : 'indisponivel';
      setAviso(
        motivo === 'negado' || motivo === 'sem_suporte'
          ? 'Não consegui usar sua localização. Você ainda pode arrastar o mapa até onde quiser.'
          : 'Não encontrei sua localização agora. Tente de novo ou arraste o mapa.',
      );
    } finally {
      setProcurando(false);
    }
  }

  function verNoMapa(id: string, lat: number, lon: number) {
    setComando((c) => ({ lat, lon, id: (c?.id ?? 0) + 1, zoom: 17 }));
    setAbrir({ id });
    document.getElementById('mapa-regiao')?.scrollIntoView({ block: 'center' });
  }

  return (
    <Pagina titulo="Problemas perto de você" tituloDocumento="Mapa" className="pagina-mapa">
      <div className="barra-mapa">
        <button type="button" className="botao botao-secundario" onClick={irParaMim} disabled={procurando}>
          <IconePino /> {procurando ? 'Procurando…' : 'Usar minha localização'}
        </button>
        <label className="camada-opcao">
          <input type="checkbox" checked={camadaLigada} onChange={(e) => setCamadaLigada(e.target.checked)} />
          Mostrar prioridade por subprefeitura
        </label>
      </div>
      {painel.fase === 'carregando' && (
        <p role="status" className="dica">
          Carregando as subprefeituras…
        </p>
      )}
      {painel.fase === 'indisponivel' && (
        <p role="status" className="dica">
          O painel de prioridades ainda não tem dados, então não há o que mostrar por subprefeitura.
        </p>
      )}
      {painel.fase === 'erro' && (
        <div role="alert" className="anuncio anuncio-erro">
          <p>Não consegui carregar as subprefeituras agora. O mapa continua funcionando.</p>
          <button type="button" className="botao botao-secundario" onClick={recarregarPainel}>
            Tentar de novo
          </button>
        </div>
      )}
      <Anuncio mensagem={aviso} tipo="info" />

      <div className="mapa-layout">
        <div className="mapa-coluna">
          <div id="mapa-regiao">
            <MapaRelatos
              centro={CENTRO_PADRAO}
              relatos={itens}
              comando={comando}
              abrir={abrir}
              onAreaMudou={buscar}
              subprefeituras={painel.fase === 'ok' ? painel.linhas : null}
            />
          </div>

          <ul className="legenda" aria-label="Como ler os marcadores do mapa">
            {LEGENDA.map(({ chave, info, explicacao }) => (
              <li key={chave}>
                <span className={`marcador marcador-${chave}`} aria-hidden="true">
                  {info.simbolo} {info.curto}
                </span>{' '}
                {explicacao}
              </li>
            ))}
          </ul>

          {painel.fase === 'ok' && (
            <div className="legenda-camada">
              <ul className="legenda" aria-label="Como ler as subprefeituras do mapa">
                {FAIXAS.map(({ chave, texto }) => (
                  <li key={chave}>
                    <span
                      className="amostra-faixa"
                      style={{ background: `rgba(11, 42, 60, ${OPACIDADE_FAIXA[chave]})` }}
                      aria-hidden="true"
                    />{' '}
                    {texto}
                  </li>
                ))}
                <li>
                  <span className="amostra-faixa amostra-sem-dados" aria-hidden="true" /> sem dados no painel
                </li>
              </ul>
              <p className="dica">
                Faixas relativas entre as 32 subprefeituras, pelo índice de atropelamentos de pedestres e reclamações de
                calçada. Toque numa subprefeitura para ver os números, ou veja todas no{' '}
                <Link to="/painel">painel</Link>. {ATRIBUICAO_GEOSAMPA}.
              </p>
            </div>
          )}

        </div>

        <div className="mapa-lista">
          <Link to="/reportar" className="botao botao-fixo">
            <IconeMais /> Reportar problema
          </Link>

          <section aria-labelledby="titulo-lista">
            <h2 id="titulo-lista">Lista de problemas nesta região</h2>
            <p role="status" className="contagem">
              {carregando
                ? 'Buscando problemas…'
                : erro
                  ? ''
                  : itens.length === 0
                    ? 'Nenhum problema registrado nesta região ainda.'
                    : itens.length === 1
                      ? '1 problema nesta região.'
                      : `${itens.length} problemas nesta região, do mais perto ao mais longe.`}
            </p>
            {erro && (
              <div role="alert" className="anuncio anuncio-erro">
                <p>Não consegui carregar os problemas desta região. O resto do app continua funcionando.</p>
                <button type="button" className="botao botao-secundario" onClick={tentarDeNovo}>
                  Tentar de novo
                </button>
              </div>
            )}
            <ol className="cartoes">
              {itens.slice(0, visiveis).map((r) => (
                <li key={r.id} className="cartao">
                  <p className="cartao-titulo">{rotuloCategoria(r.categoria)}</p>
                  <p className="selos">
                    <SeloPrioridade prioridade={r.prioridade} /> <SeloStatus status={r.status} />
                  </p>
                  <p className="cartao-detalhe">
                    {r.confirmacoes === 1 ? '1 pessoa confirmou' : `${r.confirmacoes} pessoas confirmaram`}
                  </p>
                  <button
                    type="button"
                    className="botao botao-secundario"
                    onClick={() => verNoMapa(r.id, r.lat, r.lon)}
                    aria-label={`Ver no mapa: ${rotuloCategoria(r.categoria)}, ${infoPrioridade(r.prioridade).rotulo}`}
                  >
                    Ver no mapa
                  </button>
                </li>
              ))}
            </ol>
            {itens.length > visiveis && (
              <button
                type="button"
                className="botao botao-secundario"
                onClick={() => setVisiveis((v) => v + POR_PAGINA)}
              >
                Mostrar mais {Math.min(POR_PAGINA, itens.length - visiveis)}
              </button>
            )}
          </section>
        </div>
      </div>
    </Pagina>
  );
}
