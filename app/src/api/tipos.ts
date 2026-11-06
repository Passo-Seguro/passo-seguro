// Tipos do contrato, derivados de schema.d.ts (gerado a partir do openapi.yaml).
// Não declare campos à mão aqui: se o contrato mudar, `npm run gen:api` + o compilador acusam.
import type { components } from './schema';

type S = components['schemas'];

export type Categoria = S['Categoria'];
export type StatusRelato = S['StatusRelato'];
export type Prioridade = S['Prioridade'];
export type RelatoCriado = S['RelatoCriado'];
export type RelatoProximo = S['RelatoProximo'];
export type RelatoResumo = S['RelatoResumo'];
export type Relato = S['Relato'];
export type RespostaAssistente = S['RespostaAssistente'];
export type FonteCitada = S['FonteCitada'];
export type PrioridadeSubprefeitura = S['PrioridadeSubprefeitura'];
export type Erro = S['Erro'];
