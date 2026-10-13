// Projets : menu, projet de démonstration, isolement des données, onglet qui garde son projet.
const { pw, BASE, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1360, height: 850 } }); surveiller(p, erreurs);
  await p.goto(BASE + '/#/'); await p.waitForSelector('.proj-btn');
  check((await p.textContent('.proj-btn')).includes('Projet principal'), 'ouverture sur le projet de base');
  await p.click('.proj-btn'); await p.click('.proj-menu a'); await p.waitForSelector('#demo');
  await p.click('#demo'); await p.waitForURL(/\/p\/demo/); await p.waitForSelector('.tiles');
  check((await p.textContent('.proj-btn')).includes('Démo'), 'projet de démonstration créé et ouvert');
  await p.goto(p.url().replace(/#.*/, '#/pubs')); await p.waitForSelector('.ad-card img');
  check(await p.locator('.ad-card img').count() === 5, 'affiches de démo affichées');
  const [np] = await Promise.all([p.context().waitForEvent('page'),
    p.evaluate(() => window.open(location.href.replace(/#.*/, '#/jeux'), '_blank', 'noopener'))]);
  await np.waitForSelector('.proj-btn');
  check((await np.textContent('.proj-btn')).includes('Démo'), 'un nouvel onglet reste sur le même projet');
  await np.close();
  const avant = await p.evaluate(async () => (await (await fetch('/api/dashboard')).json()).counts.appearances);
  await p.goto(p.url().replace(/#.*/, '#/saisie')); await p.waitForSelector('#f-mag input');
  await p.fill('#f-mag input', 'famitsu'); await p.keyboard.press('Enter'); await p.fill('#f-num', '777');
  await p.fill('#f-game input', 'sakura'); await sleep(200); await p.keyboard.press('Enter'); await sleep(400);
  await p.click('#ad-grid .pick'); await p.click('#entry button[type=submit]'); await sleep(800);
  const apres = await p.evaluate(async () => (await (await fetch('/api/dashboard')).json()).counts.appearances);
  check(avant === apres, 'une saisie dans la démo ne touche pas le projet principal');
  await p.click('.proj-btn'); await p.click('.proj-menu button:not(.sel)'); await p.waitForURL(/\/p\/principal\//);
  check((await p.textContent('.proj-btn')).includes('Projet principal'), 'retour au projet principal par le menu');
  // ménage
  await p.evaluate(async () => fetch('/api/projets/demo', { method: 'DELETE' }));
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
