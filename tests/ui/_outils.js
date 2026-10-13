// Outils communs aux tests navigateur (lancés par tests/lancer_tests.sh).
const pw = require(process.env.PW || 'playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8799';
const TMP = process.env.TEST_TMP;
const echecs = [];
const check = (cond, msg) => { console.log((cond ? '  ✓ ' : '  ✗ ') + msg); if (!cond) echecs.push(msg); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
function surveiller(page, erreurs) {
  page.on('pageerror', e => erreurs.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') erreurs.push(m.text()); });
}
async function fin(browser, erreurs) {
  check(erreurs.length === 0, 'aucune erreur JavaScript' + (erreurs.length ? ' : ' + erreurs.join(' | ') : ''));
  await browser.close();
  console.log(echecs.length ? `ÉCHEC : ${echecs.length} problème(s)` : 'OK');
  process.exit(echecs.length ? 1 : 0);
}
module.exports = { pw, BASE, TMP, check, sleep, surveiller, fin };
