# Changelog

## Em desenvolvimento

- Base do controlador de criação preparada para evolução interativa.
- Painel lateral de tarefas para criação numérica contínua de elementos.
- Preservação temporária do diálogo numérico como fallback interno.
- Correção da detecção de diálogo ativo quando a aba Tarefas está vazia.
- Correção do reinício do nome automático e do fechamento seguro do painel.
- Testes automatizados para estados, transações e ciclo de vida da sessão.
- Captura básica de dois pontos na vista 3D, com criação contínua.
- Prévia axial leve por linha Coin3D, sem objetos temporários no documento.
- Cancelamento progressivo com Esc e limpeza simétrica de callbacks e prévia.
- Entrada numérica preservada como opção para coordenadas espaciais exatas.
- Encerramento diferido da captura para evitar remoção de callbacks durante eventos Coin.
- Início automático da captura ao abrir o painel, sem botões Capturar ou Parar.
- Criação contínua, mantendo a ferramenta ativa para elementos sucessivos.
- Esc cancela o segmento após o primeiro ponto e fecha a ferramenta ao aguardar o primeiro ponto.
- Limpeza diferida contra Access violation preservada no encerramento da ferramenta.
- Captura ainda baseada em projeção da vista, sem snap geométrico.
- Snap geométrico básico em vértices e extremidades de arestas.
- Marcador Coin3D leve no ponto exato, com projeção da vista como fallback.
- Metadados de snap mantidos somente durante a sessão de criação.

## 0.3.0 — 30/07/2026

- Interface simplificada para um único comando de criação.
- Comando público "Criar elemento estrutural".
- Manutenção do campo Tipo do elemento.
- Designações compactas, como W150x13,0, na interface.
- Preservação da designação canônica do catálogo nos objetos.
- Testes automatizados adicionados.
- Manutenção da geometria e do comportamento paramétrico existente.

## 0.2.0 — 2026-07-30

- Renomeação visual para Metal Structure.
- Hierarquia de catálogo: categoria, série e perfil.
- Campo de nome e sequência automática com três dígitos.
- Orientação espacial controlada pelo Placement do objeto.
- Composição da rotação axial com a orientação do membro.
- Proteção contra eventos onChanged durante a criação das propriedades.
- Migração básica de objetos v0.1.0.
