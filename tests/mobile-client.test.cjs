const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('public/mobile/mobile-shell.js','utf8');
async function session(result, failure) {
  const redirects = [], themes = [], calls = [], status = {};
  const context = { window: {}, location: {replace: (url) => redirects.push(url)},
    document: {querySelector: () => status, addEventListener() {}},
    PrevClima: {request: async (path) => { calls.push(path); if (failure) throw failure; return result; }, applyTheme: (user) => themes.push(user)},
  };
  vm.runInNewContext(source,context);
  return {user:await context.window.MobileSession,redirects,themes,calls,status};
}
test('mobile guard uses audience-specific session endpoint and accepts only USER',async () => {
  const user = {role:'USER',name:'Usuário',dark_theme:true};
  const result = await session({user});
  assert.equal(result.user,user); assert.deepEqual(result.calls,['/auth/mobile-session']);
  assert.deepEqual(result.redirects,[]); assert.equal(result.themes[0],user);
  for (const role of ['ADMIN','METEOROLOGIST']) {
    const rejected = await session({user:{role}});
    assert.equal(rejected.user,null); assert.deepEqual(rejected.redirects,['/mobile/']);
  }
});
test('expired mobile session returns to mobile login; network failure stays retryable',async () => {
  const expired = await session(null,Object.assign(new Error('Login'),{status:401}));
  assert.deepEqual(expired.redirects,['/mobile/']);
  const offline = await session(null,Object.assign(new Error('Offline'),{status:0}));
  assert.deepEqual(offline.redirects,[]); assert.match(offline.status.textContent,/conexão/);
});
test('all primary mobile links and account recovery stay in mobile application',() => {
  for (const page of ['inicio','alertas','mapa','perfil']) {
    const html = fs.readFileSync(`public/mobile/${page}.html`,'utf8');
    for (const target of ['inicio','alertas','mapa','perfil']) assert.ok(html.includes(`/mobile/${target}.html`));
    assert.doesNotMatch(html,/href="\/(?:inicio|alertas|mapa|perfil|localizacao|estacoes)\.html/);
    assert.match(html,/mobile-shell\.js/);
  }
  const auth = fs.readFileSync('public/mobile/index.html','utf8');
  assert.match(auth,/\/mobile\/conta\.html#reset/); assert.match(auth,/\/mobile\/conta\.html#verify/);
  assert.match(fs.readFileSync('public/mobile/mobile.js','utf8'),/\/mobile\/conta\.html#verify/);
  const root = fs.readFileSync('public/index.html','utf8');
  assert.match(root,/data-professional="true"/); assert.doesNotMatch(root,/href="\/cadastro\.html"/);
});
