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
  "# Findings\n\n**Verified** `capture-1` [source](https://github.com/fastapi/fastapi) [unsafe](javascript:alert)\n\n<img src=x onerror=alert(1)>\n\n- First finding\n- Second finding\n\n| Key | Value |\n| --- | --- |\n| records | 8 |",
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
