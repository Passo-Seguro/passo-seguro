import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';
import { MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { RelatoProximo } from '../api/tipos';
import { infoPrioridade, infoStatus, rotuloCategoria } from '../lib/dominio';
import type { Ponto } from '../lib/localizacao';
import { SeloPrioridade, SeloStatus } from './Selos';

export const URL_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
export const ATRIBUICAO_OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

export interface ComandoMapa {
  lat: number;
  lon: number;
  /** Muda a cada pedido, para repetir o mesmo destino. */
  id: number;
  zoom?: number;
}

interface Props {
  centro: Ponto;
  zoom?: number;
  relatos: RelatoProximo[];
  comando: ComandoMapa | null;
  /** Relato que deve abrir o balão (vindo da lista); um objeto novo reabre o mesmo balão. */
  abrir: { id: string } | null;
  onAreaMudou: (centro: Ponto, raioM: number) => void;
}

/** Marcador: cor + texto da prioridade (nunca só cor). O texto completo fica só para leitor de tela. */
function iconeDoRelato(r: RelatoProximo): L.DivIcon {
  const prioridade = infoPrioridade(r.prioridade);
  const nomeAcessivel = `${rotuloCategoria(r.categoria)}. ${prioridade.rotulo}. ${infoStatus(r.status).selo}.`;
  return L.divIcon({
    className: 'marcador-alvo',
    iconSize: [52, 44], // área de toque de 44 px de altura
    iconAnchor: [26, 22],
    popupAnchor: [0, -18],
    html:
      `<span class="marcador marcador-${r.prioridade ?? 'nenhuma'}">` +
      `<span aria-hidden="true">${prioridade.simbolo} ${prioridade.curto}</span>` +
      `<span class="so-leitor">${nomeAcessivel}</span></span>`,
  });
}

function OuvinteArea({ onAreaMudou }: { onAreaMudou: Props['onAreaMudou'] }) {
  const mapa = useMap();
  const avisar = () => {
    const c = mapa.getCenter();
    const raio = Math.ceil(c.distanceTo(mapa.getBounds().getNorthEast()));
    onAreaMudou({ lat: c.lat, lon: c.lng }, Math.min(5000, Math.max(1, raio)));
  };
  useMapEvents({ moveend: avisar });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(avisar, []); // primeira busca ao abrir
  return null;
}

function ObedeceComando({ comando }: { comando: ComandoMapa | null }) {
  const mapa = useMap();
  useEffect(() => {
    if (comando) mapa.setView([comando.lat, comando.lon], comando.zoom ?? Math.max(mapa.getZoom(), 16));
  }, [comando, mapa]);
  return null;
}

export function MapaRelatos({ centro, zoom = 15, relatos, comando, abrir, onAreaMudou }: Props) {
  const marcadores = useRef(new Map<string, L.Marker>());
  const icones = useMemo(() => new Map(relatos.map((r) => [r.id, iconeDoRelato(r)])), [relatos]);

  useEffect(() => {
    if (abrir) marcadores.current.get(abrir.id)?.openPopup();
  }, [abrir]);

  return (
    <div role="region" aria-label="Mapa dos problemas perto de você. A mesma informação está na lista abaixo do mapa.">
    <MapContainer center={[centro.lat, centro.lon]} zoom={zoom} className="mapa" scrollWheelZoom>
      <TileLayer url={URL_TILES} attribution={ATRIBUICAO_OSM} maxZoom={19} />
      <OuvinteArea onAreaMudou={onAreaMudou} />
      <ObedeceComando comando={comando} />
      {relatos.map((r) => (
        <Marker
          key={r.id}
          position={[r.lat, r.lon]}
          icon={icones.get(r.id)}
          title={`${rotuloCategoria(r.categoria)} · ${infoPrioridade(r.prioridade).rotulo}`}
          ref={(m) => {
            if (m) marcadores.current.set(r.id, m);
            else marcadores.current.delete(r.id);
          }}
        >
          <Popup>
            <strong>{rotuloCategoria(r.categoria)}</strong>
            <br />
            <SeloPrioridade prioridade={r.prioridade} />
            <br />
            <SeloStatus status={r.status} />
            <br />
            {r.confirmacoes === 1 ? '1 pessoa confirmou' : `${r.confirmacoes} pessoas confirmaram`}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
    </div>
  );
}
