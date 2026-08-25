# AGENTS.md — Steel Structures

## Contexto do projeto

Steel Structures é uma workbench independente para FreeCAD, dedicada a estruturas metálicas. É desenvolvida principalmente em Python, integrada às APIs FreeCAD, Part, Draft e Qt/PySide. O objetivo é oferecer criação paramétrica, boa integração com o modelo de documentos do FreeCAD e fluxo adequado a CAD estrutural, evoluindo incrementalmente sem quebrar recursos existentes. Não presuma funcionalidades além das implementadas no repositório.

Alvos atuais: FreeCAD 1.1.3, Python 3.11, Windows e interface em português do Brasil. Quetzal, Dodo e FrameForge não são dependências nem bases de código; podem servir apenas como referência conceitual de fluxo e funcionalidades.

## Estrutura e convenções

- `freecad/SteelStructures/`: pacote da workbench. Mantenha separados comandos (`commands.py`), objetos paramétricos (`member.py`, `grid.py`), preferências, catálogos e integração GUI (`init_gui.py`).
- `freecad/SteelStructures/interactive/`: ferramentas Draft, painéis de tarefas, controladores e widgets Qt.
- `freecad/SteelStructures/profiles/`: modelos, catálogo, validação, geometria 2D pura e adaptador FreeCAD.
- `grid_geometry.py` e `profiles/geometry.py`: núcleos geométricos puros; preserve a separação dos adaptadores FreeCAD/Part (`grid.py`, `profiles/freecad_geometry.py`) quando aplicável.
- `Resources/Icons/`, `Documentation/`, `tests/` e `scripts/`: recursos, documentação, testes `unittest` e verificações do projeto.
- Use `SteelStructures_*` para IDs públicos de comandos e nomes claros em inglês para símbolos internos, mantendo textos de interface em português do Brasil.
- Membros são construídos localmente no eixo Z e orientados por `Placement`; a rotação da seção ocorre no eixo longitudinal local. Preserve membros em X, Y, Z e direções inclinadas, inserções, offsets, extensões, massa e dados de catálogo. Não assuma seção I para toda família; novas famílias exigem gerador geométrico próprio.
- Não altere catálogos sem registrar a origem dos dados.
- Não incremente a versão, altere metadados de release ou atualize `Documentation/CHANGELOG.md` automaticamente durante o desenvolvimento comum. Versionamento, changelog de release, tag e release só devem ser tratados quando fizerem parte explícita da tarefa ou etapa correspondente. Quando houver uma alteração deliberada da versão do projeto, mantenha `package.xml`, `freecad/SteelStructures/__init__.py` e a documentação sincronizados.

## Princípios de desenvolvimento

- Compreenda primeiro a implementação e os testes existentes; altere depois.
- Prefira mudanças pequenas, focadas e compatíveis com a arquitetura atual. Não reescreva módulos funcionais sem necessidade, não duplique lógica e não mude comportamento visual ou funcional fora do escopo.
- Não introduza dependências externas sem necessidade e autorização.
- Preserve compatibilidade e documentos existentes. Não alegue teste manual no FreeCAD se ele não ocorreu; informe claramente limitações e validações manuais pendentes.

## Engenharia específica do FreeCAD

Quando aplicável, preserve o comportamento paramétrico, propriedades persistentes, compatibilidade de objetos `Part::FeaturePython`, contratos de `execute`, `onChanged`, `onDocumentRestored` e recompute, transações e Undo/Redo, estabilidade de `Shape`, nomes e propriedades já consumidos e abertura de documentos existentes. Evite recursão/reentrância em callbacks e deixe cancelamentos sem objetos temporários ou transações órfãs.

Trate qualquer mudança de propriedades persistentes, `SchemaVersion`, serialização ou migração como alto risco: planeje compatibilidade, restauração de documentos e testes de recompute/persistência. Preserve a geometria local e aplique orientação pelo `Placement`, sem incorporar transformações globais indevidamente à `Shape`.

## Testes e verificações

