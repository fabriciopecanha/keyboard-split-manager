#!/usr/bin/env node
/* test_html_final.js — F6/F5: testes do HTML FINAL entregue, não de fontes separadas.

Parte A (Node/VM): scripts extraídos do próprio HTML final:
  - parseWithExactUid (F4) sobre casos reproduzidos do review;
  - validateDataset (F3) sobre dataset embutido e sobre mutações malformadas;
  - paridade canônica embutido ↔ dataset.

Parte B (Playwright + Chrome real, perfil isolado):
  - título v06, sem "v05 Homologado";
  - honestidade do comparador (F2): dif diferença textual real (15 esperadas), sem engolir;
  - importações incompletas recusadas (F3) sem mutar estado;
  - UID numérico + campo seguinte na importação → exato, sem SyntaxError (F4);
  - edição + rascunho persistido (localStorage simulado pelo perfil isolado).

Saída: JSON em reports/VERIFY_HTML_V06_TESTS.json (quando OUT= path informado).
*/
const fs = require("fs");
const os = require("os");
const path = require("path");
const vm = require("vm");

const KSM = path.resolve(__dirname, "..");
const HTML_PATH = path.resolve(process.argv[2] || process.env.HTML_PATH || path.join(KSM, "deliverables", "keyboard_split_manager_v06.html"));
const DATASET_PATH = path.join(KSM, "data", "keymap_data_v06.json");
const OUT_JSON = process.env.OUT_JSON || "";
const UID = "12888985424971681029";
const EXPECTED_DIFFS_DEFAULT_LAYER_VS_L0 = 15;

const results = [];
function rec(name, ok, detail) { results.push({ name, ok, detail: detail === undefined ? "" : String(detail).slice(0, 400) }); }

/* ---------------- Parte A ---------------- */
function extractScripts(html) {
  const coreBlocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  const dataMatch = html.match(/<script id="ksm-data" type="application\/json">([\s\S]*?)<\/script>/);
  return { coreBlocks, dataJson: dataMatch ? dataMatch[1].replace(/<\\\/script/g, "</script") : null };
}

let core, embeddedParsed, html;
try {
  html = fs.readFileSync(HTML_PATH, "utf8");
  rec("html existe", true, `${html.length} B`);
  const { coreBlocks, dataJson } = extractScripts(html);
  rec("html pacote modular (core+app blocks == 2, data presente)", coreBlocks.length === 2 && !!dataJson, `blocks=${coreBlocks.length} sizes=[${coreBlocks.map(b => b.length).join(", ")}] data=${dataJson ? dataJson.length : 0} B`);
  const sandbox = { module: { exports: {} }, console, TextEncoder, require: (m) => require(m) };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(coreBlocks[0], sandbox);
  core = sandbox.module.exports;
  rec("core extraído do HTML final carregado", !!(core && core.validateDataset && core.parseWithExactUid), Object.keys(core).join(","));
  embeddedParsed = core.parseWithExactUid(dataJson);
  const dsText = fs.readFileSync(DATASET_PATH, "utf8");
  const dsParsed = core.parseWithExactUid(dsText);
  const same = core.canonicalString(embeddedParsed) === core.canonicalString(dsParsed);
  rec("paridade canônica embutido == dataset (F6/integridade real)", same, core.canonicalString(embeddedParsed).slice(0, 60) + "…");
} catch (e) {
  rec("carregar HTML final + core", false, e.message);
}

