# Metal Structure — FreeCAD

Bancada paramétrica dedicada à modelagem de estruturas metálicas no FreeCAD.

## Versão 0.2.0

- Nome da bancada alterado para **Metal Structure**.
- Seleção hierárquica por **Categoria do perfil → Série do perfil → Perfil**.
- Categorias iniciais: **Aço laminado** e **Aço dobrado**.
- Série disponível nesta versão: **Perfis W**.
- Campo **Nome** no diálogo e nas propriedades do objeto.
- Numeração automática legível: `Pilar 001 - W 200 x 26,6`.
- Correção da orientação entre quaisquer pontos X, Y e Z.
- Correção da propriedade **Rotação da seção**.
- Correção do erro de inicialização da propriedade `Manufacturer` no FreeCAD 1.1.3.
- Migração básica de membros criados na versão 0.1.0.

## Instalação

1. Feche o FreeCAD.
2. Remova a pasta antiga `BancadaFC_Steel_v0.1.0` de `%APPDATA%\FreeCAD\Mod\`.
3. Extraia a pasta `MetalStructure_v0.2.0` dentro de `%APPDATA%\FreeCAD\Mod\`.
4. Reinicie o FreeCAD e selecione **Metal Structure**.

## Testes recomendados

Crie quatro elementos com ponto inicial `(0, 0, 0)`:

- X: ponto final `(3000, 0, 0)`;
- Y: ponto final `(0, 3000, 0)`;
- Z: ponto final `(0, 0, 3000)`;
- Inclinado: ponto final `(2000, 1500, 2500)`.

Em seguida, altere **Rotação da seção** para `45°` e `90°` na aba Dados.
