#!/usr/bin/env node
'use strict';
// Lanceur npm de Deepy : trouve Python, prepare un environnement isole (venv), puis lance l'interface.
//   deepy                     interface complete
//   deepy "question"          une reponse puis retour au terminal
//   type log.txt | deepy explique
//   deepy --reprendre         reprend la derniere conversation
//   deepy doctor              diagnostic · deepy update : mise a jour · deepy --version

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const http = require('http');
const { spawnSync, spawn } = require('child_process');

const ICI = path.resolve(__dirname, '..');
const PKG = require(path.join(ICI, 'package.json'));
const REPO = 'marketbuss/deepy';
const IS_WIN = process.platform === 'win32';
const BASE = IS_WIN
  ? path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'Deepy')
  : path.join(os.homedir(), '.deepy');
const VENV = path.join(BASE, 'venv');
const VPY = IS_WIN ? path.join(VENV, 'Scripts', 'python.exe') : path.join(VENV, 'bin', 'python');
const REQ = path.join(ICI, 'requirements.txt');
const V = { ok: '\x1b[32m✓\x1b[0m', ko: '\x1b[31m✗\x1b[0m', av: '\x1b[33m!\x1b[0m', g: '\x1b[90m', z: '\x1b[0m', b: '\x1b[1m' };

const run = (cmd, args, opts = {}) => spawnSync(cmd, args, { encoding: 'utf8', windowsHide: true, ...opts });

