// Import d'un fichier CSV depuis la page « Import / Export » : aperçu, colonnes, essai, import.
const fs = require('fs'), path = require('path');
const { pw, BASE, TMP, check, sleep, surveiller, fin } = require('./_outils');
(async () => {
  const fichier = path.join(TMP, 'parutions_ui.csv');
  fs.writeFileSync(fichier, '﻿Revue;N°;Date;Page;Jeu;Plateforme;En vente\r\n'
    + 'Gamest;12;8 et 15 avril 1997;33;Street Fighter Zero 2;Arcade / Sega Saturn;○\r\n'
    + 'Gamest;12;8 et 15 avril 1997;40;Darkstalkers;Arcade;×\r\n');
  const b = await pw.chromium.launch(); const erreurs = [];
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } }); surveiller(p, erreurs);
  await p.goto(BASE + '/#/export'); await p.waitForSelector('#import-card input[type=file]', { state: 'attached' });
  await p.setInputFiles('#import-card input[type=file]', fichier); await p.waitForSelector('#imp-type');
  check(await p.inputValue('#imp-type') === 'parutions', 'type reconnu : parutions');
  check(await p.inputValue('.imp-map select[data-k="magazine"]') === '0', 'colonne « Revue » associée au magazine');
  check(await p.locator('#imp-body table tbody tr').count() === 2, 'aperçu des lignes');
  check(await p.locator('#imp-go').isDisabled(), '« Importer » grisé avant la vérification');
  await p.click('#imp-try'); await p.waitForSelector('.import-report');
  check(/Seront créés/.test(await p.textContent('.import-report')), 'vérification : ce qui sera créé');
  await p.click('#imp-go'); await sleep(800);
  check(/Créés/.test(await p.textContent('.import-report')), 'import effectué');
  const r = await (await p.request.get(BASE + '/api/search?jeu=street')).json();
  check(r.stats.total === 1 && r.items[0].date_label === '8 et 15 avril 1997' && r.items[0].for_sale === 1
    && /Sega Saturn/.test(r.items[0].platform), 'parution importée avec date, plateformes et vente');
  await fin(b, erreurs);
})().catch(e => { console.error('ÉCHEC', e.message.split('\n')[0]); process.exit(1); });
