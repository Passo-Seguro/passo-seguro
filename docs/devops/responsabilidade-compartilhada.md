# Responsabilidade compartilhada

Quem cuida de quê na nossa nuvem. Usamos serviços gerenciados (PaaS): Container Apps e PostgreSQL Flexible Server. A divisão abaixo vale para esses serviços. A arquitetura está em [`arquitetura.md`](./arquitetura.md).

Marcação: **●** é responsabilidade principal daquele lado. **◐** é dividida.

## Matriz

| Camada | Microsoft | Equipe | Nossa prática concreta |
|---|---|---|---|
| Datacenter e hardware | ● | | Nenhuma ação. Escolhemos só a região (`centralus`) e o armazenamento local redundante (LRS, sem zona). `zone_redundancy_enabled = false` no ambiente. |
| Rede física | ● | | Nenhuma ação. |
| Hipervisor | ● | | Nenhuma ação. |
| Sistema operacional e patches | ● | ◐ | O sistema do host dos Container Apps e do servidor PostgreSQL é da Microsoft. O que é nosso é o sistema **dentro da imagem** (Alpine no app, Debian slim na API): a linha da imagem abaixo cobre isso. |
| Runtime de containers | ● | ◐ | A plataforma de containers é da Microsoft. Nós definimos o que roda nela: CPU e memória por app (0,5 vCPU e 1 GiB na API; 0,25 vCPU e 0,5 GiB no app), sondas de saúde (`/saude` e `/healthz`), no máximo 2 réplicas e usuário sem privilégios na imagem (uid 10001 na API, 101 no app). |
| Imagem e dependências | | ● | **Trivy** varre cada imagem no `build` e reprova com vulnerabilidade HIGH/CRITICAL que já tenha correção; só publica no GHCR o que passou. O Trivy também varre o Terraform e os Dockerfiles. SBOM em SPDX por imagem, nos artifacts do pipeline. Versões fixas (`pip-compile`, tags de imagem, actions fixadas por SHA). **Dependabot** abre PRs semanais de actions, pip, npm e Docker, com espera de 7 dias para versões novas. O app roda `apk upgrade` na imagem para trazer correções do sistema. |
| Código da aplicação | | ● | **Semgrep** (SAST) e **Gitleaks** (segredos no histórico inteiro) em todo push; `ruff`, `pytest` (com o teste de contrato Schemathesis contra o `openapi.yaml`) e os testes do app. A API valida o upload pelo conteúdo (só JPEG e PNG, limite de 10 MB e de pixels) e remove o EXIF da foto. O GitHub tem secret scanning e push protection ligados. |
| Identidade e acesso | ◐ | ● | A Microsoft opera o Entra ID e o RBAC. Nós definimos quem pode o quê: o pipeline entra por **OIDC**, sem senha, com `id-passoseguro-github`, que é *Contributor* só no escopo de cada Container App e *Reader* no resource group. Os apps usam a identidade gerenciada `id-passoseguro-apps` (*Key Vault Secrets User* e leitura só do container `painel`). O environment `production` do GitHub aceita só a branch `main`. **Ele não exige aprovação de revisor** (zero revisores configurados). |
| Dados e criptografia | ◐ | ● | A Microsoft criptografa em repouso por padrão os serviços que usamos (Storage e PostgreSQL), com chaves dela. Nós cuidamos do restante: TLS mínimo 1.2 e só HTTPS na conta de armazenamento, `sslmode=require` na conexão com o banco, HTTP redirecionado para HTTPS no app, segredos gerados pelo Terraform e guardados no **Key Vault** (7 segredos, validade até 30/06/2027), hash do `autor_id` e coordenadas públicas arredondadas. Detalhes em [`lgpd.md`](./lgpd.md). |
| Configuração de rede e NSG | ◐ | ● | A Microsoft opera a rede virtual. A configuração é nossa, em [`rede.tf`](../../infra/rede.tf): VNet com duas sub-redes, **rede privada** para o banco (sem endereço público, DNS privado), ingress interno na API e **NSG** em cada sub-rede. O NSG do app só aceita 80 e 443 da internet e não existe regra para 22 ou 3389. O NSG do banco só aceita a 5432 vinda da `snet-aca` e nega o resto. Exceções conhecidas: o firewall da conta de armazenamento e o acesso público do Key Vault estão abertos (veja [riscos aceitos](../../infra/README.md#riscos-aceitos)). |
| Backup do banco | ◐ | ● | A Microsoft executa os backups automáticos do PostgreSQL Flexible Server. Nós escolhemos a retenção: **7 dias**, sem redundância geográfica. Não há teste de restauração documentado neste repositório. |
| Backup das fotos | | ● | **Lacuna.** O Terraform não configura backup nem snapshot do share `fotos` (Azure Files, LRS). Uma foto apagada ou corrompida não tem cópia nossa. |

## Comparação com a opção de VM (IaaS)

Na VM que avaliamos (veja [por que não uma VM](./arquitetura.md#por-que-não-uma-vm)), o sistema operacional, os patches, o runtime de containers, o firewall do host e o backup do banco passariam a ser nossos, e cada um exigiria rotina e evidência. No PaaS, o sistema operacional e o runtime saem do nosso lado: a nossa responsabilidade começa na imagem e vai até o código, a identidade, os dados e a configuração de rede. Essas últimas camadas continuam nossas nas duas opções, e é nelas que o pipeline, o Trivy e o NSG atuam.
