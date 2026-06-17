# Componentes React

## App

**Arquivo:** `ui/src/App.tsx`
**Descrição:** Componente principal. Gerencia estado global (tópico, relatório, status, histórico).

### Estado

| Variável | Tipo | Inicial | Descrição |
|---|---|---|---|
| `topic` | `string` | `""` | Tópico da pesquisa |
| `report` | `string` | `""` | Relatório Markdown gerado |
| `isRunning` | `boolean` | `false` | Indicador de processamento |
| `status` | `{ text, type }` | `{ text: "Pronto.", type: "neutral" }` | Status exibido no badge |
| `sidebarActive` | `string` | `"nova-pesquisa"` | Item ativo da barra lateral |
| `historyItems` | `HistoryItem[]` | `[]` | Lista do histórico |

### Funções principais

| Função | Descrição |
|---|---|
| `runResearch()` | POST `/api/research` com o tópico, atualiza relatório e status |
| `loadHistory()` | GET `/api/history` para popular a barra lateral |
| `loadResearchFromHistory(id)` | GET `/api/history/{id}` para carregar pesquisa salva |
| `deleteHistoryItem(id)` | DELETE `/api/history/{id}` |
| `copyMarkdown()` | Copia o relatório para a área de transferência |

### Dependências

| Dependência | Tipo | Motivo |
|---|---|---|
| `@mantine/core` | UI | AppShell, Card, Button, Textarea, Badge |
| `react-markdown` | Renderização | Exibe o relatório como Markdown |
| `remark-gfm` | Plugin | Suporte a tabelas GFM |
| `rehype-external-links` | Plugin | Links externos abrem em nova aba |

## AppNavbar

**Arquivo:** `ui/src/components/AppNavbar.tsx`
**Descrição:** Barra lateral com navegação e lista de sessões do histórico.

### Props

| Prop | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `active` | `string` | Sim | ID do item ativo |
| `onNavigate` | `(id: string) => void` | Sim | Callback de navegação |
| `historyItems` | `HistoryItem[]` | Sim | Itens do histórico |
| `onSelectHistory` | `(id: number) => void` | Sim | Seleciona pesquisa do histórico |
| `onDeleteHistory` | `(id: number) => void` | Sim | Remove item do histórico |

## MarkdownRenderer

**Arquivo:** `ui/src/components/MarkdownRenderer.tsx`
**Descrição:** Renderiza conteúdo Markdown com suporte a GFM (tabelas, listas) e links externos.

### Props

| Prop | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `content` | `string` | Sim | Texto Markdown a ser renderizado |

## EmptyState

**Arquivo:** `ui/src/components/EmptyState.tsx`
**Descrição:** Exibido quando nenhum relatório foi gerado ainda.

### Props

Nenhuma.

## SvgIcon

**Arquivo:** `ui/src/components/SvgIcon.tsx`
**Descrição:** Renderiza um ícone SVG inline a partir de um path.

### Props

| Prop | Tipo | Obrigatório | Padrão | Descrição |
|---|---|---|---|---|
| `path` | `string` | Sim | — | Caminho SVG (`d` attribute) |
| `size` | `number` | Não | `24` | Tamanho em pixels |
| `viewBox` | `string` | Não | `"0 0 24 24"` | ViewBox do SVG |

## Tipos compartilhados

**Arquivo:** `ui/src/types.ts`

```typescript
interface HistoryItem {
  id: number;
  topic: string;
  created_at: string;
}
```
