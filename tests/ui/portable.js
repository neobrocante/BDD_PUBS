// Écran de portable 14 pouces (1280×720) et ergonomie (lot 1 de la feuille de route) :
// la saisie tient à l'écran, bouton « ← Retour », modifier une pub sans quitter la page,
// vignette → photo entière, version affichée.
const { pw, BASE, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); surveiller(p, erreurs);

  // Saisie rapide : après avoir choisi la pub, Page et Enregistrer sont à l'écran
  await p.goto(BASE + '/#/saisie'); await p.waitForSelector('#f-mag input');
  await p.fill('#f-mag input', 'weekly'); await p.keyboard.press('Enter');
  await p.fill('#f-num', '421'); await sleep(600);
  await p.fill('#f-game input', 'final'); await sleep(200); await p.keyboard.press('Enter'); await sleep(500);
  await p.click('#ad-grid .pick'); await sleep(300);
  const btn = await p.locator('#entry button[type=submit]').boundingBox();
  check(btn.y >= 0 && btn.y + btn.height <= 720, `portable : « Enregistrer » visible sans défiler (bas à ${Math.round(btn.y + btn.height)}px)`);
  const pg = await p.locator('#f-page').boundingBox();
  check(pg.y >= 0 && pg.y + pg.height <= 720, 'portable : le champ « Page » est à l\'écran');
  check(/v\d/.test(await p.textContent('#version')), 'numéro de version affiché en haut');

  // Fiche d'un numéro : « ✎ pub » modifie la pub sans quitter la page, puis « ← Retour »
  await p.goto(BASE + '/#/magazines'); await p.waitForSelector('table.data tr[data-id]');
  check(await p.locator('table.data th', { hasText: 'Publicités' }).count() >= 1, 'liste des magazines : colonne « Publicités »');
  await p.click('table.data tr[data-id]'); await sleep(400);
  await p.click('table.data tr[data-id]'); await p.waitForSelector('#apps [data-act="editad"]');
  const page = p.url();
  check(await p.locator('.back-btn').count() === 1, 'bouton « ← Retour » sur la fiche du numéro');
  const adId = (await p.locator('#apps tbody tr').first().locator('a[href^="#/pubs/"]').getAttribute('href')).split('/').pop();
  await p.locator('#apps [data-act="editad"]').first().click(); await p.waitForSelector('.overlay');
  await p.locator('.overlay input[type=number]').first().fill('4');
  await p.locator('.overlay button[type=submit]').click(); await sleep(800);
  check(p.url() === page, 'après « ✎ pub » : toujours sur la fiche du numéro');
  const ad = await (await p.request.get(`${BASE}/api/ads/${adId}`)).json();
  check(String(ad.pages) === '4', `nombre de pages de la pub enregistré (${ad.pages})`);
  check(await p.locator('.back-btn').count() === 1, 'bouton « ← Retour » toujours là après la modification');
  await p.click('.back-btn'); await sleep(600);
  check(/#\/magazines\/\d+$/.test(p.url()), '« ← Retour » ramène à la page précédente (' + p.url().split('#')[1] + ')');

  // Vignette d'une pub : clic → photo entière
  await p.goto(BASE + '/#/pubs'); await p.waitForSelector('.ad-card img');
  await p.click('.ad-card img'); await sleep(500);
  check(await p.locator('.lightbox').count() === 1, 'clic sur une vignette : photo entière affichée');
  check(/#\/pubs$/.test(p.url()), 'clic sur la vignette : on reste sur la galerie');
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
