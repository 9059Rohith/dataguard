const assert = require("node:assert/strict");
const {
  safeHref,
  selectRecords,
  canonical,
  inlineTokens,
} = require("../dataguard/ui-core.js");
assert.equal(safeHref("javascript:alert(1)"), null);
assert.equal(safeHref("data:text/html,<script>alert(1)</script>"), null);
assert.equal(safeHref("https://user:secret@example.com/path"), null);
assert.equal(
  safeHref("https://github.com/fastapi/fastapi"),
  "https://github.com/fastapi/fastapi",
);
const tokens = inlineTokens(
  "**Evidence** `capture-1` [unsafe](javascript:alert) <img onerror=alert(1)>",
  ["capture-1"],
);
assert.equal(
  tokens.find((token) => token.type === "capture").text,
  "capture-1",
);
assert.equal(
  tokens.some((token) => token.type === "link"),
  false,
);
assert.ok(
  tokens.some((token) => token.type === "text" && token.text.includes("<img")),
);
assert.equal(
  canonical({ license: { name: "MIT", id: 1 }, stars: 4 }),
  canonical({ stars: 4, license: { id: 1, name: "MIT" } }),
);
const records = [
  {
    full_name: "z/repo",
    stargazers_count: 10,
    open_issues_count: 0,
    archived: false,
    license: { name: "MIT" },
  },
  {
    full_name: "a/repo",
    stargazers_count: 20,
    open_issues_count: 3,
    archived: true,
  },
  {
    full_name: "b/repo",
    stargazers_count: null,
    open_issues_count: 1,
    archived: false,
  },
];
assert.deepEqual(
  selectRecords(records, "", "stars").map((x) => x.index),
  [1, 0, 2],
);
assert.deepEqual(
  selectRecords(records, "repo", "repository", "active").map((x) => x.index),
  [2, 0],
);
assert.deepEqual(
  selectRecords(records, "", "issues", "licensed").map((x) => x.index),
  [0],
);
assert.deepEqual(
  selectRecords(records, "a/", "repository").map((x) => x.index),
  [1],
);
console.log(
  "UI core: safe links, Markdown tokens, capture citations, semantic comparison, filters and stable sorting passed.",
);
const { renderMarkdown } = require("../dataguard/ui-core.js");
class Node {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase();
    this.ownerDocument = doc;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this._text = "";
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  replaceChildren(...nodes) {
    this.children = [...nodes];
    this._text = "";
  }
  setAttribute(name, value) {
    this.attributes[name] = value;
  }
  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    return (
      this._text + this.children.map((child) => child.textContent).join("")
    );
  }
}
const doc = {
  createElement(tag) {
    return new Node(tag, doc);
  },
};
const output = doc.createElement("div");
renderMarkdown(
  output,
  "# Findings\n\n**Verified** `capture-1` [source](https://github.com/fastapi/fastapi) [unsafe](javascript:alert)\n\n**`fastapi/fastapi`** has the highest **`stargazers_count`**.\n\n<img src=x onerror=alert(1)>\n\n- First finding\n- Second finding\n\n| Key | Value |\n| --- | --- |\n| records | 8 |",
  ["capture-1"],
);
const descendants = (node) => [node, ...node.children.flatMap(descendants)];
const tree = descendants(output);
assert.equal(
  tree.some((node) => ["SCRIPT", "IMG", "IFRAME"].includes(node.tagName)),
  false,
);
assert.ok(
  tree.some(
    (node) => node.tagName === "STRONG" && node.textContent === "Verified",
  ),
);
assert.ok(
  tree.some(
    (node) =>
      node.tagName === "BUTTON" &&
      node.dataset.action === "details" &&
      node.dataset.id === "capture-1",
  ),
);
assert.ok(tree.some((node) => node.tagName === "TABLE"));
for (const value of ["fastapi/fastapi", "stargazers_count"]) {
  assert.ok(
    tree.some(
      (node) =>
        node.tagName === "STRONG" &&
        node.children.some(
          (child) => child.tagName === "CODE" && child.textContent === value,
        ),
    ),
  );
}
assert.equal(output.textContent.includes("`fastapi/fastapi`"), false);
assert.ok(output.textContent.includes("<img src=x onerror=alert(1)>"));
assert.ok(
  tree
    .filter((node) => node.tagName === "A")
    .every((node) => node.href.startsWith("https:")),
);
assert.ok(
  canonical(JSON.parse('{"__proto__":{"polluted":true}}')).includes(
    "__proto__",
  ),
);
assert.equal({}.polluted, undefined);
console.log(
  "Safe DOM Markdown: headings, bold, source buttons, tables, rejected active HTML and unsafe links passed.",
);
const css = require("node:fs").readFileSync(
  require("node:path").join(__dirname, "../dataguard/console.css"),
  "utf8",
);
const luminance = (hex) => {
  const channels = [1, 3, 5]
    .map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return channels.reduce(
    (sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index],
    0,
  );
};
for (const selector of [
  ".sub",
  ".rail-facts dt",
  ".source-note",
  ".form-hint",
  ".check-row small",
  ".capture-meta",
  ".evidence-list dt",
  ".mini-label",
  ".public-limits",
  ".data-notice",
  ".answer-provenance",
  ".tool-args",
  ".tool-result p",
  ".connection-card dt",
  ".settings-row p",
  ".drawer-kicker",
  ".record-stat-grid span",
]) {
  const rule = css.slice(css.indexOf(selector + " {")).split("}")[0];
  const color = rule.match(/(?:^|[;\s])color:\s*(#[0-9a-f]{6})/)[1];
  assert.ok(
    (luminance("#f6f3e9") + 0.05) / (luminance(color) + 0.05) >= 4.5,
    selector + " has sufficient small-text contrast on ivory",
  );
}
assert.match(css, /\.dialog-close\s*\{\s*min-width: 44px;\s*min-height: 44px;/);
assert.match(css, /\.mobile-menu\s*\{\s*min-width: 44px;\s*min-height: 44px;/);
assert.match(
  css,
  /\.sr-only\s*\{\s*position: absolute !important;\s*left: 0;\s*top: 0;/,
);
console.log("Small-text contrast and mobile/menu close target checks passed.");
