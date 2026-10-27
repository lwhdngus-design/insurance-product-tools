// Browser regression: period/rate tables, exclusions, version and page evidence,
// the original user question, follow-ups, and a deliberately incorrect AI plan.
// Start the sample server or a built static site, then set URL to its index.html.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-proxy-server', '--host-resolver-rules=MAP product-tools.test 127.0.0.1'],
  });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(process.env.URL || 'http://127.0.0.1:8765/index.html');
    await page.waitForFunction(() => typeof DOCS !== 'undefined' && DOCS.length === 82 && document.getElementById('docsProgress').hidden,
      null, { timeout: 180000 });
    const checks = await page.evaluate(async () => {
      let checks = 0;
      const check = (condition, name) => { if (!condition) throw new Error(name); checks++; };
      const applied = '적용이율 기간별 차등', guarantee = '최저보증이율 기간별 차등';
      const cases = [
        ['적용이율: 10년 이내 2%, 10년 초과 3%', true, false],
        ['예정이율\n경과기간 | 10년 이내 | 10년 초과\n이율 | 2.25% | 3.5%', true, false],
        ['보험료 산출에 적용하는 이율: 1~10년 연 2%, 10년 이후 연 3%', true, false],
        ['적용이율: 0년~10년 2%, 10년 초과 3%', true, false],
        ['적 용 이 율: 10 년 이 하 2.00％, 10 년 초 과 3.00％', true, false],
        ['적용이율: 제1보험기간 2%, 제2보험기간 3%', true, false],
        ['적립이율: 보험료 납입기간 중 2%, 납입완료 후 3%', true, false],
        ['최저보증이율: 10년 이내 1%, 10년 초과 0.5%', false, true],
        ['최저보증금리: 5년 미만 1.25%, 5년 이상 0.75%', false, true],
        ['적용이율: 10년 이내 2%, 10년 초과 2%', false, false],
        ['적용이율: 10년 이내 2%, 10년 초과 2%. 유지보너스 3%', false, false],
        ['적용이율: 10년 이내 | 10년 초과 / 2% | 2%. 보너스 3%', false, false],
        ['적용이율: 전 기간 2%. 최저보증이율: 10년 이내 1%, 10년 초과 0.5%', false, true],
        ['적용이율: 10년 이내 2%, 10년 초과 3%. 최저보증이율: 10년 이내 1%, 10년 초과 1%', true, false],
        ['적용이율 2%. 8. 보험금 지급: 10년 이내 50%, 10년 이후 100%', false, false],
        ['사망보험금 10년 이내 50%, 10년 이후 100%', false, false],
        ['연체이율 10년 이내 2%, 10년 초과 3%', false, false],
        ['보험계약대출이율 10년 이내 2%, 10년 초과 3%', false, false],
        ['보험금 지급기일 이후의 적립이율: 1년 이내 2%, 1년 초과 3%', false, false],
        ['적립이율: 청구일 다음날부터 1년 이내 2%, 1년 초과 3%', false, false],
        ['예정이율 2.75% → 2.25%로 개정', false, false],
      ];
      for (const [text, a, g] of cases) {
        check(!!conceptHit(text, applied) === a, 'applied: ' + text);
        check(!!conceptHit(text, guarantee) === g, 'guarantee: ' + text);
      }
      const original = '적용이율을 보험기간별로 별도 적용하는 상품 알려줘. 예를 들어 10년이내 2%, 10년이후 3% 등';
      for (const q of [original, '보험기간에 따라 적용이율이 다른 상품', '예정이율을 경과기간별로 나눠 적용하는 상품',
        '10년 이내와 이후에 금리가 달라지는 종신보험', '적용이율 10년 이내 2%, 10년 초과 3%인 상품', '적용이율이 기간별로 다른 상품 몇 개야?']) {
        const p = rulePlan(q);
        check(p.concept === applied && !p.field && !p.value && !p.text && !p.item, 'question: ' + q);
      }
      check(rulePlan('최저보증이율이 10년 이내와 이후에 다른 상품').concept === guarantee, 'guarantee question');
      for (const q of ['평균 예정이율 알려줘', '예정이율 2.25%인 상품', '사망보험금이 기간별로 다른 상품', '연체이율이 기간별로 다른 상품']) {
        check(!AI_CONCEPTS[rulePlan(q).concept]?.rate, 'ordinary query: ' + q);
      }

      // Synthetic extracted PDF pages; never add company documents to public samples.
      const make = (key, pages, start = '2026-01-01') => ({ id: key, name: key, docType: '사업방법서', start, pages, features: {}, status: '판매중' });
      const docs = [
        make('차등상품', ['적용이율: 10년 이내 2%, 10년 초과 3%']),
        make('보증상품', ['적용이율: 2%. 최저보증이율: 10년 이내 1%, 10년 초과 0.5%']),
        make('동일상품', ['적용이율: 10년 이내 2%, 10년 초과 2%. 보너스 3%']),
        make('이전상품', ['적용이율: 2%']),
        make('연속상품', ['적용이율: 10년 이내 2%', '10년 초과 3%']),
        make('두쪽상품', ['상품 안내', '적용이율: 10년 이내 2%, 10년 초과 3%']),
      ];
      const old = make('이전상품구판', ['적용이율: 10년 이내 1.5%, 10년 초과 2.5%'], '2020-01-01');
      DOCS.splice(0, DOCS.length, ...docs, old);
      CATALOG = docs.map(d => ({ key: d.name, name: d.name, kind: '종신', status: d.name === '연속상품' ? '판매종료' : '판매중',
        feat: {}, versions: [{ start: d.start, docs: [d] }], latest: { start: d.start, docs: [d] } }));
      CATALOG[3].versions.push({ start: old.start, docs: [old] });
      CATALOG[2].feat.F04 = true; // 사망보험금 체증형이지만 이율은 같은 상품
      // Same pages_with protocol as the real local server, including consecutive-page numbers.
      const originalApi = api;
      if (SERVER_MODE) api = async (path, body) => {
        if (path !== 'api/pages_with') return originalApi(path, body);
        const pages = [];
        for (const d of DOCS.filter(d => body.ids.includes(d.id))) d.pages.forEach((text, i) => {
          const matches = t => body.match_any ? body.words.some(w => norm(t).includes(norm(w))) : body.words.every(w => norm(t).includes(norm(w)));
          if (matches(text) || (body.neighbors && d.pages.some((t, j) => Math.abs(i - j) <= 1 && matches(t)))) pages.push({ id: d.id, page: i + 1, text });
        });
        return { pages };
      };
      AI.ok = false; showView('ai');
      const withStep = await executePlan(cleanPlan({ ...rulePlan(original), features: ['체증형'] }));
      check(withStep.total === 0, 'benefit step-up tag cannot substitute for different rates');
      await askAi(original, 'new');
      let turn = document.querySelector('.ai-turn:last-child');
      check(turn.querySelectorAll('tbody tr').length === 4, 'original question result count');
      check(turn.innerText.includes('3%') && turn.innerText.includes('2%'), 'both rates visible');
      check(turn.innerText.includes('이전 판'), 'old version marked');
      check(turn.querySelectorAll('[data-page="2"]').length >= 2, 'page 2 links');
      const row = [...turn.querySelectorAll('tbody tr')].find(r => r.innerText.includes('두쪽상품'));
      check(row.querySelector('td:nth-child(5) a').dataset.page === '2', 'evidence begins on actual page 2');
      await askAi('그 중 판매중인 것만', 'follow');
      turn = document.querySelector('.ai-turn:last-child');
      check(turn.querySelectorAll('tbody tr').length === 3, 'follow-up preserves rate structure');
      await askAi('최저보증이율이 10년 이내와 이후에 다른 상품 알려줘', 'new');
      turn = document.querySelector('.ai-turn:last-child');
      check(turn.querySelectorAll('tbody tr').length === 1 && turn.innerText.includes('보증상품'), 'guarantee separately');
      await askAi('차등상품 적용이율이 보험기간별로 다른지 알려줘', 'new');
      check(document.querySelector('.ai-turn:last-child').innerText.includes('3%'), 'named product uses schedule evidence');

      const originalChat = aiChat;
      AI.ok = true; AI.model = 'fixture'; AI.models = ['fixture']; renderAiStatus(); document.getElementById('aiWrite').checked = false;
      aiChat = async () => JSON.stringify({ action: 'list', concept: '보험금 기간별 차등', field: '예정이율', value: '2%', item: '감액', item_value: '2%', text: '별도 적용' });
      await askAi(original, 'new');
      turn = document.querySelector('.ai-turn:last-child');
      check(turn.querySelectorAll('tbody tr').length === 4, 'incorrect AI numeric/item plan repaired');
      check(AI_HISTORY.at(-1).plan.concept === applied && !AI_HISTORY.at(-1).plan.value, 'AI repaired condition');
      aiChat = originalChat; api = originalApi;
      return checks;
    });
    assert.equal(errors.length, 0, errors.join('; '));
    console.log(`PASS: ${checks} period/rate checks, rendered evidence and AI-plan correction (${process.env.URL || 'local'})`);
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
