# Instruções de desenvolvimento — Steel Structures

## Contexto do projeto

- Nome do projeto: Steel Structures.
- Objetivo: bancada independente do FreeCAD dedicada exclusivamente a estruturas metálicas.
- Versão-alvo atual: FreeCAD 1.1.3.
- Python-alvo atual: Python 3.11.
- Plataforma principal de desenvolvimento: Windows.
- Idioma principal da interface: português do Brasil.

## Independência e referências externas

- Não utilizar Quetzal, Dodo ou FrameForge como dependência ou base de código.
- Quetzal, Dodo e FrameForge podem ser estudados apenas como referência de fluxo e funcionalidades.

## Arquitetura

- Manter arquitetura modular, separando interface, comandos, objetos paramétricos, geometria, catálogos e testes.
- Todo elemento estrutural deve permanecer paramétrico.
- Novas famílias de perfis devem possuir geradores geométricos próprios.
- Não assumir que todas as famílias usam seção I.

## Geometria e comportamento

- O sólido local deve ser criado no eixo Z e orientado pelo Placement do objeto.
- A rotação da seção deve ocorrer em torno do eixo longitudinal local do membro.
- Preservar a criação correta de membros em X, Y, Z e direções inclinadas.
- Preservar os modos de inserção, offsets, extensões, massa e propriedades de catálogo.
- Não modificar comportamento visual ou funcional sem solicitação explícita.
- Não alterar catálogos sem citar a origem dos dados.

## Qualidade e entrega

- Toda correção ou nova função deve possuir testes quando tecnicamente possível.
- Alterações devem ser resumidas no CHANGELOG.
- A versão deve permanecer sincronizada entre package.xml, __init__.py e documentação.
- Antes de concluir uma tarefa, executar as verificações aplicáveis e apresentar os resultados.
- Não realizar commits automaticamente, salvo quando solicitado explicitamente.
