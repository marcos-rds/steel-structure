# Changelog

## Não lançado

- Migração integral da identidade atual de Metal Structure para Steel Structures, incluindo pacote Python, workbench, comandos e recursos, sem alterar a versão.

## 0.4.0 — 31/07/2026

- Nova ferramenta `StructuralMemberDraftTool`, baseada diretamente na Linha nativa do Draft, para criação gráfica ou numérica por dois pontos.
- Entrada numérica, snaps, restrições, Relativo e Global reutilizam integralmente a infraestrutura nativa do Draft.
- Opções de nome, tipo, perfil, inserção, rotação e cor integradas ao painel nativo.
- Modo Continuar cria membros sucessivos na mesma sessão, preservando a interface, a prévia, o callback e as opções do perfil.
- Fechamento por Esc ou Close e reabertura da ferramenta estabilizados, sem referências residuais de sessão.
- Corrigido o erro `QLineEdit already deleted`, eliminando manipulação do TaskBox externo, `headerText` e travessia da árvore Qt.
- Cabeçalho externo fixo “Criar elemento estrutural”, com orientação do primeiro e do próximo ponto pela barra inferior do FreeCAD.
- Comprimento e Ângulo nativos aparecem somente depois da confirmação do primeiro ponto.
- Barra oficial Draft Snap registrada na bancada e disponível no menu de barras de ferramentas.
- Removidos o painel numérico legado, a captura Coin3D própria e os adaptadores próprios de snap e pré-visualização.
- Propriedade editável `Length`, sincronizada com `StartPoint`, `EndPoint` e `MemberLength`, preservando o ponto inicial e a direção do membro.
- O cancelamento parcial do segmento com um primeiro Esc permanece adiado; Esc conserva o encerramento nativo completo da Linha.

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
