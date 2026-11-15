import { useEffect, useState } from 'react';
import L from 'leaflet';
import { GeoJSON, Popup, useMap } from 'react-leaflet';
import { Link } from 'react-router';
import type { PrioridadeSubprefeitura } from '../api/tipos';
import { estiloDaFaixa, indexarPorNome, carregarPoligonos, type PoligonoSubprefeitura } from '../lib/subprefeituras';
import { SeloPrioridade } from './Selos';

const numero = new Intl.NumberFormat('pt-BR');
const indice = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 3 });

function BalaoSubprefeitura({ nome, linha }: { nome: string; linha: PrioridadeSubprefeitura | undefined }) {
  return (
    <>
      <strong>{nome}</strong>
      <br />
      {linha ? (
        <>
          <SeloPrioridade prioridade={linha.prioridade} />
          {linha.indice_prioridade != null && <p className="balao-linha">Índice de prioridade: {indice.format(linha.indice_prioridade)}</p>}
          {linha.atropelamentos_pedestres != null && (
            <p className="balao-linha">Atropelamentos de pedestres: {numero.format(linha.atropelamentos_pedestres)}</p>
          )}
          {linha.reclamacoes_calcada_sp156 != null && (
            <p className="balao-linha">Reclamações de calçada: {numero.format(linha.reclamacoes_calcada_sp156)}</p>
          )}
          <p className="balao-linha">
            <Link to="/painel">Ver no painel</Link>
          </p>
        </>
      ) : (
        <p className="balao-linha">Sem dados desta subprefeitura no painel.</p>
      )}
    </>
  );
}

/**
 * Camada de subprefeituras do mapa: as 32 pintadas pela faixa de prioridade do painel.
 * Ao ligar, enquadra a cidade inteira (com o zoom da rua a camada seria só uma mancha).
 * Se o arquivo de polígonos não carregar, o mapa segue sem a camada.
 */
export function CamadaSubprefeituras({ linhas }: { linhas: PrioridadeSubprefeitura[] }) {
  const mapa = useMap();
  const [poligonos, setPoligonos] = useState<PoligonoSubprefeitura[] | null>(null);

  useEffect(() => {
    let ativo = true;
    carregarPoligonos()
      .then((p) => ativo && setPoligonos(p))
      .catch((e) => console.warn('Falha ao carregar os limites das subprefeituras', e));
    return () => {
      ativo = false;
    };
  }, []);

  useEffect(() => {
    if (!poligonos) return;
    const limites = L.geoJSON(poligonos).getBounds();
    if (limites.isValid()) mapa.fitBounds(limites, { padding: [8, 8] });
  }, [poligonos, mapa]);

  if (!poligonos) return null;
  const porNome = indexarPorNome(linhas);
  return (
    <>
      {poligonos.map((p) => {
        const nome = p.properties.subprefeitura;
        const linha = porNome.get(nome);
        // `key` com a faixa: o react-leaflet não reaplica `style` sozinho quando o painel muda.
        return (
          <GeoJSON key={`${nome}:${linha?.prioridade ?? '-'}`} data={p} style={estiloDaFaixa(linha?.prioridade)}>
            <Popup>
              <BalaoSubprefeitura nome={nome} linha={linha} />
            </Popup>
          </GeoJSON>
        );
      })}
    </>
  );
}
