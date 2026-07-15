const ORIGIN = "https://lostproperty.pcf.npa.go.jp";
const ALLOWED_PATHS = new Set([
  "/ZDSERVFP/SZDSA0101",
  "/ZDSERVFP/SZDSA0101/next",
  "/ZDSERVFP/SZDWA0101",
  "/ZDSERVFP/SZDWA0101/search",
]);

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

function upstreamHeaders(request) {
  const headers = new Headers();
  for (const name of [
    "accept",
    "accept-language",
    "content-type",
    "cookie",
    "user-agent",
  ]) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }
  return headers;
}

export default {
  async fetch(request, env) {
    if (
      !safeEqual(
        request.headers.get("x-otoshimono-proxy-token"),
        env.PORTAL_PROXY_TOKEN,
      )
    ) {
      return new Response("Forbidden", { status: 403 });
    }

    const requestUrl = new URL(request.url);
    if (
      !["GET", "POST"].includes(request.method) ||
      !ALLOWED_PATHS.has(requestUrl.pathname)
    ) {
      return new Response("Not Found", { status: 404 });
    }

    const contentLength = Number(request.headers.get("content-length") || "0");
    if (contentLength > 64 * 1024) {
      return new Response("Payload Too Large", { status: 413 });
    }

    const target = new URL(requestUrl.pathname + requestUrl.search, ORIGIN);
    const upstream = await fetch(target, {
      method: request.method,
      headers: upstreamHeaders(request),
      body: request.method === "POST" ? request.body : undefined,
      redirect: "manual",
    });

    const responseHeaders = new Headers(upstream.headers);
    const location = responseHeaders.get("location");
    if (location) {
      const redirectTarget = new URL(location, target);
      if (redirectTarget.origin === ORIGIN) {
        responseHeaders.set(
          "location",
          new URL(
            redirectTarget.pathname + redirectTarget.search,
            requestUrl.origin,
          ).toString(),
        );
      }
    }
    responseHeaders.set("cache-control", "no-store");
    responseHeaders.set(
      "x-otoshimono-proxy-colo",
      request.headers.get("cf-placement") || request.cf?.colo || "unknown",
    );

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  },
};
