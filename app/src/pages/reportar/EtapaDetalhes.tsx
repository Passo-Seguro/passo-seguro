import type { Ponto } from '../../lib/localizacao';
import type { FotoPronta } from './EtapaFoto';

interface Props {
  foto: FotoPronta;
  ponto: Ponto;
  descricao: string;
  onDescricao: (texto: string) => void;
  onVoltar: () => void;
  onEnviar: () => void;
}

export const LIMITE_DESCRICAO = 1000;

export function EtapaDetalhes({ foto, ponto, descricao, onDescricao, onVoltar, onEnviar }: Props) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onEnviar();
      }}
    >
      <div className="resumo">
        <img src={foto.url} alt="Foto do problema" className="miniatura" />
        <p>
          Local marcado perto de {ponto.lat.toFixed(4)}, {ponto.lon.toFixed(4)}.
        </p>
      </div>

      <label htmlFor="descricao" className="rotulo">
        Quer contar mais? (opcional)
      </label>
      <p id="descricao-dica" className="dica">
        Não escreva telefone, CPF nem nome de pessoas.
      </p>
      <textarea
        id="descricao"
        name="descricao"
        rows={4}
        maxLength={LIMITE_DESCRICAO}
        value={descricao}
        onChange={(e) => onDescricao(e.target.value)}
        aria-describedby="descricao-dica"
      />

      <div className="acoes acoes-navegacao">
        <button type="button" className="botao botao-secundario" onClick={onVoltar}>
          Voltar
        </button>
        <button type="submit" className="botao botao-primario">
          Enviar relato
        </button>
      </div>
    </form>
  );
}
