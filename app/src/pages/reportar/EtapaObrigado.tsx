import { Link } from 'react-router';
import type { Categoria, StatusRelato } from '../../api/tipos';
import { SeloStatus } from '../../components/Selos';
import { infoStatus, ROTULO_CATEGORIA } from '../../lib/dominio';

interface Props {
  status: StatusRelato;
  categoria: Categoria | null;
  onOutro: () => void;
}

export function EtapaObrigado({ status, categoria, onOutro }: Props) {
  return (
    <>
      <p className="selos">
        Situação do seu relato: <SeloStatus status={status} />
      </p>
      <p>{infoStatus(status).explicacao}</p>
      <p>
        Problema:{' '}
        <strong>{categoria ? ROTULO_CATEGORIA[categoria] : 'ainda sem classificação (uma pessoa vai olhar a foto)'}</strong>
      </p>
      <p>Você pode acompanhar o andamento a qualquer momento em “Meus relatos”.</p>

      <div className="acoes">
        <Link to="/meus-relatos" className="botao botao-primario">
          Acompanhar meus relatos
        </Link>
        <button type="button" className="botao botao-secundario" onClick={onOutro}>
          Reportar outro problema
        </button>
        <Link to="/" className="botao botao-secundario">
          Voltar ao mapa
        </Link>
      </div>
    </>
  );
}
