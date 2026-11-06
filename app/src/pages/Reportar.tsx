import { useEffect, useMemo, useState } from 'react';
import { ApiError, corrigirCategoria, criarRelato } from '../api/cliente';
import type { Categoria, RelatoCriado } from '../api/tipos';
import { Anuncio } from '../components/Anuncio';
import { Pagina } from '../components/Pagina';
import { obterAutorId } from '../lib/autor';
import { PERGUNTA_CATEGORIA } from '../lib/dominio';
import { comprimirImagem, ErroImagem } from '../lib/imagem';
import type { Ponto } from '../lib/localizacao';
import { EtapaClasse } from './reportar/EtapaClasse';
import { EtapaDetalhes } from './reportar/EtapaDetalhes';
import { EtapaFoto, type FotoPronta } from './reportar/EtapaFoto';
import { EtapaLocal } from './reportar/EtapaLocal';
import { EtapaObrigado } from './reportar/EtapaObrigado';

type Etapa = 'foto' | 'local' | 'detalhes' | 'enviando' | 'classe' | 'obrigado';

/** Traduz uma falha de envio em mensagem simples e diz para qual etapa voltar. */
function tratarFalhaDoEnvio(e: unknown): { mensagem: string; voltarPara: Etapa; limparLocal?: boolean } {
  if (e instanceof ApiError) {
    if (e.codigo === 'fora_da_area') {
      return { mensagem: 'Você está fora de São Paulo; toque no mapa dentro da cidade.', voltarPara: 'local', limparLocal: true };
    }
    if (e.status === 413) {
      return { mensagem: 'A foto ficou grande demais. Tire outra foto ou escolha outra.', voltarPara: 'foto' };
    }
    if (e.status === 422) {
      return { mensagem: 'Alguma informação não passou na verificação. Confira a foto e o local.', voltarPara: 'detalhes' };
    }
    if (e.semRede) {
      return { mensagem: 'Sem conexão com a internet. Confira o sinal e tente enviar de novo.', voltarPara: 'detalhes' };
    }
  }
  return { mensagem: 'O servidor está com problemas agora. Tente enviar de novo em instantes.', voltarPara: 'detalhes' };
}

export function Reportar() {
  const autorId = useMemo(() => obterAutorId(), []);
  const [etapa, setEtapa] = useState<Etapa>('foto');
  const [foto, setFoto] = useState<FotoPronta | null>(null);
  const [preparando, setPreparando] = useState(false);
  const [ponto, setPonto] = useState<Ponto | null>(null);
  const [descricao, setDescricao] = useState('');
  const [relato, setRelato] = useState<RelatoCriado | null>(null);
  const [categoriaFinal, setCategoriaFinal] = useState<Categoria | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  // Libera a memória da pré-visualização quando a foto muda ou a tela fecha.
  useEffect(
    () => () => {
      if (foto) URL.revokeObjectURL(foto.url);
    },
    [foto],
  );

  async function aoEscolherFoto(arquivo: File) {
    setPreparando(true);
    setAviso(null);
    try {
      const { blob } = await comprimirImagem(arquivo);
      setFoto({ blob, url: URL.createObjectURL(blob), kb: Math.round(blob.size / 1024) });
    } catch (e) {
      setAviso(e instanceof ErroImagem ? e.message : 'Não consegui preparar essa foto. Tente outra.');
    } finally {
      setPreparando(false);
    }
  }

  async function enviar() {
    if (!foto || !ponto) return;
    setAviso(null);
    setEtapa('enviando');
    try {
      const criado = await criarRelato({ foto: foto.blob, lat: ponto.lat, lon: ponto.lon, descricao, autorId });
      setRelato(criado);
      setEtapa('classe');
    } catch (e) {
      const falha = tratarFalhaDoEnvio(e);
      setAviso(falha.mensagem);
      if (falha.limparLocal) setPonto(null);
      setEtapa(falha.voltarPara);
    }
  }

  async function escolherCategoria(categoria: Categoria) {
    if (!relato) return;
    setAviso(null);
    if (categoria !== relato.categoria) {
      setSalvando(true);
      try {
        await corrigirCategoria(relato.id, categoria, autorId);
      } catch {
        setAviso('Não consegui salvar sua resposta agora. Tente de novo; se preferir, escolha “Não sei dizer”.');
        setSalvando(false);
        return;
      }
      setSalvando(false);
    }
    setCategoriaFinal(categoria);
    setEtapa('obrigado');
  }

  function naoSei() {
    setCategoriaFinal(relato?.categoria ?? null);
    setEtapa('obrigado');
  }

  function recomecar() {
    setFoto(null);
    setPonto(null);
    setDescricao('');
    setRelato(null);
    setCategoriaFinal(null);
    setAviso(null);
    setEtapa('foto');
  }

  const titulos: Record<Etapa, string> = {
    foto: 'Passo 1 de 3: a foto',
    local: 'Passo 2 de 3: o local',
    detalhes: 'Passo 3 de 3: enviar',
    enviando: 'Enviando seu relato…',
    classe: relato?.categoria ? PERGUNTA_CATEGORIA[relato.categoria] : 'Ajude a identificar o problema',
    obrigado: 'Obrigado! Seu relato foi enviado',
  };

  return (
    <Pagina titulo={titulos[etapa]} tituloDocumento="Reportar problema">
      <Anuncio mensagem={aviso} />

      {etapa === 'foto' && (
        <EtapaFoto
          foto={foto}
          preparando={preparando}
          onArquivo={(a) => void aoEscolherFoto(a)}
          onContinuar={() => {
            setAviso(null);
            setEtapa('local');
          }}
        />
      )}

      {etapa === 'local' && (
        <EtapaLocal
          ponto={ponto}
          onPonto={setPonto}
          onVoltar={() => setEtapa('foto')}
          onContinuar={() => {
            setAviso(null);
            setEtapa('detalhes');
          }}
        />
      )}

      {etapa === 'detalhes' && foto && ponto && (
        <EtapaDetalhes
          foto={foto}
          ponto={ponto}
          descricao={descricao}
          onDescricao={setDescricao}
          onVoltar={() => setEtapa('local')}
          onEnviar={() => void enviar()}
        />
      )}

      {etapa === 'enviando' && (
        <p role="status" className="carregando">
          Estamos enviando a foto e identificando o problema. Isso leva alguns segundos.
        </p>
      )}

      {etapa === 'classe' && relato && foto && (
        <EtapaClasse
          foto={foto}
          detectada={relato.categoria}
          salvando={salvando}
          onEscolher={(c) => void escolherCategoria(c)}
          onNaoSei={naoSei}
        />
      )}

      {etapa === 'obrigado' && relato && (
        <EtapaObrigado status={relato.status} categoria={categoriaFinal} onOutro={recomecar} />
      )}
    </Pagina>
  );
}
