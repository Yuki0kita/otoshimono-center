/* 日本珍拾得物センター フィード描画 */

const FEATURED_THRESHOLD = 40;
const FEATURED_COUNT = 5;
const PAGE_SIZE = 30;

const state = {
  items: [],
  pref: "",
  shown: 0,
};

/** 官製の乾いた文体で1件分の本文を組み立てる */
function officialSentence(item) {
  const when = item.found_date === "不明" || !item.found_date
    ? "拾得日不明"
    : `${formatDate(item.found_date)}ごろ`;
  // 市区町村は都道府県名を含む（例: 東京都千代田区）ため重ねない
  const area = item.city !== "不詳" && item.city ? item.city : item.pref;
  const spot = item.place && item.place !== "不明／その他" ? item.place : "";
  const where = [area, spot].filter(Boolean).join("の") || "場所不詳";
  let text = `${when}、${where}で「${item.name}」が拾われました。`;
  if (item.features) text += `特徴は${item.features}。`;
  if (item.contents) {
    const all = item.contents.split("、");
    const listed = all.slice(0, 5).join("、");
    const rest = all.length > 5 ? `ほか${all.length - 5}点` : "";
    text += `あわせて${listed}${rest}が確認されています。`;
  }
  if (item.expiry_date) text += `保管期限は${formatDate(item.expiry_date)}です。`;
  return text;
}

function formatDate(ymd) {
  const [y, m, d] = ymd.split("/").map(Number);
  if (!y || !m || !d) return ymd;
  return `${m}月${d}日`;
}

function shareUrl(item) {
  const text = `【拾得物】${officialSentence(item)} #日本珍拾得物センター`;
  const url = location.origin + location.pathname;
  return `https://x.com/intent/post?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
}

function renderCard(item) {
  const card = document.createElement("article");
  card.className = "item-card";

  const meta = document.createElement("p");
  meta.className = "item-meta";
  meta.textContent = [
    item.found_date === "不明" ? "拾得日不明" : item.found_date,
    item.pref || "保管場所（施設）",
    item.category,
  ].filter(Boolean).join(" ・ ");

  const name = document.createElement("h3");
  name.className = "item-name";
  name.textContent = item.name;

  const body = document.createElement("p");
  body.className = "item-body";
  body.textContent = officialSentence(item);

  const contact = document.createElement("p");
  contact.className = "item-contact";
  contact.textContent = `問い合わせ先: ${item.contact}（番号 ${item.ref_no}）`;

  const actions = document.createElement("div");
  actions.className = "item-actions";
  const share = document.createElement("a");
  share.href = shareUrl(item);
  share.target = "_blank";
  share.rel = "noopener";
  share.textContent = "Xで共有";
  actions.appendChild(share);

  card.append(meta, name, body, contact, actions);
  return card;
}

function filteredItems() {
  return state.pref
    ? state.items.filter((i) => i.pref === state.pref)
    : state.items;
}

function renderFeatured() {
  const list = document.getElementById("featured-list");
  list.textContent = "";
  const featured = state.items
    .filter((i) => i.score >= FEATURED_THRESHOLD)
    .slice(0, FEATURED_COUNT);
  if (featured.length === 0) {
    list.innerHTML = '<p class="empty-state">現在、注目物件はありません。</p>';
    return;
  }
  featured.forEach((i) => list.appendChild(renderCard(i)));
}

function renderLatest({ reset = false } = {}) {
  const list = document.getElementById("latest-list");
  if (reset) {
    list.textContent = "";
    state.shown = 0;
  }
  const items = filteredItems();
  const next = items.slice(state.shown, state.shown + PAGE_SIZE);
  next.forEach((i) => list.appendChild(renderCard(i)));
  state.shown += next.length;

  if (items.length === 0) {
    list.innerHTML = '<p class="empty-state">該当する物件はありません。</p>';
  }
  document.getElementById("load-more").hidden = state.shown >= items.length;
}

function populatePrefSelect() {
  const select = document.getElementById("pref-select");
  const present = new Set(state.items.map((i) => i.pref).filter(Boolean));
  // payload.prefs は北から南の順（収集側の都道府県コード順）
  const prefs = (state.prefOrder || [...present]).filter((p) => present.has(p));
  prefs.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    select.appendChild(opt);
  });
  select.addEventListener("change", () => {
    state.pref = select.value;
    renderLatest({ reset: true });
  });
}

async function main() {
  let payload;
  try {
    const res = await fetch("data/items.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    payload = await res.json();
  } catch (err) {
    console.error("データの読み込みに失敗しました", err);
    document.getElementById("featured-list").innerHTML =
      '<p class="empty-state">データの読み込みに失敗しました。時間をおいて再度お試しください。</p>';
    document.getElementById("latest-list").textContent = "";
    return;
  }

  state.items = payload.items || [];
  state.prefOrder = payload.prefs || null;
  const updated = document.getElementById("updated-at");
  if (payload.updated_at) {
    updated.textContent = `最終更新: ${new Date(payload.updated_at).toLocaleString("ja-JP")}`;
  }
  populatePrefSelect();
  renderFeatured();
  renderLatest({ reset: true });
  document.getElementById("load-more").addEventListener("click", () => renderLatest());
}

main();
