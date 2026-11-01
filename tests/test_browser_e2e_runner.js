const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

let pw;
try { pw = require("playwright"); } catch (e) {
  const homedir = require("os").homedir();
  for (const p of [
    path.join(homedir, ".npm/_npx/9833c18b2d85bc59/node_modules/playwright"),
    path.join(homedir, ".npm/_npx/e41f203b7505f1fb/node_modules/playwright")
  ]) {
    try { pw = require(p); break; } catch (e2) {}
  }
}
if (!pw) {
  console.error("Playwright não encontrado (execute: npm install playwright)");
  process.exit(1);
}

async function run() {
  const tmpDir = process.env.TMP_DIR || "/tmp/browser_e2e_test";
  fs.mkdirSync(tmpDir, { recursive: true });

  let browser;
  try {
    browser = await pw.chromium.launch({ channel: "chrome", headless: true });
  } catch (e) {
    browser = await pw.chromium.launch({ headless: true });
  }
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  page.on("dialog", async d => { await d.accept(); });

  const htmlPath = path.resolve(__dirname, "../deliverables/keyboard_split_manager_v06.html");
  await page.goto("file://" + htmlPath);

  // Seleciona Sofle
  await page.click("button[data-kb=\"sofle\"]");

  // 1. Edita tecla da matriz: posição 13 (letra Q na camada L0)
  const key13 = await page.waitForSelector(".key[data-pos=\"13\"]");
  await key13.click();
  await page.waitForSelector("#dlgEdit", { state: "visible" });
  await page.fill("#editQmk", "KC_F21");
  await page.fill("#editLabel", "F21");
  await page.click("#editSave");
  await page.waitForSelector("#dlgEdit", { state: "hidden" });

  // 2. Edita tecla de polegar: posição 50 (dedão central esquerdo (4,2))
  const thumb50 = await page.waitForSelector(".key[data-pos=\"50\"]");
  await thumb50.click();
  await page.waitForSelector("#dlgEdit", { state: "visible" });
  await page.fill("#editQmk", "KC_F23");
  await page.fill("#editLabel", "F23");
  await page.click("#editSave");
  await page.waitForSelector("#dlgEdit", { state: "hidden" });

  // 3. Dispara o download real pelo botão "Baixar JSON"
  const downloadPromise = page.waitForEvent("download");
  await page.click("#btnDownload");
  const download = await downloadPromise;

  const downloadedJson = path.join(tmpDir, "downloaded_from_browser.json");
  await download.saveAs(downloadedJson);
  await browser.close();

  // 4. Executa o gerador passando o arquivo baixado pelo navegador
  const outDir = path.join(tmpDir, "sofle_out");
  fs.mkdirSync(outDir, { recursive: true });
  const genScript = path.resolve(__dirname, "../generators/compose_sofle_candidato.py");
  execSync(`python3 "${genScript}" --dataset "${downloadedJson}" --outdir "${outDir}" --force`);

  // 5. Confere se o candidato C gerado contém tanto a tecla de matriz quanto o polegar editado
  const candC = JSON.parse(fs.readFileSync(path.join(outDir, "sofle_candidato_v06_C_conectado.vil"), "utf8"));
  if (candC.layout[0][1][1] !== "KC_F21") {
    console.error(`ERRO MATRIZ: esperado KC_F21 na posição (1,1), obtido ${candC.layout[0][1][1]}`);
    process.exit(1);
  }
  if (candC.layout[0][4][2] !== "KC_F23") {
    console.error(`ERRO POLEGAR: esperado KC_F23 na posição elétrica (4,2), obtido ${candC.layout[0][4][2]}`);
    process.exit(1);
  }
  console.log("OK: Edição via navegador (matriz + polegar) -> download real -> gerador -> candidato C comprovado (KC_F21 em (1,1) e KC_F23 em (4,2))");
}

run().catch(e => { console.error(e); process.exit(1); });
