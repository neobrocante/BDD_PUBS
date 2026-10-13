// Affichage : aucune page ne déborde sur téléphone ; pages principales sans erreur ; encadré de protection.
const { pw, BASE, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1360, height: 900 } }); surveiller(p, erreurs);
  for (const r of ['', 'saisie', 'recherche', 'pubs', 'pubs/1', 'jeux', 'jeux/1', 'magazines', 'magazines/1', 'numeros/1', 'catalogue', 'catalogue/1', 'stats', 'listes', 'export', 'projets']) {
    await p.goto(BASE + '/#/' + r); await sleep(500);
    check(!(await p.locator('.error-box').count()), `page « ${r || 'accueil'} » affichée`);
  }
  check(await p.locator('#protection .card').count() === 1, 'encadré « Vos données sont protégées »');
  await p.setViewportSize({ width: 390, height: 844 });
  for (const r of ['saisie', 'recherche', 'pubs', 'jeux', 'magazines', 'export', 'pubs/1', 'numeros/1', 'projets', 'catalogue', 'catalogue/3', 'stats']) {
    await p.goto(BASE + '/#/' + r); await sleep(500);
    const w = await p.evaluate(() => document.documentElement.scrollWidth);
    check(w <= 390, `téléphone : « ${r} » sans débordement horizontal (${w}px)`);
  }
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
