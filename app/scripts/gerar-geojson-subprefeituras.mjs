// Gera app/src/geo/subprefeituras.json, a camada de subprefeituras do mapa.
//
// Entrada: subprefeitura.geojson do GeoSampa (SMUL, Prefeitura de São Paulo), o mesmo que o pipeline
// de dados usa para atribuir cada ponto a uma subprefeitura. Fica no Volume do Databricks:
//   databricks fs cp dbfs:/Volumes/workspace/gs/chegada/geo/subprefeitura.geojson subprefeitura.geojson
//
// Uso (a partir de app/):
//   npm run gen:geo -- caminho/para/subprefeitura.geojson
//
// O que faz: deixa em cada polígono só `subprefeitura` (nome em maiúsculas e sem acento, a MESMA chave
// do `GET /painel`), arredonda as coordenadas a 4 casas (cerca de 11 m, de sobra para um mapa de
// bairros) e tira pontos repetidos. Sem dependências.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const CASAS = 4;
const ESPERADAS = 32;

const [entrada, saidaArg] = process.argv.slice(2);
if (!entrada) {
  console.error('Uso: node scripts/gerar-geojson-subprefeituras.mjs <subprefeitura.geojson> [saida.json]');
  process.exit(2);
}
const saida = resolve(saidaArg ?? resolve(dirname(fileURLToPath(import.meta.url)), '../src/geo/subprefeituras.json'));

/** Maiúsculas, sem acento, espaços simples: igual ao `normalizar` do notebook 03_ouro. */
const normalizar = (s) =>
  s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/\s+/g, ' ').trim();

const arredondar = (n) => Number(n.toFixed(CASAS));

/** Anel fechado, arredondado e sem pontos repetidos em sequência. Devolve null se degenerar. */
function simplificarAnel(anel) {
  const pontos = [];
  for (const [lon, lat] of anel) {
    const p = [arredondar(lon), arredondar(lat)];
    const ultimo = pontos.at(-1);
    if (!ultimo || ultimo[0] !== p[0] || ultimo[1] !== p[1]) pontos.push(p);
  }
  const primeiro = pontos[0];
  const ultimo = pontos.at(-1);
  if (primeiro && (primeiro[0] !== ultimo[0] || primeiro[1] !== ultimo[1])) pontos.push([...primeiro]);
  return pontos.length >= 4 ? pontos : null;
}

function simplificarPoligono(aneis) {
  const feitos = aneis.map(simplificarAnel);
  // O anel externo é obrigatório; um buraco que degenerou simplesmente some.
  return feitos[0] ? feitos.filter(Boolean) : null;
}

function simplificarGeometria(g) {
  if (g.type === 'Polygon') {
    const c = simplificarPoligono(g.coordinates);
    return c && { type: 'Polygon', coordinates: c };
  }
  if (g.type === 'MultiPolygon') {
    const partes = g.coordinates.map(simplificarPoligono).filter(Boolean);
    return partes.length ? { type: 'MultiPolygon', coordinates: partes } : null;
  }
  throw new Error(`Geometria não suportada: ${g.type}`);
}

const origem = JSON.parse(readFileSync(entrada, 'utf-8'));
if (origem.type !== 'FeatureCollection' || origem.features.length !== ESPERADAS) {
  throw new Error(`Esperava uma FeatureCollection com ${ESPERADAS} subprefeituras, veio ${origem.features?.length}.`);
}

const nomes = new Set();
const features = origem.features.map((f) => {
  const bruto = f.properties?.nm_subprefeitura;
  if (typeof bruto !== 'string' || !bruto.trim()) throw new Error('Subprefeitura sem nm_subprefeitura.');
  const nome = normalizar(bruto);
  if (nomes.has(nome)) throw new Error(`Subprefeitura repetida: ${nome}`);
  nomes.add(nome);
  const geometry = simplificarGeometria(f.geometry);
  if (!geometry) throw new Error(`Geometria vazia depois de simplificar: ${nome}`);
  return { type: 'Feature', properties: { subprefeitura: nome }, geometry };
});
features.sort((a, b) => a.properties.subprefeitura.localeCompare(b.properties.subprefeitura, 'pt-BR'));

const texto = JSON.stringify({ type: 'FeatureCollection', features });
writeFileSync(saida, texto + '\n', 'utf-8');
console.log(`${features.length} subprefeituras, ${(texto.length / 1024).toFixed(0)} KB, gravado em ${saida}`);
