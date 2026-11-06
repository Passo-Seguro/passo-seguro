import { useCallback, useEffect, useRef, useState } from 'react';
import { SeletorLocal } from '../../components/SeletorLocal';
import { CENTRO_PADRAO, ErroLocalizacao, obterLocalizacao, type Ponto } from '../../lib/localizacao';

interface Props {
  ponto: Ponto | null;
  onPonto: (ponto: Ponto) => void;
  onVoltar: () => void;
  onContinuar: () => void;
}

type Gps = 'procurando' | 'achou' | 'falhou' | 'parado';

const MENSAGEM_FALHA: Record<string, string> = {
  negado: 'Não tenho permissão para usar sua localização. Toque no mapa no lugar do problema.',
  sem_suporte: 'Este aparelho não informa a localização. Toque no mapa no lugar do problema.',
  tempo_esgotado: 'Demorei para achar sua localização. Tente de novo ou toque no mapa no lugar do problema.',
  indisponivel: 'Não consegui achar sua localização. Tente de novo ou toque no mapa no lugar do problema.',
};

export function EtapaLocal({ ponto, onPonto, onVoltar, onContinuar }: Props) {
  const [gps, setGps] = useState<Gps>(ponto ? 'parado' : 'procurando');
  const [falha, setFalha] = useState<string | null>(null);
  const lerCentro = useRef<(() => Ponto) | null>(null);
  const registrar = useCallback((ler: () => Ponto) => {
    lerCentro.current = ler;
  }, []);

  const procurar = useCallback(async () => {
    setGps('procurando');
    setFalha(null);
    try {
      onPonto(await obterLocalizacao());
      setGps('achou');
    } catch (e) {
      setGps('falhou');
      setFalha(MENSAGEM_FALHA[e instanceof ErroLocalizacao ? e.motivo : 'indisponivel']);
    }
  }, [onPonto]);

  // Na primeira vez que a pessoa chega aqui, tenta o GPS sozinho.
  const jaTentou = useRef(false);
  useEffect(() => {
    if (jaTentou.current || ponto) return;
    jaTentou.current = true;
    void procurar();
  }, [ponto, procurar]);

  let status = '';
  if (gps === 'procurando') status = 'Procurando sua localização…';
  else if (gps === 'achou') status = 'Achei sua localização. Se não for o lugar do problema, toque no mapa no ponto certo.';
  else if (gps === 'falhou' && falha) status = falha;
  else if (ponto) status = 'Local marcado. Para mudar, toque em outro ponto do mapa.';

  return (
    <>
      <p>Onde está o problema? Usamos o GPS ou você toca no mapa.</p>
      <SeletorLocal centro={ponto ?? CENTRO_PADRAO} ponto={ponto} onEscolher={onPonto} registrarLeitorDeCentro={registrar} />
      <p role="status" className="status-linha">
        {status}
      </p>

      <div className="acoes">
        <button type="button" className="botao botao-secundario" onClick={() => void procurar()} disabled={gps === 'procurando'}>
          Usar minha localização
        </button>
        <button
          type="button"
          className="botao botao-secundario"
          onClick={() => lerCentro.current && onPonto(lerCentro.current())}
        >
          Marcar o centro do mapa
        </button>
      </div>
      <div className="acoes acoes-navegacao">
        <button type="button" className="botao botao-secundario" onClick={onVoltar}>
          Voltar
        </button>
        <button type="button" className="botao botao-primario" onClick={onContinuar} disabled={!ponto}>
          Continuar
        </button>
      </div>
      {!ponto && <p className="dica">Marque o local do problema para continuar.</p>}
    </>
  );
}
