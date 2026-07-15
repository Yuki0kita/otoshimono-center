const ORIGIN = "https://lostproperty.pcf.npa.go.jp";
const REQUEST_INTERVAL_MS = 1500;
const RETRY_BACKOFF_MS = 5000;
const RETRY_ATTEMPTS = 3;
const PAGE_SIZE = 500;
const OVER_LIMIT_TEXT = "500件を超えているため";
const COUNT_PATTERN = /(\d+)件中\d+-\d+件を表示/;

function safeEqual(left, right) {
  if (!left || !right || left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function responseHeaders(request) {
  return {
    "cache-control": "no-store",
    "x-otoshimono-proxy-colo":
      request.headers.get("cf-placement") || request.cf?.colo || "unknown",
  };
}

function absorbCookies(response, cookies) {
  const values = response.headers.getAll("Set-Cookie");
  for (const value of values) {
    const pair = value.split(";", 1)[0];
    const separator = pair.indexOf("=");
    if (separator > 0) {
      cookies.set(pair.slice(0, separator), pair.slice(separator + 1));
    }
  }
}

function cookieHeader(cookies) {
  return [...cookies].map(([name, value]) => `${name}=${value}`).join("; ");
}

async function fetchOrigin(path, options, cookies) {
  let lastError;
  for (let attempt = 1; attempt <= RETRY_ATTEMPTS; attempt += 1) {
    try {
      let target = new URL(path, ORIGIN);
      let method = options.method || "GET";
      let body = options.body;
      for (let redirectCount = 0; redirectCount <= 3; redirectCount += 1) {
        await scheduler.wait(
          redirectCount === 0 && attempt > 1
            ? RETRY_BACKOFF_MS
            : REQUEST_INTERVAL_MS,
        );
        const headers = new Headers({
          accept: "text/html,application/xhtml+xml",
          "accept-language": "ja,en;q=0.5",
          "user-agent": "otoshimono-center/0.1 (personal aggregator; polite crawl)",
        });
        if (body) {
          headers.set("content-type", "application/x-www-form-urlencoded");
        }
        if (cookies.size) {
          headers.set("cookie", cookieHeader(cookies));
        }

        const response = await fetch(target, {
          method,
          headers,
          body,
          redirect: "manual",
          signal: AbortSignal.timeout(30000),
        });
        absorbCookies(response, cookies);
        if (response.ok) {
          return response.text();
        }
        if (response.status >= 300 && response.status < 400) {
          const location = response.headers.get("location");
          if (!location) {
            throw new Error(`upstream redirect without location: ${target}`);
          }
          const next = new URL(location, target);
          if (next.origin !== ORIGIN) {
            throw new Error(`upstream redirected outside portal: ${next.origin}`);
          }
          if (
            response.status === 303 ||
            ([301, 302].includes(response.status) && method === "POST")
          ) {
            method = "GET";
            body = undefined;
          }
          target = next;
          continue;
        }
        lastError = new Error(`upstream returned ${response.status}: ${target}`);
        if (response.status < 500) {
          break;
        }
      }
      if (!lastError) {
        lastError = new Error(`upstream redirect limit exceeded: ${target}`);
      }
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("upstream request failed");
}

function menuForm() {
  return new URLSearchParams({
    menuSelect: "1",
    menuSelectValue: "",
    langCd: "01",
    commonHeaderZoomSize: "100",
  }).toString();
}

function searchForm(payload) {
  const form = new URLSearchParams();
  form.append("ishitsuFromDate", payload.date_from);
  form.append("ishitsuToDate", payload.date_to);
  form.append("initIshitsuToDate", payload.date_to);
  for (const code of payload.pref_codes) {
    form.append("prefValue", code);
  }
  for (const [name, value] of [
    ["_prefValue", "1"],
    ["prefCheck", payload.pref_codes[0]],
    ["_cityCdValue", "1"],
    ["fushoFlg", "true"],
    ["_fushoFlg", "on"],
    ["bashoShuruiValue", ""],
    ["shisetsuNm", ""],
    ["searchMethod", "1"],
    ["bunruiValue", payload.bunrui_code],
    ["goodsTypeValue", ""],
    ["buppinNmValue", ""],
    ["keyword", ""],
    ["keywordEdit", ""],
    ["conditionFlg", "1"],
    ["sortNum", ""],
    ["sortType", ""],
    ["pageTopRecordNum", "0"],
    ["dispCountPerPageSelect", "10,20,100"],
    ["limitNum", "500"],
    ["langCd", "01"],
    ["initFushoFlg", "true"],
    ["initSearchMethod", "1"],
    ["initConditionFlg", "1"],
    ["totalRecordCount", "0"],
    ["commonHeaderZoomSize", "100"],
  ]) {
    form.append(name, value);
  }
  return form.toString();
}

function validPayload(payload) {
  return (
    Array.isArray(payload?.pref_codes) &&
    payload.pref_codes.length > 0 &&
    payload.pref_codes.length <= 47 &&
    payload.pref_codes.every((code) => /^\d{2}$/.test(code)) &&
    /^\d{4}$/.test(payload?.bunrui_code || "") &&
    /^\d{4}\/\d{2}\/\d{2}$/.test(payload?.date_from || "") &&
    /^\d{4}\/\d{2}\/\d{2}$/.test(payload?.date_to || "")
  );
}

async function batchSearch(payload) {
  const cookies = new Map();
  await fetchOrigin("/ZDSERVFP/SZDSA0101", {}, cookies);
  await fetchOrigin(
    "/ZDSERVFP/SZDSA0101/next",
    { method: "POST", body: menuForm() },
    cookies,
  );
  const first = await fetchOrigin(
    "/ZDSERVFP/SZDWA0101/search",
    { method: "POST", body: searchForm(payload) },
    cookies,
  );
  const selectedCategory = new RegExp(
    `value="${payload.bunrui_code}"[^>]*selected`,
  );
  if (!selectedCategory.test(first)) {
    throw new Error("portal did not apply the requested search state");
  }

  const pages = [];
  if (!first.includes(OVER_LIMIT_TEXT)) {
    const count = first.match(COUNT_PATTERN);
    const total = count ? Number(count[1]) : 0;
    if (total > 10) {
      pages.push(
        await fetchOrigin(
          `/ZDSERVFP/SZDWA0101?&gDispCountPerPage=${PAGE_SIZE}` +
            "&gPageTopRecordNum=0&OC_TRANSACTION_TOKEN=null",
          {},
          cookies,
        ),
      );
    }
  }
  return { first, pages };
}

export default {
  async fetch(request, env) {
    const headers = responseHeaders(request);
    if (
      !safeEqual(
        request.headers.get("x-otoshimono-proxy-token"),
        env.PORTAL_PROXY_TOKEN,
      )
    ) {
      return new Response("Forbidden", { status: 403, headers });
    }

    const url = new URL(request.url);
    try {
      if (request.method === "GET" && url.pathname === "/health") {
        await fetchOrigin("/ZDSERVFP/SZDSA0101", {}, new Map());
        return Response.json({ ok: true }, { headers });
      }
      if (request.method === "POST" && url.pathname === "/batch-search") {
        const payload = await request.json();
        if (!validPayload(payload)) {
          return new Response("Bad Request", { status: 400, headers });
        }
        return Response.json(await batchSearch(payload), { headers });
      }
      return new Response("Not Found", { status: 404, headers });
    } catch (error) {
      console.error(error);
      return Response.json(
        { error: "upstream request failed" },
        { status: 502, headers },
      );
    }
  },
};