Na raiz do repositório, os comandos atuais são:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python scripts/check_project.py
```

O primeiro executa a suíte automatizada; o segundo valida sintaxe Python, arquivos essenciais, versões e integridade do catálogo. Para mudanças localizadas, execute primeiro os módulos relevantes (por exemplo, `python -m unittest tests.test_grid_geometry`) e, antes de declarar conclusão, a suíte ampla apropriada e `check_project.py`.

Adicione testes para bugs corrigidos e novos comportamentos quando razoável. Não remova nem enfraqueça testes para fazê-los passar. Informe exatamente comandos, resultados e testes não executados. Testes automatizados com módulos controlados/stubs não substituem validação visual ou manual no FreeCAD.

`tests/manual_grid_placement_persistence.py` é deliberadamente excluído da descoberta: execute-o no ambiente Python do FreeCAD, com `freecad/` no `sys.path`, quando alterações afetarem Grid, `Placement`, recompute ou persistência FCStd. Outros fluxos GUI também exigem roteiro e validação manual no FreeCAD.

## Fluxo obrigatório de publicação

```text
IMPLEMENTAÇÃO LOCAL
→ TESTES AUTOMATIZADOS
→ TESTE MANUAL NO FREECAD
→ APROVAÇÃO DO USUÁRIO SOBRE FUNCIONAMENTO E DESIGN
→ COMMIT
→ PUSH SOMENTE APÓS AUTORIZAÇÃO EXPLÍCITA DO USUÁRIO
```

- Nunca faça commit, push, tag ou release automaticamente.
- Testes automatizados aprovados não autorizam publicação. Aguarde a validação manual do usuário antes do commit.
- Push exige autorização explícita e separada do usuário.
- Não use comandos Git destrutivos, como `reset`, `clean` ou rebase forçado, sem solicitação explícita.

## Política adaptativa de agentes

Steel Structures não usa multiagente por padrão. Antes de cada tarefa, avalie complexidade, quantidade de módulos, riscos arquitetural e de regressão, relevância de UI/UX, necessidade de pesquisa/benchmark e dificuldade de diagnóstico. Use o menor número de agentes que gere ganho real.

Para textos, ícones, correções triviais, mudanças localizadas, tarefas mecânicas e bugs óbvios isolados, use somente um **Implementer**, responsável pela implementação, integração e testes.

Em tarefas médias ou de alto risco, use especialistas complementares somente quando houver benefício claro:

- **Architect**: define a integração antes de novos subsistemas, modelos de dados, propriedades persistentes, FeaturePython, dependências ou refatorações estruturais.
- **Technical Reviewer**: revisa independentemente regressões, duplicação, arquitetura, escopo, casos extremos, FreeCAD/Qt e testes faltantes; não deve reimplementar toda a feature.
- **CAD UI/UX Reviewer**: avalia ações, seleção, preview, feedback, inserção, propriedades, edição posterior e consistência sob a ótica de produtividade em CAD estrutural.
- **QA / Test Specialist**: cobre extremos, regressões, estados inválidos, cancelamento, Undo/Redo, documentos existentes e recompute.
- **Benchmark / Product Researcher**: antes da implementação, pesquisa conceitos e fluxos em Tekla Structures, Advance Steel, SCIA Engineer, FreeCAD e ferramentas relevantes. Não copia código/assets proprietários nem reproduz interfaces literalmente.

Ao usar múltiplos agentes, atribua responsabilidades distintas, prefira competências complementares e evite implementações duplicadas sem motivo. Em bugs complexos, hipóteses independentes podem ser úteis; em mudanças importantes, prefira revisão independente; faça benchmark/arquitetura antes de implementar quando isso evitar retrabalho. Multiagente é ferramenta de qualidade, não meta.

## Desenvolvimento de UI

- Mantenha fluxo de CAD profissional, minimize cliques e forneça feedback claro para entradas inválidas.
- Quando tecnicamente razoável, previews devem reagir imediatamente aos parâmetros relevantes.
- Cancelar deve deixar documento, callbacks, transações e interface consistentes, sem elementos temporários órfãos.
- Preserve consistência visual e comportamental entre ferramentas. Referências externas podem inspirar conceitos, mas a solução deve ser própria e coerente com Steel Structures; produtividade CAD prevalece sobre estética isolada.

## Definition of done e comunicação

Uma tarefa de código está **pronta para validação do usuário**, não para publicação, somente quando o escopo foi implementado sem mudanças desnecessárias, testes relevantes passam, comportamentos importantes têm testes quando apropriado, nenhuma regressão conhecida foi ocultada e estão documentados o que mudou e o que ainda requer teste manual no FreeCAD.

Antes de mudança de risco médio/alto, informe brevemente o que será alterado, áreas afetadas e se um agente adicional é recomendado, com motivo. Ao concluir, apresente resumo, arquivos alterados, comandos de teste e resultados, pontos de atenção e um roteiro curto de teste manual no FreeCAD quando aplicável.
