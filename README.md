# Keyboard Split Manager (v0.1.0-beta)

> **Editor visual de keymaps e gerenciador de configurações para teclados split (Corne e Sofle)**  
> Versão: `v0.1.0-beta` · Licença: MIT / Open Source

---

## 📌 Visão Geral

O **Keyboard Split Manager** é uma ferramenta gráfica *single-file* (HTML/JavaScript puro) desenvolvida para visualização, customização, auditoria e geração de layouts para teclados mecânicos ergonômicos divididos. Funciona 100% offline diretamente no navegador, sem necessidade de servidor backend ou dependências externas em tempo de execução.

### Status de Qualidade
* **Auditoria de Código:** Pendências identificadas na auditoria técnica corrigidas.
* **Testes Automatizados:** 
  * **106/106 testes integrados aprovados** via Playwright e navegador real Chromium (`app/test_html_final.js`), cobrindo renderização, persistência, migração, histórico pré-mutação e resgate de emergência.
  * **38/38 testes aprovados** na suíte unitária Python (`pytest tests/`), cobrindo validadores de schema, extratores e integridade canônica.
* **Build Determinístico:** Hashes SHA-256 reproduzíveis para o HTML empacotado e dataset canônico.

---

## ✨ Funcionalidades Principais

* **🔍 Zoom Dinâmico no Teclado (60% a 250%):**  
  Ajuste ergonômico da escala com botões `[−]`, `[+]` e `[100%]`. Aumenta teclas, fontes principais, sub-rótulos e bindings, mantendo a preferência memorizada no navegador (`localStorage`).
* **📋 Cópia e Colagem Completa de Teclas:**  
  O botão `📋 Copiar tecla` no editor captura todas as propriedades da tecla: rótulo (*label*), sub-rótulo (*sub*), comportamento descritivo, código Vial/QMK (`impl_qmk`), binding ZMK (`impl_zmk`), tipo de tecla e status.
* **⇄ Troca de Teclas (Swap):**  
  Inversão rápida entre duas posições do teclado com escolha de escopo (apenas na camada ativa ou em todas as camadas). Limpa automaticamente referências a bindings órfãos no destino.
* **🛡️ Histórico Seguro com Desfazer:**  
  Gravação automática de *checkpoints* pré-mutação antes de qualquer edição ou troca. A edição ou troca é cancelada caso o navegador não consiga salvar o ponto de restauração, garantindo que o estado anterior nunca seja perdido.
* **🚨 Resgate de Rascunhos em Caso de Falha (`downloadText`):**  
  Tratador de contingência na inicialização (`safeInit`) que permite baixar rascunhos locais mesmo que o JSON esteja corrompido ou truncado (`ksm_rascunho_bruto.json`), além de opções para exportar a sessão ativa ou o mapa original de fábrica.
* **⌨️ Perfis Independentes de Hardware:**  
  * **Corne Simples v13:** 7 camadas canônicas (L0 Base, L1 Symbols, L2 Num, L3 Mouse, L4 Nav, L5 System, L6 Fun) com macros matemáticas (`math_power`, `math_square`, `math_sqrt`, `math_exp`), tap-dances de trava (`td_lock_mouse`, `td_lock_nav`) e dedões com hold-tap `&fp_mo`.
  * **Sofle 58:** Suporte a 58 teclas, rotary encoders e 10 posições dedicadas de polegar com compatibilidade Vial.

---

## 🚀 Como Usar

### 1. Abrir no Navegador
Basta abrir o arquivo standalone diretamente no seu navegador preferido (Chrome, Safari, Firefox, Edge):
```bash
open deliverables/keyboard_split_manager_v19_perfis.html
```
Não requer instalação de Node.js ou Python para edição do mapa.

### 2. Edição e Exportação
1. Selecione o teclado (**Corne** ou **Sofle**) e a camada desejada (L0 a L6 no Corne Simples).
2. Clique sobre qualquer tecla para abrir o modal de edição.
3. Ajuste o rótulo, código QMK ou binding ZMK e clique em **Salvar edição**.
4. Use o botão **Baixar (JSON)** para exportar seu layout atualizado.

### 3. Geração de Keymaps para Firmware
Para gerar o arquivo de layout ZMK DeviceTree (`.keymap`) correspondente ao perfil Corne Simples:
```bash
python3 generators/generate_corne_candidato.py --profile simple --dataset data/keymap_data_v06.json --out generators/candidates/corne_simples_v13.keymap
```

---

## ⚠️ Limitações Conhecidas e Escopos Pendentes

Para máxima clareza e rigor técnico, destacam-se os limites atuais desta versão beta:

1. **Compilação de Firmware Binário ZMK (`.uf2`):**  
   O editor e os geradores produzem o arquivo de texto de configuração ZMK DeviceTree ([`corne_simples_v13.keymap`](generators/candidates/corne_simples_v13.keymap)). A compilação desse arquivo em um binário `.uf2` executável requer o toolchain Zephyr/ZMK (`west build`, Zephyr SDK) e deve ser executada em ambiente com suporte ou via pipeline de CI (GitHub Actions).
2. **Gravação e Validação Física:**  
   A gravação física do arquivo `.uf2` via USB no microcontrolador em modo bootloader e o teste tátil de digitação/ergonomia física no Corne real continuam pendentes.
3. **Dispositivos Móveis (Safari / iOS):**  
   O aplicativo conta com avisos `<noscript>` e media queries CSS adaptativas para telas pequenas (`@media (max-width: 768px)`), mas a homologação visual em dispositivo físico Safari/iPhone ainda não foi executada.
4. **Sem Conexão WebHID/USB Direta:**  
   O aplicativo edita e audita as matrizes de layout localmente; ele não grava diretamente na memória EEPROM do teclado via cabo USB em tempo real.

---

## 🧪 Suíte de Testes e Reprodutibilidade

Para rodar os testes automatizados localmente:

```bash
# 1. Testes unitários de dados e geradores (Python)
pytest tests/ -v

# 2. Testes integrados de interface e navegador real (Playwright / Chromium)
node app/test_html_final.js deliverables/keyboard_split_manager_v19_perfis.html

# 3. Verificação de integridade estrutural e determinismo
python3 app/verify_ksm.py
```

---

## 📦 Arquivos da Entrega

* **Aplicação Standalone:** `deliverables/keyboard_split_manager_v19_perfis.html` (e `index.html` na raiz para execução web)
* **Keymap ZMK Gerado (Corne Simples v13):** `generators/candidates/corne_simples_v13.keymap`
* **Dataset Canônico:** `data/keymap_data_v06.json`
