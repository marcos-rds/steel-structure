# Metal Structure — FreeCAD

Bancada paramétrica dedicada à modelagem de estruturas metálicas no FreeCAD.

## Versão 0.4.0

- Um único comando público, **Criar elemento estrutural** (`BFC_CreateMember`), concentra o fluxo de criação.
- A ferramenta reutiliza a Linha nativa do Draft para escolher dois pontos, pelo mouse ou pelos controles numéricos do Draft.
- Snaps, restrições, Relativo e Global seguem diretamente as configurações nativas do Draft.
- O modo **Continuar** cria vários membros na mesma sessão.
- As opções estruturais ficam integradas ao painel: nome, tipo, perfil, inserção, rotação e cor.
- O tipo do elemento pode ser escolhido entre **Membro**, **Pilar**, **Viga** e **Contraventamento**.
- Seleção hierárquica por **Categoria do perfil → Série do perfil → Perfil**.
- Categorias iniciais: **Aço laminado** e **Aço dobrado**.
- Série disponível nesta versão: **Perfis W**.
- Designações compactas na interface, como `W150x13,0` e `W200x26,6`.
- A designação canônica original do catálogo, como `W 150 x 13,0`, permanece armazenada internamente nos objetos para preservar a compatibilidade.
- Campo **Nome** nas opções do perfil e nas propriedades do objeto.
- Numeração automática legível: `Membro 001 - W150x13,0` e `Pilar 001 - W200x26,6`.
- Propriedade **Length** editável, sincronizada com `StartPoint`, `EndPoint` e `MemberLength`.
- Correção da orientação entre quaisquer pontos X, Y e Z.
- Correção da propriedade **Rotação da seção**.
- Correção do erro de inicialização da propriedade `Manufacturer` no FreeCAD 1.1.3.
- Migração básica de membros criados na versão 0.1.0.

## Instalação

1. Feche o FreeCAD.
2. Remova a pasta antiga `BancadaFC_Steel_v0.1.0` de `%APPDATA%\FreeCAD\Mod\`.
3. Extraia a pasta `MetalStructure_v0.4.0` dentro de `%APPDATA%\FreeCAD\Mod\`.
4. Reinicie o FreeCAD e selecione **Metal Structure**.

## Testes recomendados

Crie quatro elementos com ponto inicial `(0, 0, 0)`:

- X: ponto final `(3000, 0, 0)`;
- Y: ponto final `(0, 3000, 0)`;
- Z: ponto final `(0, 0, 3000)`;
- Inclinado: ponto final `(2000, 1500, 2500)`.

Em seguida, altere **Rotação da seção** para `45°` e `90°` na aba Dados.
