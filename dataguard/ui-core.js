"use strict";
(function (root) {
  const safeHref = (value) => {
    try {
      const url = new URL(String(value));
      return ["https:", "http:"].includes(url.protocol) &&
        !url.username &&
        !url.password
        ? url.href
        : null;
    } catch {
      return null;
    }
  };
  const selectRecords = (
    records,
    query = "",
    sort = "repository",
    filter = "all",
  ) => {
    const needle = query.trim().toLowerCase();
    const numeric = (value) =>
      typeof value === "number" && Number.isFinite(value) ? value : -Infinity;
    return records
      .map((record, index) => ({ record, index }))
      .filter(
        ({ record: r }) =>
          (!needle ||
            [r.full_name, r.description, r.language].some((value) =>
              String(value || "")
                .toLowerCase()
                .includes(needle),
            )) &&
          (filter !== "active" || r.archived === false) &&
          (filter !== "licensed" || Boolean(r.license)) &&
          (filter !== "issues" || numeric(r.open_issues_count) > 0),
      )
      .sort((a, b) => {
        let order = 0;
        if (sort === "stars")
          order =
            numeric(b.record.stargazers_count) -
            numeric(a.record.stargazers_count);
        else if (sort === "issues")
          order =
            numeric(b.record.open_issues_count) -
            numeric(a.record.open_issues_count);
        else if (sort === "updated")
          order =
            (Date.parse(b.record.updated_at) || 0) -
            (Date.parse(a.record.updated_at) || 0);
        else
          order = String(a.record.full_name || "").localeCompare(
            String(b.record.full_name || ""),
          );
        return (Number.isNaN(order) ? 0 : order) || a.index - b.index;
      });
  };
  const canonical = (value) =>
    JSON.stringify(value, (_, item) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? Object.keys(item)
            .sort()
            .reduce(
              (result, key) => ((result[key] = item[key]), result),
              Object.create(null),
            )
        : item,
    );
  const inlineTokens = (text, captureIds = []) => {
    text = String(text);
    const result = [];
    let cursor = 0;
    const regex = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;
    for (const match of String(text).matchAll(regex)) {
      if (match.index > cursor)
        result.push({ type: "text", text: text.slice(cursor, match.index) });
      if (match[1]) result.push({ type: "strong", text: match[1] });
      else if (match[2])
        result.push({
          type: captureIds.includes(match[2]) ? "capture" : "code",
          text: match[2],
        });
      else {
        const href = safeHref(match[4]);
        result.push(
          href
            ? { type: "link", text: match[3], href }
            : { type: "text", text: match[0] },
        );
      }
      cursor = match.index + match[0].length;
    }
    if (cursor < String(text).length)
      result.push({ type: "text", text: String(text).slice(cursor) });
    return result;
  };
  const renderMarkdown = (container, text, captureIds = []) => {
    const doc = container.ownerDocument;
    container.replaceChildren();
    const inline = (target, value) => {
      for (const token of inlineTokens(String(value), captureIds)) {
        const tag = {
          text: "span",
          strong: "strong",
          code: "code",
          capture: "button",
          link: "a",
        }[token.type];
        const node = doc.createElement(tag);
        if (token.type === "strong") inline(node, token.text);
        else node.textContent = token.text;
        if (token.type === "capture") {
          node.type = "button";
          node.className = "citation-inline";
          node.dataset.action = "details";
          node.dataset.id = token.text;
          node.setAttribute(
            "aria-label",
            "Inspect cited capture " + token.text,
          );
        }
        if (token.type === "link") {
          node.href = token.href;
          node.target = "_blank";
          node.rel = "noopener noreferrer";
        }
        target.append(node);
      }
    };
    const lines = String(text).replace(/\r/g, "").split("\n");
    let paragraph = [],
      list = null,
      pre = null;
    const flush = () => {
      if (paragraph.length) {
        const p = doc.createElement("p");
        inline(p, paragraph.join(" "));
        container.append(p);
        paragraph = [];
      }
      list = null;
    };
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (/^\s*```/.test(line)) {
        flush();
        if (pre) {
          pre = null;
        } else {
          pre = doc.createElement("pre");
          pre.className = "answer-code";
          container.append(pre);
        }
        continue;
      }
      if (pre) {
        pre.textContent += (pre.textContent ? "\n" : "") + line;
        continue;
      }
      if (!line.trim()) {
        flush();
        continue;
      }
      const heading = line.match(/^\s{0,3}(#{1,4})\s+(.+)$/);
      if (heading) {
        flush();
        const h = doc.createElement(heading[1].length < 3 ? "h3" : "h4");
        inline(h, heading[2]);
        container.append(h);
        continue;
      }
      if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
        flush();
        container.append(doc.createElement("hr"));
        continue;
      }
      if (
        line.includes("|") &&
        i + 1 < lines.length &&
        /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])
      ) {
        flush();
        const wrap = doc.createElement("div");
        wrap.className = "table-wrap";
        const table = doc.createElement("table");
        const thead = doc.createElement("thead");
        const tbody = doc.createElement("tbody");
        const cells = (value) =>
          value
            .trim()
            .replace(/^\||\|$/g, "")
            .split("|")
            .map((v) => v.trim());
        const row = (values, header) => {
          const tr = doc.createElement("tr");
          for (const value of values) {
            const cell = doc.createElement(header ? "th" : "td");
            inline(cell, value);
            tr.append(cell);
          }
          return tr;
        };
        thead.append(row(cells(line), true));
        i += 2;
        while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
          tbody.append(row(cells(lines[i]), false));
          i++;
        }
        i--;
        table.append(thead, tbody);
        wrap.append(table);
        container.append(wrap);
        continue;
      }
      const item = line.match(/^\s*(?:([-*+])|(\d+)[.)])\s+(.+)$/);
      if (item) {
        if (paragraph.length) flush();
        const tag = item[2] ? "ol" : "ul";
        if (!list || list.tagName.toLowerCase() !== tag) {
          list = doc.createElement(tag);
          container.append(list);
        }
        const li = doc.createElement("li");
        inline(li, item[3]);
        list.append(li);
        continue;
      }
      if (/^\s*>/.test(line)) {
        flush();
        const quote = doc.createElement("blockquote");
        inline(quote, line.replace(/^\s*>\s?/, ""));
        container.append(quote);
        continue;
      }
      if (list) list = null;
      paragraph.push(line.trim());
    }
    flush();
  };
  const api = {
    safeHref,
    selectRecords,
    canonical,
    inlineTokens,
    renderMarkdown,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.DataGuardUI = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
