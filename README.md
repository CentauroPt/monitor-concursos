# Monitor de Concursos Públicos (Portal BASE & TED Europa)

Aplicação web concebida para a pesquisa e monitorização diária de concursos públicos, procedimentos e ajustes diretos no **Portal BASE** (Portugal) e no **TED - Tenders Electronic Daily** (União Europeia).

---

## 🔍 Critérios de Pesquisa Configurados

1. **Palavras-chave**:
   - `Unidade Móvel`
   - `Unidades Móveis`
   - `Viatura especial`
   - `Viaturas Especiais`
   - `Carrinha`
   - `Biblioteca itinerante`

2. **Gama de Códigos CPV**:
   - **`34140000` a `34149999`**: Veículos a motor pesados, viaturas de recolha, furgões e veículos para usos especiais.

3. **Resumo Individual por Concurso**:
   - 📌 **Objeto do Concurso** (designação detalhada)
   - ⏳ **Prazo de Entrega da Proposta** (data/hora limite de submissão)
   - 💰 **Valor a Concurso** (preço base / estimativa em Euros)
   - 🏢 **Entidade Adjudicante**
   - 🔗 **Link direto clicável** para abrir o anúncio oficial no Portal BASE ou TED

---

## 🚀 Como Iniciar

### Opção 1: Duplo clique (Mais fácil no Windows)
Dê um duplo clique no ficheiro:
```text
iniciar_monitor.bat
```
O servidor será iniciado e o seu navegador abrirá automaticamente em `http://localhost:8080`.

### Opção 2: Linha de comandos
No terminal, dentro desta pasta:
```bash
py app.py
```
Em seguida, abra o navegador em: [http://localhost:8080](http://localhost:8080)

---

## 💡 Como Usar a Página Web
1. Abra a página e clique no botão azul **"Pesquisar Concursos"**.
2. O sistema consultará automaticamente o **Portal BASE** e a API oficial do **TED Europa**.
3. Pode filtrar os resultados:
   - Pelos separadores: **Todos**, **Portal BASE** ou **TED Europa**.
   - Pela barra de pesquisa instantânea (pesquisa por nome de entidade, valor ou palavra).
   - Por âmbito do TED: Portugal ou toda a União Europeia.
4. Clique em **"Abrir no Portal Oficial ↗"** em qualquer concurso para aceder à página oficial.
5. Clique em **"📋 Ver Resumo"** para visualizar e copiar a síntese individual com um clique.
6. Clique em **"📥 Exportar Excel"** para descarregar a lista completa para uma folha de cálculo.
