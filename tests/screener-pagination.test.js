const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const requests = [];
let definition;
const source = fs.readFileSync(
  path.join(__dirname, '../miniprogram/pages/screener/screener.js'), 'utf8',
);
vm.runInNewContext(source, {
  require: () => ({
    searchScreener(query) {
      return new Promise((resolve, reject) => requests.push({ query, resolve, reject }));
    },
  }),
  Page: (page) => { definition = page; },
  wx: { showToast() {}, navigateTo() {} },
});

function makePage() {
  const page = { ...definition, data: JSON.parse(JSON.stringify(definition.data)) };
  page.setData = (update) => Object.assign(page.data, update);
  page.data.conditions = [{ metric: 'roe', operator: '>=', value: 0.1, consecutive_years: 1 }];
  return page;
}

async function settle() {
  await Promise.resolve();
  await Promise.resolve();
}

async function main() {
  const page = makePage();
  page.onSearch();
  assert.equal(requests[0].query.page, 1);
  requests[0].resolve({ data: { items: [{ symbol: '000001' }], total: 2 } });
  await settle();
  assert.equal(page.data.hasMore, true);

  page.onReachBottom();
  page.onReachBottom();
  assert.equal(requests.length, 2, 'repeated bottom events must not duplicate a page');
  assert.equal(requests[1].query.page, 2);
  requests[1].resolve({ data: { items: [{ symbol: '000002' }], total: 2 } });
  await settle();
  assert.equal(page.data.results.length, 2);
  assert.equal(page.data.hasMore, false);
  page.onReachBottom();
  assert.equal(requests.length, 2);

  page.onSearch();
  assert.equal(requests.length, 3);
  page.onToggleLogic();
  assert.equal(page.data.searched, false);
  requests[2].resolve({ data: { items: [{ symbol: 'STALE' }], total: 1 } });
  await settle();
  assert.equal(page.data.results.length, 0, 'old results must be ignored after changing filters');

  page.onSearch();
  requests[3].reject(new Error('network'));
  await settle();
  assert.equal(page.data.error, 'network');
  page.onSearch();
  requests[4].resolve({ data: { items: [{ symbol: '000003' }], total: 1 } });
  await settle();
  assert.equal(page.data.results[0].symbol, '000003');
  assert.equal(page.data.error, '');
  console.log('screener pagination tests passed');
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
