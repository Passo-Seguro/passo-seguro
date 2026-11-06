import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { Ponto } from '../lib/localizacao';
import { ATRIBUICAO_OSM, URL_TILES } from './MapaRelatos';

interface Props {
  centro: Ponto;
  ponto: Ponto | null;
  onEscolher: (ponto: Ponto) => void;
  /** Recebe uma função que lê o centro atual do mapa (para o botão "usar o centro do mapa"). */
  registrarLeitorDeCentro: (ler: () => Ponto) => void;
}

const ICONE_PINO = L.divIcon({
  className: 'marcador-alvo',
  iconSize: [88, 44],
  iconAnchor: [44, 44], // a ponta do pino fica no ponto marcado, com o rótulo acima da mira
  html: '<span class="marcador marcador-pino"><span aria-hidden="true">Aqui</span></span>',
});

function Toques({ onEscolher }: Pick<Props, 'onEscolher'>) {
  useMapEvents({ click: (e) => onEscolher({ lat: e.latlng.lat, lon: e.latlng.lng }) });
  return null;
}

function Ponte({ registrar, ponto }: { registrar: Props['registrarLeitorDeCentro']; ponto: Ponto | null }) {
  const mapa = useMap();
  useEffect(() => {
    registrar(() => {
      const c = mapa.getCenter();
      return { lat: c.lat, lon: c.lng };
    });
  }, [mapa, registrar]);

  // Quando o GPS (ou o botão) define o ponto, leva o mapa até ele.
  const ultimo = useRef<Ponto | null>(null);
  useEffect(() => {
    if (ponto && ponto !== ultimo.current) mapa.setView([ponto.lat, ponto.lon], Math.max(mapa.getZoom(), 17));
    ultimo.current = ponto;
  }, [ponto, mapa]);
  return null;
}

/** Mapa para marcar onde está o problema: toque no mapa, ou mire no centro e use o botão da tela. */
export function SeletorLocal({ centro, ponto, onEscolher, registrarLeitorDeCentro }: Props) {
  return (
    <div
      className="mapa-seletor"
      role="region"
      aria-label="Mapa para marcar o local do problema. Toque no mapa, ou use o botão abaixo para marcar o centro."
    >
      <MapContainer center={[centro.lat, centro.lon]} zoom={17} className="mapa mapa-pequeno">
        <TileLayer url={URL_TILES} attribution={ATRIBUICAO_OSM} maxZoom={19} />
        <Toques onEscolher={onEscolher} />
        <Ponte registrar={registrarLeitorDeCentro} ponto={ponto} />
        {ponto && <Marker position={[ponto.lat, ponto.lon]} icon={ICONE_PINO} keyboard={false} />}
      </MapContainer>
      <div className="mira" aria-hidden="true" />
    </div>
  );
}
