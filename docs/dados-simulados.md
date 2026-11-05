# Dados simulados

O mapa e o painel do Passo Seguro mostram relatos de outras pessoas. No dia da demonstração
ainda não haverá relatos de verdade, e um mapa vazio não mostra para que o produto serve.
Por isso o projeto gera **relatos fictícios**, claramente marcados, que podem ser apagados com
um comando.

## O que é gerado

O script [`scripts/gerar_dados_simulados.py`](../scripts/gerar_dados_simulados.py) insere linhas
na tabela `relatos`, todas com a coluna interna **`simulado = true`**. Cada relato simulado tem:

| Campo | Como é sorteado |
|---|---|
| Localização | Dentro de uma ou mais áreas (caixas lat/lon). Padrão: **Sé** e **Pinheiros**. 70% dos pontos se agrupam em torno de quatro "pontos quentes" por área, para o mapa parecer com a cidade real, e 30% se espalham por igual. |
| `categoria` | Uma das quatro classes, conforme `--distribuicao-classes`. Cerca de 5% ficam sem categoria (e sem `confianca`), como no caso "a visão não detectou nada". |
| `confianca` | De 0,35 a 0,99, só quando há categoria. |
| `status` | Distribuição fixa: 40% `novo`, 8% `revisao_humana`, 10% `validado`, 25% `encaminhado`, 12% `resolvido`, 5% `rejeitado`. |
| `subprefeitura` e `prioridade` | Só nos relatos `encaminhado` e `resolvido` (como no contrato). A prioridade sai da classe e das confirmações. |
| `confirmacoes` | Maior nos relatos encaminhados. |
| `fonte` | 85% `app`, 15% `robo`. |
| `criado_em` | Entre 0 e 45 dias antes da data de referência (os `resolvido` são mais antigos: de 15 a 60 dias). |
| `descricao` | Frases curtas por classe; 30% ficam vazias. Cerca de 7% trazem um telefone ou CPF **claramente falso** (`(11) 90000-0000`, `000.000.000-00`), para a triagem (RPA) poder demonstrar o mascaramento de dados pessoais. |
| Foto | Todos apontam para uma única imagem cinza escrito "Foto simulada" (`simulados/placeholder.png`). Não há fotos reais nem de terceiros. |
| Autor | Nenhum (`autor_hash` nulo). |

Os relatos simulados **aparecem pela API como qualquer outro** (`GET /relatos`, mapa), porque o
objetivo é justamente a demonstração. A coluna `simulado` é interna e nunca vai nas respostas.

## Por que é legítimo

O briefing da disciplina aceita dados simulados desde que a geração seja justificada. Aqui:

- **Finalidade:** demonstração. O avaliador precisa ver o mapa e o painel funcionando antes de
  existir uma base de relatos reais.
- **Transparência:** os dados são marcados (`simulado`), o método está neste documento e o
  código é público. Nenhum relato simulado se passa por pessoa real.
- **Sem dado pessoal real:** coordenadas sorteadas, textos inventados, telefones e CPFs zerados.
- **Reversível:** um comando remove tudo (abaixo), sem tocar nos relatos reais.
- **Reprodutível:** a mesma `--seed` e a mesma `--referencia` geram exatamente os mesmos dados.

> As áreas padrão são **caixas aproximadas** em torno de Sé e Pinheiros, não os limites oficiais
> das subprefeituras. Os números (volume de relatos, tempos, prioridades) **não representam a
> realidade** da cidade e não devem ser citados como dado.

## Como gerar

Com o banco no ar (`docker compose -f docker-compose.dev.yml up -d db`), as migrações aplicadas
(`cd api && alembic upgrade head`) e o ambiente da API instalado (ver o README), a partir da raiz
do repositório:

```bash
python scripts/gerar_dados_simulados.py                 # 300 relatos em Sé e Pinheiros
python scripts/gerar_dados_simulados.py --quantidade 50 --seed 7
python scripts/gerar_dados_simulados.py --area se       # só a Sé
python scripts/gerar_dados_simulados.py --area "Mooca:-23.57,-46.615,-23.54,-46.58"
python scripts/gerar_dados_simulados.py --distribuicao-classes buraco=50,piso_danificado=50
```

| Parâmetro | Significado | Padrão |
|---|---|---|
| `--quantidade N` | Quantos relatos gerar | 300 |
| `--area AREA` | `se`, `pinheiros` ou `[nome:]lat_min,lon_min,lat_max,lon_max`. Pode repetir. | `se` e `pinheiros` |
| `--distribuicao-classes` | Pesos relativos, no formato `classe=peso,...`. Não precisam somar 100. | `buraco=25,piso_danificado=40,obstaculo=20,veiculo_na_calcada=15` |
| `--seed N` | Semente do sorteio | 42 |
| `--referencia AAAA-MM-DD` | Data usada como "hoje" nos `criado_em` | hoje |
| `--apagar` | Em vez de gerar, apaga os simulados | |

Rodar de novo com os mesmos parâmetros **não duplica** nada: os relatos já existentes são
ignorados. Para ter mais dados, mude a `--seed`.

A conexão vem de `DATABASE_URL` (variável de ambiente ou `api/.env`).

## Como apagar

```bash
python scripts/gerar_dados_simulados.py --apagar
```

Remove **apenas** as linhas com `simulado = true`. O mesmo efeito, direto no banco:

```sql
DELETE FROM relatos WHERE simulado = true;
```

A foto `simulados/placeholder.png` é um único arquivo e pode ficar.

Antes de mostrar o produto a usuários reais, decida em conjunto se os simulados ficam (rotulados
na interface) ou saem. Recomendação: **apagar** assim que houver relatos reais suficientes.