// ---------- Python ----------
function trouverPython() {
  const candidats = IS_WIN ? [['py', ['-3']], ['python', []], ['python3', []]] : [['python3', []], ['python', []]];
  for (const [cmd, pre] of candidats) {
    const r = run(cmd, [...pre, '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], { timeout: 15000 });
    const v = (r.stdout || '').trim();
    if (r.status === 0 && /^3\.(\d+)$/.test(v) && Number(v.split('.')[1]) >= 9) return { cmd, pre, version: v };
  }
  return null;
}

function empreinte() {
  return crypto.createHash('sha256').update(fs.readFileSync(REQ)).update(PKG.version).digest('hex');
}

function preparer() {
  const marque = path.join(BASE, 'venv.ok');
  if (fs.existsSync(VPY) && fs.existsSync(marque) && fs.readFileSync(marque, 'utf8') === empreinte()) return true;
  const py = trouverPython();
  if (!py) {
    console.error(`${V.ko} Python 3.9+ introuvable.${IS_WIN ? '\n  Installe-le : winget install -e --id Python.Python.3.12  (puis rouvre le terminal)' : ''}`);
    return false;
  }
  fs.mkdirSync(BASE, { recursive: true });
  console.log(`${V.g}> premier lancement : preparation de l'environnement Python ${py.version}...${V.z}`);
  if (!fs.existsSync(VPY)) {
    const r = run(py.cmd, [...py.pre, '-m', 'venv', VENV], { stdio: 'inherit' });
    if (r.status !== 0) { console.error(`${V.ko} creation du venv impossible`); return false; }
  }
  const r = run(VPY, ['-m', 'pip', 'install', '--disable-pip-version-check', '-q', '--upgrade', '-r', REQ], { stdio: 'inherit' });
  if (r.status !== 0) { console.error(`${V.ko} installation des dependances impossible (connexion internet ?)`); return false; }
  fs.writeFileSync(marque, empreinte());
  return true;
}

// ---------- mise a jour ----------
const plusRecente = (a, b) => {
  const x = a.split('.').map(Number), y = b.split('.').map(Number);
  for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  return false;
};

async function derniereVersion(delai = 2500) {
  try {
    const r = await fetch(`https://raw.githubusercontent.com/${REPO}/main/package.json`, { signal: AbortSignal.timeout(delai) });
    return (await r.json()).version || null;
  } catch { return null; }
}

// verification au plus une fois par jour, sans ralentir le demarrage
async function signalerMaj() {
  const f = path.join(BASE, 'maj.json');
  let etat = {};
  try { etat = JSON.parse(fs.readFileSync(f, 'utf8')); } catch { /* premier passage */ }
  if (Date.now() - (etat.verifie || 0) > 86400000) {
    const v = await derniereVersion();
    if (v) { etat = { verifie: Date.now(), version: v }; fs.mkdirSync(BASE, { recursive: true }); fs.writeFileSync(f, JSON.stringify(etat)); }
  }
  if (etat.version && plusRecente(etat.version, PKG.version))
    console.log(`${V.av} Deepy v${etat.version} est disponible (tu as v${PKG.version}) : ${V.b}deepy update${V.z}`);
}

function mettreAJour() {
  console.log(`${V.g}> npm install -g github:${REPO}${V.z}`);
  const r = spawnSync(`npm install -g github:${REPO}`, { shell: true, stdio: 'inherit' });
  if (r.status === 0) {
    try { fs.unlinkSync(path.join(BASE, 'venv.ok')); } catch { /* deja absent */ }
    console.log(`${V.ok} Deepy mis a jour. Relance : deepy`);
  } else console.error(`${V.ko} echec de la mise a jour (code ${r.status})`);
  return r.status || 0;
}

// ---------- diagnostic ----------
function ollamaTags() {
  return new Promise(res => {
    const req = http.get('http://127.0.0.1:11434/api/tags', { timeout: 3000 }, r => {
      let d = ''; r.on('data', c => { d += c; }); r.on('end', () => { try { res(JSON.parse(d).models || []); } catch { res(null); } });
    });
    req.on('error', () => res(null));
    req.on('timeout', () => { req.destroy(); res(null); });
  });
}

async function doctor() {
  const ligne = (ok, txt, aide) => console.log(`  ${ok === true ? V.ok : ok === false ? V.ko : V.av} ${txt}${aide ? `\n      ${V.g}${aide}${V.z}` : ''}`);
  console.log(`\n${V.b}Deepy v${PKG.version} — diagnostic${V.z}\n`);
  ligne(true, `Node.js ${process.version}`);
  const py = trouverPython();
  ligne(!!py, py ? `Python ${py.version} (${py.cmd})` : 'Python 3.9+ introuvable', py ? '' : 'winget install -e --id Python.Python.3.12');
  const venv = fs.existsSync(VPY);
  ligne(venv, venv ? `environnement isole : ${VENV}` : 'environnement pas encore cree', venv ? '' : 'il sera cree au premier lancement de deepy');
  if (venv) {
    const r = run(VPY, ['-c', 'import rich; print(rich.__version__ if hasattr(rich, "__version__") else "ok")']);
    ligne(r.status === 0, r.status === 0 ? 'dependance rich installee' : 'rich manquant', r.status === 0 ? '' : 'supprime le dossier venv puis relance deepy');
  }
  const ollama = run(IS_WIN ? 'where' : 'which', ['ollama']).status === 0 ||
    (IS_WIN && fs.existsSync(path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama.exe')));
  ligne(ollama, ollama ? 'Ollama installe' : 'Ollama absent', ollama ? '' : 'Deepy le proposera au premier lancement (winget)');
  const modeles = await ollamaTags();
  ligne(modeles !== null, modeles !== null ? `Ollama repond (${modeles.length} modele(s) : ${modeles.map(m => m.name).join(', ') || 'aucun'})` : 'Ollama ne repond pas',
    modeles !== null ? '' : 'lance Ollama (menu Demarrer) ou : ollama serve');
  const data = path.join(process.env.APPDATA || os.homedir(), 'Deepy');
  let conf = {};
  try { conf = JSON.parse(fs.readFileSync(path.join(data, 'config.json'), 'utf8')); } catch { /* pas encore configure */ }
  ligne(conf.modele ? true : null, conf.modele ? `modele choisi : ${conf.modele}` : 'modele pas encore choisi (fait au premier lancement)');
  ligne(true, `securite : ${conf.securite || 'normal'} (commandes dangereuses toujours bloquees)`);
  ligne(process.env.GROQ_API_KEY ? true : null, process.env.GROQ_API_KEY ? 'cle Groq presente (cerveau cloud possible)' : 'pas de cle Groq : 100 % local');
  const git = run('git', ['--version']).status === 0;
  ligne(git ? true : null, git ? 'Git installe (serveur MCP git)' : 'Git absent (serveur MCP git inactif)');
  const v = await derniereVersion(4000);
  ligne(v === null ? null : !plusRecente(v, PKG.version), v === null ? 'verification de mise a jour impossible (hors ligne ?)' :
    plusRecente(v, PKG.version) ? `v${v} disponible` : 'Deepy est a jour', v && plusRecente(v, PKG.version) ? 'deepy update' : '');
  console.log(`\n  ${V.g}donnees : ${data}${V.z}\n`);
}

// ---------- main ----------
(async () => {
  const args = process.argv.slice(2);
  if (args[0] === '--version' || args[0] === '-v') return console.log(PKG.version);
  if (args[0] === 'doctor') return doctor();
  if (args[0] === 'update') return process.exit(mettreAJour());
  if (args[0] === '--help' || args[0] === '-h' || args[0] === 'aide') {
    return console.log(`deepy v${PKG.version}\n\n  deepy                       interface\n  deepy "question"            une reponse\n` +
      `  type f.txt | deepy explique  avec un texte en entree\n  deepy --reprendre           reprend la derniere conversation\n` +
      `  deepy doctor                diagnostic\n  deepy update                mise a jour`);
  }
  if (!preparer()) process.exit(1);
  if (process.stdin.isTTY && !args.length) await signalerMaj();
  const enfant = spawn(VPY, ['-X', 'utf8', path.join(ICI, 'interface.py'), ...args], {
    stdio: 'inherit',
    env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
  });
  ['SIGINT', 'SIGTERM'].forEach(s => process.on(s, () => { /* Ctrl+C : c'est Python qui gere */ }));
  enfant.on('exit', code => process.exit(code ?? 0));
})();