// F4 — UID exato nos casos do review
if (core) {
  const uidCases = [
    ["num + campo seguinte", '{"uid": ' + UID + ', "x": 1}'],
    ["num + fechamento", '{"uid": ' + UID + '}'],
    ["sem espaco + virgula", '{"uid":' + UID + ',"x":1}'],
    ["espaco + fechamento", '{"uid": ' + UID + ' }'],
    ["num no fim do objeto com espaco", '{"uid": ' + UID + '\n, "y": 2}'],
  ];
  for (const [name, txt] of uidCases) {
    try {
      const o = core.parseWithExactUid(txt);
      rec("F4 uid exato: " + name, o.uid === UID, `uid=${JSON.stringify(o.uid)}`);
    } catch (e) { rec("F4 uid exato: " + name, false, `Exception ${e.message} (antes do review: SyntaxError)`); }
  }
  // uid numérico dentro de estrutura real (emular v6 numérica via texto)
  try {
    const dsText = fs.readFileSync(DATASET_PATH, "utf8");
    const numeric = dsText.replace(/"references"\s*:\s*{/, '"references": {"__forceNumericUid__": 123, ');
    const parsed = core.parseWithExactUid(numeric);
    rec("F4 parse dataset com campo numérico colado em uid-texto", typeof parsed.references.sofle.uid === "string" && parsed.references.sofle.uid === UID, `uid=${JSON.stringify(parsed.references.sofle.uid)}`);
  } catch (e) { rec("F4 uid sobre dataset real com mutação numérica", false, e.message); }
}

// F3 — validator: dataset válido e mutações malformadas recusadas
if (core && embeddedParsed) {
  const errs0 = core.validateDataset(embeddedParsed, false);
  rec("F3 validação do dataset embutido (0 erros)", errs0.length === 0, errs0.join(" | "));

  const clone = () => JSON.parse(JSON.stringify(embeddedParsed));
  const mustFail = (label, mutate, expectSub) => {
    try {
      const m = clone();
      mutate(m);
      const errs = core.validateDataset(m, false);
      const hit = errs.some(e => expectSub.some(s => e.includes(s)));
      rec("F3 recusa: " + label, errs.length > 0 && hit, `erros=${errs.length} ${errs.slice(0, 2).join(" | ")}`);
    } catch (e) { rec("F3 recusa: " + label, false, "exceção " + e.message); }
  };
  mustFail("sem profiles", m => { delete m.profiles; }, ["profiles.candidato_teste"]);
  mustFail("sem references", m => { delete m.references; }, ["references.corne.native_layers ausente", "references.sofle.vil ausente"]);
  mustFail("matrix corne L0 reduzida a 1 tecla", m => { m.layers.L0.corne.matrix = m.layers.L0.corne.matrix.slice(0, 1); }, ["matrix deve ser 3x12"]);
  mustFail("dedões L0 corne vazios", m => { m.layers.L0.corne.thumbs = []; }, ["thumbs deve ter 6"]);
  mustFail("dedões L0 sofle vazios", m => { m.layers.L0.sofle.thumbs = []; }, ["thumbs deve ter 10"]);
  mustFail("espelho profiles divergente", m => { m.profiles.candidato_teste.corne.layers.L0.matrix[0][0].label = "DIVERGE"; }, ["espelho divergente"]);
  mustFail("conflicts não-lista", m => { m.conflicts = {}; }, ["conflicts deve ser lista"]);
  mustFail("uid sofle não-string", m => { m.references.sofle.vil.uid = 123; }, ["uid deve ser string decimal"]);
  mustFail("vil layout com 15 camadas", m => { m.references.sofle.vil.layout = m.references.sofle.vil.layout.slice(0, 15); }, ["layout deve ter 16"]);
  mustFail("schema_version inválido", m => { m.schema_version = 99; }, ["schema_version"]);
}

// F10 — a validação respeita o schema da versão importada: o v05 ORIGINAL
// (Corne/keymap_data.json, sem "conflicts") não pode mais ser recusado pela migração.
const V05_FIXTURE_PATH = path.join(KSM, "data", "fixtures", "keymap_data_v05.json");
const V05_PATH = fs.existsSync(V05_FIXTURE_PATH) ? V05_FIXTURE_PATH : path.join(KSM, "..", "Corne", "keymap_data.json");
if (core && fs.existsSync(V05_PATH)) {
  try {
    const v5Text = fs.readFileSync(V05_PATH, "utf8");
    const v5 = core.parseWithExactUid(v5Text);
    rec("F10 parse v05 original ok", v5.schema_version === 5, "schema=" + v5.schema_version + " size=" + v5Text.length + " B");
    const errs5 = core.validateDataset(v5, true);
    rec("F10 v05 original aceito pela validação (0 erros, sem 'conflicts')", errs5.length === 0, errs5.join(" | ") || "0 erros");
    const v5up = JSON.parse(JSON.stringify(v5));
    v5up.schema_version = 6;
    const errsUp = core.validateDataset(v5up, true);
    rec("F10 v5 promovido a schema 6 continua exigente (conflicts obrigatório no 6)", errsUp.some(e => e.includes("conflicts")), errsUp.slice(0, 2).join(" | "));
  } catch (e) {
    rec("F10 v05 original validado", false, "exceção " + e.message);
  }
}

/* ---------------- Parte B (Playwright + Chrome real) ---------------- */
async function partB() {
  let pw;
  try {
    pw = require("playwright");
  } catch (e) {
    pw = null;
  }
  if (!pw) {
    rec("playwright disponível", false, "playwright não encontrado (execute: npm ci ou npm install)");
    return;
  }
  rec("playwright disponível", true, "módulo playwright disponível");

  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "ksm-chrome-"));
  let browser;
  try {
    browser = await pw.chromium.launch({ channel: "chrome", headless: true });
  } catch (e) {
    browser = await pw.chromium.launch({ headless: true });
  }
  const context = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
  const page = await context.newPage();
  const dialogMsgs = [];
  const consoleErrors = [];
  const pageErrors = [];
  page.on("dialog", async d => { dialogMsgs.push(d.message()); try { await d.dismiss(); } catch (e) { /* ignore */ } });
  page.on("console", m => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", e => pageErrors.push(String(e && e.message)));

  const url = "file://" + HTML_PATH;
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(300);

  // título v19 / consolidado
  const title = await page.title();
  rec("título do app consolidado", /v06|v18|v19/i.test(title), title);
  const bodyText = await page.evaluate(() => document.body.innerText);
  rec("sem 'v05 Homologado' na UI", !bodyText.includes("v05 Homologado"), "checa innerText");
  rec("nenhum pageerror no load (ex.: TypeError reading 'L0')", pageErrors.length === 0, pageErrors.join(" | "));

  // board candidato corne L0
  let firstKey = await page.evaluate(() => { const k = document.querySelector("#boardWrap .key"); return k ? k.innerText.replace(/\n/g, "|") : null; });
  rec("candidato corne L0 renderizado", !!firstKey && firstKey.includes("Tab"), firstKey);

  // perfil de referência (ex-Hardware Instalado) — F1
  await page.click('button[data-profile="reference"]');
  await page.waitForTimeout(150);
  let refKey = await page.evaluate(() => { const k = document.querySelector("#boardWrap .key"); return k ? k.innerText.replace(/\n/g, "|") : null; });
  rec("perfil Referência renderiza bindings nativos &kp (F1)", !!refKey && refKey.includes("&kp"), refKey);
  // clique em referência → alerta somente leitura, sem crash
  await page.click("#boardWrap .key");
  await page.waitForTimeout(100);
  rec("referência é somente leitura (alerta, sem crash)", dialogMsgs.some(m => m.includes("somente leitura")), (dialogMsgs[0] || "").slice(0, 80));
  await page.click('button[data-profile="candidate"]');
  await page.waitForTimeout(100);

  // sofle 10 dedões + nota de encoders
  await page.click('button[data-kb="sofle"]');
  await page.waitForTimeout(150);
  const sofleHasNote = await page.evaluate(() => document.body.innerText.includes("encoders"));
  rec("sofle 58 com nota de encoders", sofleHasNote, "");
  const thumbsCount = await page.evaluate(() => document.querySelectorAll("#boardWrap .thumbs .key").length);
  rec("sofle tem 10 dedões visíveis", thumbsCount === 10, `count=${thumbsCount}`);
  await page.click('button[data-kb="corne"]');
  await page.waitForTimeout(100);

  // comparador honesto (F2): cand L0 vs default_layer
  await page.click("#btnCompare");
  await page.waitForSelector("#dlgCompare[open]", { timeout: 3000 });
  await page.selectOption("#cmpA", "cand:L0");
  await page.selectOption("#cmpB", "refc:default_layer");
  await page.click("#cmpRun");
  await page.waitForTimeout(200);
  const cmpOut = await page.evaluate(() => document.getElementById("cmpOut").innerText);
  const rowMatches = cmpOut.match(/(\d+) diferença\(s\) textual\(is\)/);
  const diffCount = rowMatches ? parseInt(rowMatches[1], 10) : -1;
  rec("F2 comparador mostra diferenças reais", diffCount === EXPECTED_DIFFS_DEFAULT_LAYER_VS_L0, `esperado=${EXPECTED_DIFFS_DEFAULT_LAYER_VS_L0} obtido=${diffCount}`);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(100);

  // importações recusadas (F3): matriz com 1 tecla; sem profiles; sem references
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ksm-import-"));
  const mkImport = (name, mutate) => {
    const m = JSON.parse(JSON.stringify(embeddedParsed));
    mutate(m);
    const p = path.join(tmpDir, name);
    fs.writeFileSync(p, JSON.stringify(m, null, 1), "utf8");
    return p;
  };
  const importCases = [
    ["incompleto_matrix1key.json", m => { m.layers.L0.corne.matrix = m.layers.L0.corne.matrix.slice(0, 1); }],
    ["incompleto_sem_profiles.json", m => { delete m.profiles; }],
    ["incompleto_sem_references.json", m => { delete m.references; }],
  ];
  const chipBefore = await page.evaluate(() => document.getElementById("chipDirty").innerText);
  let firstRefuseMsgDetail = "";
  for (const [name, mutate] of importCases) {
    const p = mkImport(name, mutate);
    await page.setInputFiles("#fileImport", p);
    await page.waitForTimeout(250);
    const msg = dialogMsgs.find(x => x.includes("IMPORTAÇÃO RECUSADA"));
    rec("F3 import recusada: " + name, !!msg, (msg || "nenhum alerta de recusa").split("\n").slice(0, 2).join(" | "));
    if (!firstRefuseMsgDetail && msg) firstRefuseMsgDetail = msg.split("\n").slice(0, 3).join(" | ");
  }
  const chipAfter = await page.evaluate(() => document.getElementById("chipDirty").innerText);
  rec("estado preservado após recusas (chip igual)", chipBefore === chipAfter, `${chipBefore} → ${chipAfter}`);

  // F4 em importação REAL: uid como número + campo seguinte → exato, sem crash
  const t = fs.readFileSync(DATASET_PATH, "utf8");
  const uidNumericBefore = (t.match(/"uid": "12888985424971681029"\s*,/g) || []).length;
  const uidNumericText = uidNumericBefore
    ? t.replace(/"uid": "12888985424971681029"\s*,/g, '"uid": 12888985424971681029, "__next": 1,')
    : t;
  rec("mutation uid numérico preparada", uidNumericBefore >= 2, `${uidNumericBefore} ocorrências convertidas para número`);
  const pU = path.join(tmpDir, "uid_numeric.json");
  fs.writeFileSync(pU, uidNumericText, "utf8");
  const errsBeforeImport = pageErrors.length;
  await page.setInputFiles("#fileImport", pU);
  await page.waitForTimeout(300);
  const uidMsgIdx = dialogMsgs.map(m => m.includes("Arquivo válido importado")).lastIndexOf(true);
  const uidMsg = uidMsgIdx >= 0 ? dialogMsgs[uidMsgIdx] : "";
  const uidOk = uidMsg.includes(UID) && pageErrors.length === errsBeforeImport;
  rec("F4 import com uid numérico + campo seguinte → exato", !!uidOk, (uidMsg.split("\n").slice(0, 2).join(" | ") || pageErrors.join("|") || "sem alerta"));

  // importação válida própria (baseline do estado) → aceita
  const pV = path.join(tmpDir, "valida_v6.json");
  fs.writeFileSync(pV, fs.readFileSync(DATASET_PATH, "utf8"), "utf8");
  await page.setInputFiles("#fileImport", pV);
  await page.waitForTimeout(300);
  rec("import válida v6 aceita", (dialogMsgs.find(x => x.includes("Arquivo válido importado")) || "").includes(UID) || dialogMsgs.filter(x => x.includes("Arquivo válido importado")).length >= 2, "");

  // edição + rascunho persistido + reload
  await page.click("#boardWrap .key");
  await page.waitForSelector("#dlgEdit[open]", { timeout: 3000 });
  await page.fill("#editSub", "EDT-TEST");
  await page.click("#editSave");
  await page.waitForTimeout(600);
  const draft = await page.evaluate(() => localStorage.getItem("ksm_v06_draft"));
  rec("rascunho v06 gravado em localStorage", !!draft && draft.includes("EDT-TEST"), draft ? `${draft.length} B` : "vazio");
  const cellSub = await page.evaluate(() => document.querySelector("#boardWrap .key .sub").innerText);
  rec("edição refletida no board (sub=EDT-TEST)", cellSub === "EDT-TEST", cellSub);
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(400);
  const subAfterReload = await page.evaluate(() => document.querySelector("#boardWrap .key .sub").innerText);
  rec("rascunho recuperado após reload", subAfterReload === "EDT-TEST", subAfterReload);
  rec("nenhum pageerror acumulado", pageErrors.length === 0, pageErrors.join(" | "));

  // limpeza de estado e restauração pristine
  await page.evaluate(() => localStorage.clear());
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(300);
  const pristineSub = await page.evaluate(() => document.querySelector("#boardWrap .key .sub").innerText);
  rec("limpeza restaura estado pristine do dataset embutido", pristineSub !== "EDT-TEST", pristineSub);

  /* ---------- cenários F7–F11 (contextos isolados por cenário) ---------- */
  let v5TextReal = null;
  try { v5TextReal = fs.readFileSync(V05_PATH, "utf8"); } catch (e) { v5TextReal = null; }
  rec("v05 original acessível para cenários F8–F10", !!v5TextReal && v5TextReal.length > 900000, v5TextReal ? v5TextReal.length + " B" : "ARQUIVO AUSENTE");

  async function freshPage(acceptDialog = false) {
    const c2 = await browser.newContext({ viewport: { width: 1500, height: 1000 } });
    const p2 = await c2.newPage();
    const msgs2 = [], perr2 = [];
    p2.on("dialog", async d => {
      msgs2.push(d.message());
      try {
        if (p2.__acceptNextDialog || acceptDialog) {
          p2.__acceptNextDialog = false;
          await d.accept();
        } else {
          await d.dismiss();
        }
      } catch (e) { /* ignore */ }
    });
    p2.on("console", m => { if (m.type() === "error") perr2.push(m.text()); });
    p2.on("pageerror", e => perr2.push(String(e && e.message)));
    return { c2, p2, msgs2, perr2 };
  }

  // F7 — gravação com SNAPSHOT: edição durante a gravação fica FORA do arquivo
  if (v5TextReal && core) {
    const { c2, p2, msgs2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    await p2.evaluate(() => {
      window.__gatePromise = new Promise(res => { window.__gateResolve = res; });
      window.showSaveFilePicker = async () => ({
        name: "keymap_data_v06_test_snapshot.json",
        createWritable: async () => ({
          buf: [],
          write(chunk) { this.buf.push(String(chunk)); return undefined; },
          async close() { await window.__gatePromise; window.__saved = this.buf.join(""); },
        }),
      });
    });
    await p2.click("#btnWriteFile");
    await p2.waitForFunction("() => window.__gateResolve !== undefined", null, { timeout: 5000 });
    await p2.click("#boardWrap .key");
    await p2.waitForSelector("#dlgEdit[open]", { timeout: 3000 });
    await p2.fill("#editSub", "GRAV-CORRENTE");
    await p2.click("#editSave");
    await p2.waitForTimeout(150);
    await p2.evaluate(() => window.__gateResolve());
    await p2.waitForTimeout(400);
    const saved = await p2.evaluate(() => window.__saved || "");
    rec("F7 arquivo recebeu o SNAPSHOT (edição durante a gravação ficou fora)", saved.startsWith("{") && !saved.includes("GRAV-CORRENTE"), saved ? saved.length + " B; edição dentro do arquivo=" + saved.includes("GRAV-CORRENTE") : "nada gravado");
    const chip = await p2.evaluate(() => document.getElementById("chipDirty").innerText);
    rec("F7 chip mantém 'Alterações NÃO salvas' (edição posterior não vira 'confirmado')", chip.includes("NÃO salvas"), chip);
    const chipFile = await p2.evaluate(() => document.getElementById("chipFile").innerText);
    rec("F7 arquivo não marcado 'confirmado' enquanto há pendência", chipFile.includes("não confirmado"), chipFile);
    rec("F7 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F8 — histórico aceita e sobrevive ao reload com entradas v05 arquivadas
  if (v5TextReal && core) {
    const { c2, p2, msgs2, perr2 } = await freshPage();
    const v5Obj = core.parseWithExactUid(v5TextReal);
    const entry = JSON.stringify([{ ts: "2026-10-29T10:00:00.000Z", label: "rascunho antigo v05 (teste F8)", hash: "teste", data: v5Obj }]);
    await c2.addInitScript(([e]) => { try { localStorage.setItem("ksm_v06_history", e); } catch (err) { /* ignore */ } }, [entry]);
    await p2.goto(url, { waitUntil: "load" });
    await p2.click("#btnHistory");
    await p2.waitForSelector("#dlgHistory[open]", { timeout: 3000 });
    const histText = await p2.evaluate(() => document.getElementById("histOut").innerText);
    rec("F8 entrada v05 sobrevive ao recarregar e aparece no histórico", histText.includes("rascunho antigo v05 (teste F8)"), histText.split("\n").slice(0, 3).join(" | "));
    await p2.locator("#histOut button", { hasText: "Restaurar" }).first().click();
    await p2.waitForTimeout(250);
    const bannerText = await p2.evaluate(() => document.getElementById("banner").innerText);
    rec("F8 restaurar v05 vai ao banner de migração (não aplica direto)", bannerText.includes("Migrar com referência histórica") && bannerText.includes("Arquivar rascunho"), bannerText.split("\n").slice(0, 2).join(" | "));
    rec("F8 alerta informa o caminho seguro para v05", msgs2.some(m => m.includes("banner de migração")), (msgs2.find(m => m.includes("banner")) || "").split("\n")[0]);
    rec("F8 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F9 — armazenamento cheio NÃO gera mensagem falsa de sucesso
  if (v5TextReal) {
    const { c2, p2, msgs2, perr2 } = await freshPage();
    await c2.addInitScript(([v5]) => {
      try { localStorage.setItem("keyboard_split_manager_data_v05", v5); } catch (err) { /* ignore */ }
      const orig = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k, val) {
        if (k === "ksm_v06_history") { const e = new Error("QuotaExceededError (simulado)"); e.name = "QuotaExceededError"; throw e; }
        return orig.call(this, k, val);
      };
    }, [v5TextReal]);
    await p2.goto(url, { waitUntil: "load" });
    await p2.waitForTimeout(300);
    const arqButtons = await p2.locator("button", { hasText: "Arquivar rascunho" }).count();
    rec("F9 setup: rascunho antigo presente no banner", arqButtons > 0, "count=" + arqButtons);
    if (arqButtons) {
      await p2.locator("button", { hasText: "Arquivar rascunho" }).first().click();
      await p2.waitForTimeout(500);
    }
    rec("F9 NENHUMA mensagem de 'arquivado' com armazenamento falhando", !msgs2.some(m => m.includes("arquivado no histórico")), msgs2.map(m => m.split("\n")[0]).join(" || ").slice(0, 300));
    rec("F9 alerta honesto 'ARQUIVAMENTO NÃO CONFIRMADO' exibido", msgs2.some(m => m.includes("ARQUIVAMENTO NÃO CONFIRMADO")), msgs2.map(m => m.split("\n")[0]).join(" || ").slice(0, 200));
    const stillThere = await p2.locator("button", { hasText: "Arquivar rascunho" }).count();
    rec("F9 rascunho permanece disponível no banner (nada perdido)", stillThere > 0, "count=" + stillThere);
    rec("F9 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F10 — importação do v05 ORIGINAL aceita (schema da versão importada respeitado)
  if (v5TextReal) {
    const { c2, p2, msgs2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    await p2.setInputFiles("#fileImport", V05_PATH);
    await p2.waitForTimeout(500);
    rec("F10 v05 original importado sem recusa (banner de migração)", msgs2.some(m => m.includes("Rascunho v05 válido recebido")), msgs2.map(m => m.split("\n")[0]).join(" || ").slice(0, 250));
    rec("F10 NENHUM 'IMPORTAÇÃO RECUSADA' para o schema da própria versão", !msgs2.some(m => m.includes("IMPORTAÇÃO RECUSADA")), msgs2.map(m => m.split("\n")[0]).join(" || ").slice(0, 250));
    const mig = await p2.locator("button", { hasText: "Migrar com referência histórica" }).count();
    rec("F10 banner de migração ativo para o v05", mig > 0, "count=" + mig);
    rec("F10 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F11 — comando de verificação real (arquivo correto, argumentos reais)
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    await p2.click("#btnGenerate");
    await p2.waitForSelector("#dlgGenerate[open]", { timeout: 3000 });
    const cmd = await p2.evaluate(() => document.getElementById("genVerify").value);
    rec("F11 aponta para o arquivo real app/verify_ksm.py", cmd.includes("app/verify_ksm.py"), cmd.split("\n").slice(0, 2).join(" | "));
    rec("F11 não aponta mais para generators/verify_ksm.py (inexistente)", !cmd.includes("generators/verify_ksm.py"), cmd.split("\n").slice(0, 2).join(" | "));
    rec("F11 sem argumento inventado --dataset (o verificador não o aceita)", !cmd.includes("--dataset"), cmd.split("\n")[1] || "");

    // F12 — comando Sofle aponta para compose_sofle_candidato.py oficial
    const cmdSofle = await p2.evaluate(() => document.getElementById("genSofle").value);
    rec("F12 comando Sofle usa compose_sofle_candidato.py oficial", cmdSofle.includes("generators/compose_sofle_candidato.py"), cmdSofle.split("\n")[1] || "");
    rec("F12 comando Sofle usa argumento --outdir", cmdSofle.includes("--outdir"), cmdSofle.split("\n")[1] || "");
    rec("F12 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F13 — saveEdit() no Sofle valida impl_qmk sem exigir '&' em impl_zmk
  {
    const { c2, p2, msgs2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    // Seleciona Sofle
    await p2.click('button[data-kb="sofle"]');
    await p2.waitForTimeout(200);
    // Clica na primeira tecla da matriz (0,0)
    await p2.click('.key[data-pos="0"]');
    await p2.waitForSelector("#dlgEdit[open]", { timeout: 3000 });
    // Altera apenas o código QMK para um valor customizado e deixa ZMK vazio
    await p2.fill("#editQmk", "KC_MUTE");
    await p2.fill("#editZmk", "");
    await p2.click("#editSave");
    await p2.waitForTimeout(200);
    const dialogClosed = await p2.evaluate(() => !document.getElementById("dlgEdit").hasAttribute("open"));
    rec("F13 saveEdit() no Sofle salva com impl_qmk válido sem exigir & no ZMK", dialogClosed, "dialogClosed=" + dialogClosed);
    rec("F13 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F14 — Diff nativo do Sofle: alteração somente em impl_qmk aparece no runCompare()
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    await p2.click('button[data-kb="sofle"]');
    await p2.waitForTimeout(200);
    // Edita a tecla na posição 0: muda apenas impl_qmk, mantendo impl_zmk igual ao original
    await p2.click('.key[data-pos="0"]');
    await p2.waitForSelector("#dlgEdit[open]", { timeout: 3000 });
    await p2.fill("#editQmk", "KC_CUSTOM_DIFF");
    await p2.click("#editSave");
    await p2.waitForTimeout(200);

    // Abre modal de comparação
    await p2.click("#btnCompare");
    await p2.waitForSelector("#dlgCompare[open]", { timeout: 3000 });
    // Lado A: Candidato L0, Lado B: Referência Sofle L0
    await p2.selectOption("#cmpA", "cand:L0");
    await p2.selectOption("#cmpB", "refs:L0");
    await p2.click("#cmpRun");
    await p2.waitForTimeout(300);

    const cmpText = await p2.evaluate(() => document.getElementById("cmpOut").innerText);
    const hasDiff = cmpText.includes("KC_CUSTOM_DIFF");
    rec("F14 comparador do Sofle reflete alteração somente em impl_qmk no diff", hasDiff, cmpText.split("\n").slice(0, 4).join(" | "));
    rec("F14 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F15 — Auditoria separada Corne e Sofle
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    await p2.click("#btnAudit");
    await p2.waitForSelector("#dlgAudit[open]", { timeout: 3000 });
    const auditText = await p2.evaluate(() => document.getElementById("auditOut").innerText);
    rec("F15 auditoria possui seção CORNE (ZMK)", auditText.includes("CORNE (ZMK): 420 / 420"), auditText.split("\n").slice(0, 3).join(" | "));
    rec("F15 auditoria possui seção SOFLE (Vial/QMK)", auditText.includes("SOFLE (Vial/QMK): 580 / 580"), auditText.split("\n").slice(4, 7).join(" | "));
    rec("F15 auditoria identifica placeholders claramente", auditText.includes("Placeholders identificados"), auditText.split("\n").slice(8, 12).join(" | "));
    rec("F16 auditoria de acessibilidade de camadas presente", auditText.includes("AUDITORIA DE ACESSIBILIDADE E GRAFO DE CAMADAS"), auditText.split("\n").slice(12, 16).join(" | "));
    rec("F15 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F17 — Zoom do Teclado
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });
    const zInitial = await p2.evaluate(() => document.getElementById("zoomLevelText").innerText);
    rec("F17 zoom inicial 100%", zInitial === "100%", "inicial=" + zInitial);

    await p2.click("#btnZoomIn");
    const zIn = await p2.evaluate(() => {
      return {
        txt: document.getElementById("zoomLevelText").innerText,
        prop: document.documentElement.style.getPropertyValue("--board-zoom")
      };
    });
    rec("F17 botão Zoom + amplia escala", zIn.txt === "115%" && zIn.prop === "1.15", "txt=" + zIn.txt + " prop=" + zIn.prop);

    await p2.click("#btnZoomReset");
    const zReset = await p2.evaluate(() => document.getElementById("zoomLevelText").innerText);
    rec("F17 botão 100% reseta escala", zReset === "100%", "reset=" + zReset);

    await p2.click("#btnZoomOut");
    const zOut = await p2.evaluate(() => document.getElementById("zoomLevelText").innerText);
    rec("F17 botão Zoom - reduz escala", zOut === "85%", "out=" + zOut);

    rec("F17 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F18 — Copiar / Colar e Mover / Trocar Teclas
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });

    // Seleciona Sofle
    await p2.click("button[data-kb=\"sofle\"]");

    // 1. Testa Copiar e Colar via modal de edição
    const k0 = await p2.waitForSelector(".key[data-pos=\"0\"]");
    await k0.click();
    await p2.waitForSelector("#dlgEdit[open]", { timeout: 3000 });
    const origLabel0 = await p2.inputValue("#editLabel");

    await p2.click("#btnCopyKey");
    const copyFb = await p2.evaluate(() => document.getElementById("copyKeyFeedback").innerText);
    const clipDisp = await p2.evaluate(() => {
      const p = document.getElementById("clipboardPill");
      const l = document.getElementById("clipKeyLabel");
      return { disp: p.style.display, txt: l.innerText };
    });
    rec("F18 copiar tecla registra na barra e ativa feedback", copyFb.includes("Copiada") && clipDisp.disp !== "none" && clipDisp.txt.includes(origLabel0), "copyFb=" + copyFb + " clip=" + clipDisp.txt);

    await p2.click("#editCancel");
    await p2.waitForSelector("#dlgEdit", { state: "hidden" });

    // Abre tecla 1 e cola
    const k1 = await p2.waitForSelector(".key[data-pos=\"1\"]");
    await k1.click();
    await p2.waitForSelector("#dlgEdit[open]", { timeout: 3000 });
    const origLabel1 = await p2.inputValue("#editLabel");
    await p2.click("#btnPasteKey");
    const pastedLabel = await p2.inputValue("#editLabel");
    rec("F18 colar tecla transfere rótulo copiado para formulário", pastedLabel === origLabel0 && origLabel0 !== origLabel1, "antes=" + origLabel1 + " colado=" + pastedLabel);
    await p2.click("#editCancel");
    await p2.waitForSelector("#dlgEdit", { state: "hidden" });

    // 2. Testa Mover / Trocar teclas na camada atual (Swap Current)
    await p2.click("#btnOpenMoveKey");
    await p2.waitForSelector("#dlgMoveKey[open]", { timeout: 3000 });
    await p2.selectOption("#moveKeySrc", "0");
    await p2.selectOption("#moveKeyDest", "1");
    await p2.selectOption("#moveKeyMode", "swap");
    await p2.selectOption("#moveKeyScope", "current");
    await p2.click("#moveKeyExec");
    await p2.waitForSelector("#dlgMoveKey", { state: "hidden" });

    // Confere que pos 0 e pos 1 inverteram os rótulos na L0
    const lbl0AfterSwap = await p2.evaluate(() => document.querySelector(".key[data-pos=\"0\"] .lbl").innerText);
    const lbl1AfterSwap = await p2.evaluate(() => document.querySelector(".key[data-pos=\"1\"] .lbl").innerText);
    rec("F18 troca (Swap) na camada atual inverte posições 0 e 1", lbl0AfterSwap === origLabel1 && lbl1AfterSwap === origLabel0, "pos0=" + lbl0AfterSwap + " pos1=" + lbl1AfterSwap);

    // 3. Testa Mover / Trocar em TODAS as camadas (Scope All)
    // Dedões 48 e 49: pega rótulos na L0 e L1 antes
    const d48L0Pre = await p2.evaluate(() => document.querySelector(".key[data-pos=\"48\"] .lbl").innerText);
    const d49L0Pre = await p2.evaluate(() => document.querySelector(".key[data-pos=\"49\"] .lbl").innerText);
    await p2.click(".tab[data-layer=\"L1\"]");
    const d48L1Pre = await p2.evaluate(() => document.querySelector(".key[data-pos=\"48\"] .lbl").innerText);
    const d49L1Pre = await p2.evaluate(() => document.querySelector(".key[data-pos=\"49\"] .lbl").innerText);

    await p2.click("#btnOpenMoveKey");
    await p2.waitForSelector("#dlgMoveKey[open]", { timeout: 3000 });
    await p2.selectOption("#moveKeySrc", "48");
    await p2.selectOption("#moveKeyDest", "49");
    await p2.selectOption("#moveKeyMode", "swap");
    await p2.selectOption("#moveKeyScope", "all");
    await p2.click("#moveKeyExec");
    await p2.waitForSelector("#dlgMoveKey", { state: "hidden" });

    // Confere na L1 atual e na L0 que ambos inverteram
    const d48L1Pos = await p2.evaluate(() => document.querySelector(".key[data-pos=\"48\"] .lbl").innerText);
    const d49L1Pos = await p2.evaluate(() => document.querySelector(".key[data-pos=\"49\"] .lbl").innerText);
    await p2.click(".tab[data-layer=\"L0\"]");
    const d48L0Pos = await p2.evaluate(() => document.querySelector(".key[data-pos=\"48\"] .lbl").innerText);
    const d49L0Pos = await p2.evaluate(() => document.querySelector(".key[data-pos=\"49\"] .lbl").innerText);

    rec("F18 troca (Swap) em TODAS as camadas inverte em L0 e L1",
      d48L0Pos === d49L0Pre && d49L0Pos === d48L0Pre && d48L1Pos === d49L1Pre && d49L1Pos === d48L1Pre,
      "L0: " + d48L0Pre + "/" + d49L0Pre + "->" + d48L0Pos + "/" + d49L0Pos + " | L1: " + d48L1Pre + "/" + d49L1Pre + "->" + d48L1Pos + "/" + d49L1Pos
    );

    rec("F18 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F19 — Consolidação v18 (Perfis Corne Simples 7 camadas + Mapa antigo + Sofle)
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });

    // 1. Testa perfil Corne Simples (7 camadas)
    await p2.click('button[data-profile="simple"]');
    await p2.waitForTimeout(200);
    const tabsSimple = await p2.evaluate(() => [...document.querySelectorAll("#layerTabs .tab")].map(t => t.innerText));
    rec("F19 Corne Simples exibe exatamente 7 camadas", tabsSimple.length === 7 && tabsSimple[0].includes("BASE"), tabsSimple.join(" | "));

    // 2. Auditoria no perfil Corne Simples
    await p2.click("#btnAudit");
    await p2.waitForSelector("#dlgAudit[open]", { timeout: 3000 });
    const auditSimple = await p2.evaluate(() => document.getElementById("auditOut").innerText);
    rec("F19 auditoria em Corne Simples reconhece perfil independente", auditSimple.includes("PERFIL: Corne Simples"), auditSimple.split("\n")[0]);
    await p2.click("#auditClose");
    await p2.waitForSelector("#dlgAudit", { state: "hidden" });

    // 3. Zoom no Corne Simples
    await p2.click("#btnZoomIn");
    const zoomSimple = await p2.evaluate(() => document.getElementById("zoomLevelText").innerText);
    rec("F19 zoom funcional no Corne Simples", zoomSimple === "115%", "zoom=" + zoomSimple);
    await p2.click("#btnZoomReset");

    // 4. Alterna para Mapa antigo (10 camadas)
    await p2.click('button[data-profile="candidate"]');
    await p2.waitForTimeout(200);
    const tabsCand = await p2.evaluate(() => [...document.querySelectorAll("#layerTabs .tab")].map(t => t.innerText));
    rec("F19 Mapa antigo exibe 10 camadas (L0 a L9)", tabsCand.length === 10, "camadas=" + tabsCand.length);

    // 5. Alterna para Sofle: botão Corne Simples deve ser ocultado
    await p2.click('button[data-kb="sofle"]');
    await p2.waitForTimeout(200);
    const simpleBtnHidden = await p2.evaluate(() => {
      const b = document.querySelector('button[data-profile="simple"]');
      return b ? b.hidden : true;
    });
    rec("F19 botão Corne Simples ocultado ao selecionar Sofle", simpleBtnHidden, "hidden=" + simpleBtnHidden);

    rec("F19 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();
  }

  // F20 — Validações da Revisão 13, Histórico Pre-State, Binding Swap e Mobile/iPhone
  {
    const { c2, p2, perr2 } = await freshPage();
    await p2.goto(url, { waitUntil: "load" });

    // 1. Corne Simples v13 / Revisão 13
    await p2.click('button[data-profile="simple"]');
    await p2.waitForTimeout(150);
    const bodyTxt = await p2.evaluate(() => document.body.innerText);
    rec("F20 Corne Simples v13 identificado no cabeçalho ou perfil", bodyTxt.includes("v13") || bodyTxt.includes("revisão 13"), "v13 text check");

    // 2. Noscript para JavaScript bloqueado
    const hasNoscript = await p2.evaluate(() => {
      const el = document.querySelector("noscript");
      return el && el.innerHTML.includes("JavaScript") && el.innerHTML.includes("Safari");
    });
    rec("F20 aviso noscript para JavaScript bloqueado presente", !!hasNoscript, "noscript presente com orientações Safari/iPhone");

    // 3. Adaptação para tela pequena / iPhone (@media max-width: 768px)
    const hasMobileQuery = await p2.evaluate(() => {
      return [...document.styleSheets].some(sheet => {
        try {
          return [...sheet.cssRules].some(rule => rule.media && rule.media.mediaText.includes("768px"));
        } catch (e) { return false; }
      });
    });
    rec("F20 CSS contém media query adaptativa para iPhone/mobile (max-width: 768px)", hasMobileQuery, "max-width: 768px");

    // 4. Defeito de binding órfão eliminado na troca (Swap) — testado em células isoladas
    const bindingSwapOk = await p2.evaluate(() => {
      const { swapCells } = window.__ksm;
      const k0 = { label: "TEST_A", binding: "&custom_binding_test" };
      const k1 = { label: "TEST_B" };
      swapCells(k0, k1);
      const ok = (k0.binding === undefined) && (k1.binding === "&custom_binding_test");
      return { ok, k0Binding: k0.binding, k1Binding: k1.binding };
    });
    rec("F20 troca de tecla elimina binding órfão no destino", bindingSwapOk.ok, JSON.stringify(bindingSwapOk));

    // 5. Histórico registra estado IMEDIATAMENTE ANTERIOR à troca (Undo / Desfazer)
    const lbl0Before = await p2.evaluate(() => document.querySelector(".key[data-pos=\"0\"] .lbl").innerText);
    const lbl1Before = await p2.evaluate(() => document.querySelector(".key[data-pos=\"1\"] .lbl").innerText);
    await p2.click("#btnOpenMoveKey");
    await p2.waitForSelector("#dlgMoveKey[open]", { timeout: 3000 });
    await p2.selectOption("#moveKeySrc", "0");
    await p2.selectOption("#moveKeyDest", "1");
    await p2.selectOption("#moveKeyMode", "swap");
    await p2.selectOption("#moveKeyScope", "current");
    await p2.click("#moveKeyExec");
    await p2.waitForSelector("#dlgMoveKey", { state: "hidden" });

    // Confere que a troca foi realmente aplicada na UI
    const lbl0Swapped = await p2.evaluate(() => document.querySelector(".key[data-pos=\"0\"] .lbl").innerText);
    const lbl1Swapped = await p2.evaluate(() => document.querySelector(".key[data-pos=\"1\"] .lbl").innerText);
    rec("F20 swap executado na UI altera posições 0 e 1",
      lbl0Swapped === lbl1Before && lbl1Swapped === lbl0Before,
      "esperado 0=" + lbl1Before + " 1=" + lbl0Before + ", obtido 0=" + lbl0Swapped + " 1=" + lbl1Swapped
    );

    // Abre o diálogo de Histórico e confere que o topo é "antes de troca..."
    await p2.click("#btnHistory");
    await p2.waitForSelector("#dlgHistory[open]", { timeout: 3000 });
    const topHistText = await p2.evaluate(() => {
      const firstItem = document.querySelector("#histOut .item .h");
      return firstItem ? firstItem.innerText : "";
    });
    rec("F20 histórico registra snapshot 'antes de troca' pré-mutação", topHistText.includes("antes de troca"), topHistText);

    // Clica em "Restaurar" na primeira versão (pre-state) e ACEITA o diálogo de confirmação deliberadamente
    p2.__acceptNextDialog = true;
    await p2.click("#histOut .item button.primary");
    await p2.waitForTimeout(300);

    // Confere que pos 0 e pos 1 voltaram ao estado original de antes da troca
    const lbl0Restored = await p2.evaluate(() => document.querySelector(".key[data-pos=\"0\"] .lbl").innerText);
    const lbl1Restored = await p2.evaluate(() => document.querySelector(".key[data-pos=\"1\"] .lbl").innerText);
    rec("F20 restaurar histórico desfaz a troca e retorna ao estado pré-mutação",
      lbl0Restored === lbl0Before && lbl1Restored === lbl1Before,
      "antes=" + lbl0Before + "/" + lbl1Before + " restaurado=" + lbl0Restored + "/" + lbl1Restored
    );

    rec("F20 nenhum pageerror", perr2.length === 0, perr2.join(" | "));
    await c2.close();

    // F21: Fluxo completo de falha na inicialização (safeInit) + renderização do aviso + clique real no botão de resgate
    const c3 = await browser.newContext({ acceptDownloads: true });
    const p3 = await c3.newPage();
    const perr3 = [];
    p3.on("pageerror", err => perr3.push(err.message));

    const corruptDraft = '{"broken_draft": [unclosed array without closing';
    await p3.addInitScript((bad) => {
      localStorage.setItem("ksm_v06_draft", bad);
      window.__forceInitError = "Falha simulada na inicialização para teste end-to-end de resgate";
    }, corruptDraft);

    await p3.goto(url, { waitUntil: "domcontentloaded" });

    // Aguarda a renderização real do aviso de erro e do botão de resgate no DOM
    const rescueBtn = await p3.waitForSelector("#btnRescueUserDraft", { timeout: 3000 });
    rec("F21 aviso de falha na inicialização renderiza botão de resgate no DOM", !!rescueBtn, "botão #btnRescueUserDraft visível");

    // Intercepta o evento de download e clica no botão real na interface
    const downloadPromise = p3.waitForEvent("download");
    await p3.click("#btnRescueUserDraft");
    const download = await downloadPromise;

    const downloadedName = download.suggestedFilename();
    const downloadedPath = await download.path();
    const downloadedContent = fs.readFileSync(downloadedPath, "utf8");

    rec("F21 clique real no botão baixa ksm_rascunho_bruto.json com conteúdo íntegro",
      downloadedName === "ksm_rascunho_bruto.json" && downloadedContent === corruptDraft,
      "arquivo=" + downloadedName + " tamanho=" + downloadedContent.length + " B"
    );
    rec("F21 nenhum pageerror não-tratado na falha de inicialização", perr3.length === 0, perr3.join(" | "));
    await c3.close();
  }

  await browser.close();
  try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch (e) { /* ignore */ }
  // espelho de tela
  await pageShot();
  async function pageShot() { /* (snapshot já dispensável; mantido como noop p/ futuros relatórios) */ }
}

(async () => {
  try { await partB(); } catch (e) { rec("Parte B (Playwright) executada", false, e && e.message ? e.message : String(e)); }
  const fails = results.filter(r => !r.ok);
  const summary = {
    html: HTML_PATH,
    total: results.length,
    pass: results.length - fails.length,
    fail: fails.length,
    itens: results,
  };
  console.log(JSON.stringify(summary, null, 2));
  if (OUT_JSON) {
    fs.writeFileSync(OUT_JSON, JSON.stringify(summary, null, 2) + "\n", "utf8");
    console.error("registrado em: " + OUT_JSON);
  }
  process.exit(fails.length ? 1 : 0);
})();
