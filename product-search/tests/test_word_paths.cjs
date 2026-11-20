// Exercise the actual global filename/date rules without browser dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../pdf-docs.js'), 'utf8');
const context = vm.createContext({ assert, norm: s => s.replace(/\s+/g, '').toLowerCase() });
vm.runInContext(source.slice(0, source.indexOf('// ---------- PDF 텍스트 추출')), context);
vm.runInContext(`
  assert.equal(saleDatesOf('원본/2026년 10월/(무)교육보험_사업방법서_20261026_수정3.docx').start, '2026-10-26');
  assert.equal(saleDatesOf('20260101-20261231 신상품/(무)교육보험_약관_20261026.docx').start, '2026-10-26');
  assert.equal(saleDatesOf('원본/2025.10.26/(무)교육보험_약관_20261026.docx').start, '2025-10-26');
  assert.equal(saleDatesOf('원본/2026.10/(무)교육보험_약관_20261026.pdf').start, '2026-10-01');
  for (const suffix of ['사업방법서_20261026_수정3.docx', '약관_20261026_수정3.docx', '산출방법서_20261026_F.docx', '요율확인의뢰서_20261026_사업비변경.docx']) {
    assert.equal(productNameOf('(무)교육보험_' + suffix), '(무)교육보험');
  }
`, context);
console.log('PASS: Word monthly/annual folders, day folders, revision suffixes and unchanged PDF date rules');
