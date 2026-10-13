// Saisie rapide : jeu -> miniatures -> pub, création de jeu/pub, clavier, téléphone (tactile + clavier Android).
const { pw, BASE, TMP, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1360, height: 950 } }); surveiller(p, erreurs);
  await p.goto(BASE + '/#/saisie'); await p.waitForSelector('#f-mag input');
  await p.fill('#f-mag input', 'dengeki'); await p.keyboard.press('Enter');
  await p.fill('#f-num', '41'); await sleep(500);
  // jeu inconnu -> « Nouveau jeu » -> la fenêtre « Nouvelle pub » s'ouvre d'elle-même
  await p.click('#f-game input'); await p.keyboard.type('Xenogears'); await sleep(250);
  await p.click('#f-game .combo-list:not([hidden]) li.create'); await sleep(400);
  check(await p.locator('.overlay').last().locator('h2').textContent() === 'Nouveau jeu', 'fenêtre « Nouveau jeu »');
  await p.locator('.overlay').last().locator('button[type=submit]').click(); await sleep(700);
  const am = p.locator('.overlay').last();
  check(await am.locator('h2').textContent() === 'Nouvelle pub', 'puis « Nouvelle pub » automatiquement');
  await am.locator('.chip', { hasText: /^PlayStation$/ }).click();
  await am.locator('.picker input[type=search]').fill('saturn'); await am.locator('.chip', { hasText: 'Sega Saturn' }).click();
  await am.locator('input[placeholder^="Ce qui distingue"]').fill('Fei et le Gear');
  await am.locator('input[type=file]').setInputFiles(TMP + '/image_bleue.png'); await sleep(300);
  await am.locator('button[type=submit]').click(); await sleep(900);
  check((await p.locator('#ad-grid .ad-tile.sel .t').allTextContents())[0] === 'Fei et le Gear', 'nouvelle pub sélectionnée dans la grille');
  await p.fill('#f-page', '5'); await p.click('#entry button[type=submit]'); await sleep(900);
  check(await p.locator('#in-issue tbody tr').count() === 1, 'parution enregistrée dans le numéro');
  // au clavier : « fin » -> Entrée -> Tab -> Entrée (miniature) -> page -> Entrée
  await p.click('#f-game input'); await p.keyboard.type('fin'); await sleep(250);
  check((await p.locator('#f-game .combo-list li[data-i="0"]').textContent()).startsWith('Final Fantasy VII'), 'titres qui commencent par la saisie en premier');
  await p.keyboard.press('Enter'); await sleep(400);
  await p.keyboard.press('Tab'); await p.keyboard.press('Enter'); await sleep(200);
  check(await p.evaluate(() => document.activeElement.id) === 'f-page', 'après le choix de la miniature, curseur sur « Page »');
  await p.keyboard.type('12'); await p.keyboard.press('Enter'); await sleep(900);
  check(await p.locator('#in-issue tbody tr').count() === 2, 'enchaînement au clavier enregistré');
  await p.click('#f-game input'); await p.keyboard.type('biohazard'); await sleep(250); await p.keyboard.press('Enter'); await sleep(300);
  await p.click('#entry button[type=submit]'); await sleep(300);
  check((await p.textContent('#f-err')).includes('miniatures'), 'message clair si la pub n\'est pas choisie');
  await p.close();

  // téléphone : tactile + texte « renvoyé » par le clavier Android après création d'un jeu
  const ctx = await b.newContext({ ...pw.devices['Pixel 7'] });
  const m = await ctx.newPage(); surveiller(m, erreurs);
  await m.goto(BASE + '/#/saisie'); await m.waitForSelector('#f-game input'); await sleep(400);
  await m.tap('#f-mag input'); await m.keyboard.type('weekly'); await sleep(300);
  await m.tap('#f-mag .combo-list li[data-i="0"]'); await sleep(200);
  await m.tap('#f-num'); await m.keyboard.type('888'); await sleep(600);
  await m.tap('#f-game input'); await m.keyboard.type('Chrono Trigger'); await sleep(300);
  await m.tap('#f-game .combo-list:not([hidden]) li.create'); await sleep(600);
  await m.locator('.overlay').last().locator('button[type=submit]').tap(); await sleep(800); // jeu créé
  const adModal = m.locator('.overlay').last();
  const gameInput = adModal.locator('.combo input').first();
  await gameInput.evaluate(i => i.dispatchEvent(new Event('input', { bubbles: true }))); await sleep(300); // clavier Android
  await adModal.locator('button[type=submit]').tap(); await sleep(900);
  check(await m.locator('.overlay').count() === 0, 'pas de boucle « Jeu obligatoire » (clavier Android)');
  await m.tap('#f-page'); await m.keyboard.type('33');
  await m.tap('#entry button[type=submit]'); await sleep(900);
  check(await m.locator('#in-issue tbody tr').count() === 1, 'téléphone : parution enregistrée');
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
