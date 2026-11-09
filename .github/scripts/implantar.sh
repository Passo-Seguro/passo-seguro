#!/usr/bin/env bash
# Troca a imagem de um Azure Container App e espera a NOVA revisão ficar saudável.
#
#   implantar.sh <container-app> <resource-group> <imagem-completa> [timeout-em-segundos]
#
# Usado pelo job "deploy" do ci.yml (já logado na Azure por OIDC). Para reproduzir à mão,
# faça `az login` e rode com os mesmos argumentos. Não imprime nenhum segredo.
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "uso: $0 <container-app> <resource-group> <imagem> [timeout-s]" >&2
  exit 2
fi

app="$1"
rg="$2"
imagem="$3"
limite="${4:-300}"

echo "Atualizando ${app} para ${imagem}"
az containerapp update --name "$app" --resource-group "$rg" --image "$imagem" --output none

# Revisão mais recente (pela data de criação) com o que interessa conferir.
consulta='sort_by([], &properties.createdTime)[-1].{
  nome: name,
  imagem: properties.template.containers[0].image,
  saude: properties.healthState,
  execucao: properties.runningState,
  provisionamento: properties.provisioningState,
  trafego: properties.trafficWeight
}'

fim=$((SECONDS + limite))
ultimo=""
while [ "$SECONDS" -lt "$fim" ]; do
  rev="$(az containerapp revision list --name "$app" --resource-group "$rg" --query "$consulta" --output json)"
  nome="$(jq -r '.nome' <<<"$rev")"
  img="$(jq -r '.imagem' <<<"$rev")"
  saude="$(jq -r '.saude' <<<"$rev")"
  execucao="$(jq -r '.execucao' <<<"$rev")"
  prov="$(jq -r '.provisionamento' <<<"$rev")"

  estado="${nome} saude=${saude} execucao=${execucao} provisionamento=${prov}"
  if [ "$estado" != "$ultimo" ]; then
    echo "  revisão ${estado}"
    ultimo="$estado"
  fi

  # Falha cedo: a revisão nova já morreu, não adianta esperar o tempo todo.
  if [ "$img" = "$imagem" ] && { [ "$execucao" = "Failed" ] || [ "$prov" = "Failed" ]; }; then
    echo "::error::A revisão ${nome} de ${app} falhou (execucao=${execucao}, provisionamento=${prov})."
    exit 1
  fi

  # Só vale a revisão que usa a imagem DESTE commit; uma revisão antiga saudável não conta.
  if [ "$img" = "$imagem" ] && [ "$saude" = "Healthy" ] && [[ "$execucao" == Running* ]]; then
    echo "Revisão ${nome} de ${app} saudável com a imagem do commit."
    exit 0
  fi

  sleep 10
done

echo "::error::A revisão mais recente de ${app} não ficou saudável com a imagem ${imagem} em ${limite}s."
echo "Último estado: ${ultimo}"
echo "Imagem da revisão mais recente: ${img:-desconhecida}"
exit 1
