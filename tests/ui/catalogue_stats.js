// Catalogue (numéros possédés / manquants), statistiques, dates en texte libre (lots 2 et 3).
const { pw, BASE, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); surveiller(p, erreurs);

  // Catalogue : liste des magazines avec complétude
  await p.goto(BASE + '/#/catalogue'); await p.waitForSelector('#list tr[data-id]');
  check(await p.locator('#list .progress').count() >= 3, 'catalogue : une jauge de complétude par magazine');
  await p.locator('#list tr[data-id]', { hasText: 'Sega Saturn Magazine' }).click();
  await p.waitForSelector('.num-grid');
  const avant = await p.locator('.num-chip.own').count();
  // Générer jusqu'à 15, puis marquer le n°15 possédé d'un clic
  await p.fill('#gen [name=a]', '15'); await p.click('#gen button[type=submit]'); await sleep(700);
  check(await p.locator('.num-chip').count() >= 15, 'numéros générés jusqu\'au 15');
  await p.locator('.num-chip', { hasText: /^15$/ }).click(); await sleep(600);
  check(await p.locator('.num-chip.own').count() === avant + 1, 'clic sur un numéro : marqué possédé');
  check(/Il me manque/.test(await p.textContent('.missing-list')), 'liste « Il me manque » affichée');
  await p.click('#seg [data-f="manquants"]'); await sleep(500);
  check(await p.locator('.num-chip.own').count() === 0, 'filtre « Manquants »');

  // Statistiques : regroupement par type de jeu, barres, lien vers la recherche
  await p.goto(BASE + '/#/stats'); await p.waitForSelector('#res table');
  await p.selectOption('[name=par]', 'genre'); await sleep(600);
  const rpg = p.locator('#res tbody tr', { hasText: 'RPG' });
  check(await rpg.count() === 1 && await rpg.locator('.hbar').count() === 1, 'statistiques par type de jeu, avec barre');
  await p.selectOption('[name=mesure]', 'pages'); await sleep(500);
  check(/Pages de pub/.test(await p.textContent('#res th.bar-col')), 'barres en pages de pub');
  await rpg.locator('a').click(); await sleep(700);
  check(/#\/recherche\?.*genre=RPG/.test(p.url()) && (await p.inputValue('[name=genre]')) === 'RPG', 'clic sur un groupe : recherche filtrée');

  // Dates en texte libre : fiche d'un numéro
  await p.goto(BASE + '/#/magazines'); await p.locator('table.data tr[data-id]', { hasText: 'Weekly Famitsu' }).click();
  await p.waitForSelector('#issues tr[data-id]'); await p.locator('#issues tr[data-id]').first().click(); await p.waitForSelector('#apps');
  await p.click('#edit'); await p.waitForSelector('.overlay');
  const date = p.locator('.overlay label', { hasText: 'Date de parution' }).locator('input');
  await date.fill('8 et 15 avril 1997'); await p.locator('.overlay button[type=submit]').click();
  await p.waitForSelector('.overlay', { state: 'detached' }); await sleep(700);
  const sub = await p.textContent('.page-head .sub');
  check(/8 et 15 avril 1997/.test(sub), 'date « 8 et 15 avril 1997 » acceptée et affichée telle quelle'
    + (/8 et 15/.test(sub) ? '' : ` (${sub.replace(/\s+/g, ' ')} | ${await p.locator('.overlay .form-error').allTextContents()})`));
  await p.click('#edit'); await p.waitForSelector('.overlay');
  const nErr = erreurs.length;
  await date.fill('bientôt'); await p.locator('.overlay button[type=submit]').click(); await sleep(500);
  check(/année introuvable/.test(await p.textContent('.overlay .form-error')), 'date sans année : message clair');
  erreurs.splice(nErr, erreurs.length - nErr, ...erreurs.slice(nErr).filter(e => !/status of 400/.test(e))); // refus attendu
  await p.keyboard.press('Escape');
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
