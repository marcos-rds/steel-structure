# Changelog

## Em desenvolvimento

- A criação interativa agora reutiliza diretamente a ferramenta Linha do Draft: painel nativo de coordenadas, Relativo, Global, Continuar, snap, restrições e pré-visualização.
- As opções estruturais de nome, tipo, perfil, inserção, rotação e cor aparecem em uma caixa separada abaixo da interface nativa.
- A linha temporária do Draft é descartada e somente o membro paramétrico definitivo é criado; a indisponibilidade da interface Draft é informada sem abrir uma interface alternativa.
- A barra oficial Draft Snap é registrada diretamente na Metal Structure com os comandos nativos do Draft e fica disponível no menu de barras de ferramentas.
- O cabeçalho nativo do TaskBox passa de “Primeiro ponto do elemento estrutural” para “Próximo ponto”, com o ícone da Metal Structure preservado e sem herdar o ícone da Linha; Comprimento e Ângulo aparecem somente no segundo estágio.
- A ferramenta nativa pode ser fechada e reaberta com uma nova instância Draft, limpando referências encerradas.
- O modo Continuar reutiliza a mesma sessão, interface, prévia e callback nativos do Draft, reiniciando somente o segmento de dois pontos entre membros.
- Membros estruturais recebem a propriedade editável Length, sincronizada com EndPoint e com MemberLength, preservando StartPoint e a direção atual.
- O cancelamento parcial do segmento com um primeiro Esc foi adiado; nesta etapa, Esc conserva o encerramento nativo completo da ferramenta Linha.
- O identificador nativo `Line` é usado para o estado Continuar, eliminando avisos de chave desconhecida nas preferências do Draft.
- O sistema legado de painel numérico, captura Coin3D, prévia e snap próprios foi removido do fluxo de criação; a entrada gráfica e numérica passa exclusivamente pela infraestrutura nativa do Draft.

### Histórico dos marcos intermediários da 0.4.0

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
- Snapper nativo do Draft passa a ser o mecanismo principal da captura.
- Modos, tolerância, marcadores e preferências de snap do Draft são respeitados.
- Barra nativa Encaixe de Draft disponibilizada sem duplicar comandos.
- Snap básico próprio permanece disponível somente como fallback.

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
