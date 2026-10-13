// Fiche jeu : lecture romaji automatique et recherche en ligne (Wikidata simulé pendant les tests).
const { pw, BASE, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); surveiller(p, erreurs);
  await p.goto(BASE + '/#/jeux'); await p.waitForSelector('#new');
  await p.click('#new'); await p.waitForSelector('.overlay [name=title]');
  // Romaji lu pendant la frappe du titre original
  await p.fill('.overlay [name=original_title]', 'ときめきメモリアル'); await sleep(800);
  check(await p.inputValue('.overlay [name=romaji]') === 'tokimekimemoriaru', 'romaji lu automatiquement');
  await p.fill('.overlay [name=original_title]', '');  await sleep(600);
  // Recherche en ligne : la fiche choisie remplit les cases vides
  await p.fill('.overlay [name=title]', 'Final Fantasy VII');
  await p.click('.overlay [data-online]'); await p.waitForSelector('.overlay .online-hit');
  check(await p.locator('.overlay .online-hit').count() === 1, 'une fiche proposée (le film est écarté)');
  await p.click('.overlay .online-hit'); await sleep(900);
  check(await p.inputValue('.overlay [name=original_title]') === 'ファイナルファンタジーVII', 'titre japonais repris');
  check(await p.inputValue('.overlay [name=romaji]') === 'fainarufantajī VII', 'puis romaji lu');
  check(await p.inputValue('.overlay [name=publisher]') === 'Square' && await p.inputValue('.overlay [name=year]') === '1997',
    'éditeur et année repris');
  await p.locator('.overlay button[type=submit]').click(); await sleep(900);
  const g = (await (await p.request.get(BASE + '/api/games?q=fainaru')).json()).find(x => x.wikidata);
  check(g && g.wikidata === 'Q100001' && g.series_name === 'Final Fantasy', 'jeu enregistré avec sa fiche Wikidata et sa série');
  // Réglage : désactiver la recherche en ligne fait disparaître le bouton
  await p.goto(BASE + '/#/export'); await p.waitForSelector('#online');
  await p.uncheck('#online'); await sleep(400);
  await p.goto(BASE + '/#/jeux'); await p.waitForSelector('#new'); await p.click('#new'); await p.waitForSelector('.overlay [name=title]'); await sleep(500);
  check(await p.locator('.overlay [data-online]').count() === 0, 'désactivée : plus de bouton de recherche en ligne');
  await p.keyboard.press('Escape');
  await p.request.post(BASE + '/api/reglages', { data: { enligne: true } });
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
