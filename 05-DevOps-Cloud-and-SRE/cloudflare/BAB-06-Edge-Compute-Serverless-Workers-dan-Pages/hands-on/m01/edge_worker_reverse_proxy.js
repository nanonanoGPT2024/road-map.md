/**
 * Hands-on Lab: Enterprise Edge Reverse Proxy & Streaming HTML Transformer
 * Modul: Bab 06 - Cloudflare Workers & Pages
 * 
 * Implementasi ES Module Cloudflare Worker:
 * - Edge Middleware (Security & Query validation)
 * - Dynamic Routing ke multiple upstream origins
 * - Streaming HTMLRewriter (In-flight DOM modification)
 * - Latency Tracking & Telemetry Header Injection
 */

export default {
  /**
   * Main Fetch Handler
   * @param {Request} request - HTTP Request object
   * @param {Object} env - Environment bindings (KV, Secrets, Variables)
   * @param {Object} ctx - Execution context (ctx.waitUntil, ctx.passThroughOnException)
   * @returns {Promise<Response>}
   */
  async fetch(request, env, ctx) {
    const startTime = performance.now();
    const url = new URL(request.url);

    // =========================================================================
    // 1. CONFIGURATION & CONSTANTS
    // =========================================================================
    const API_ORIGIN = env.API_ORIGIN || "https://dummyjson.com";
    const DOCS_ORIGIN = env.DOCS_ORIGIN || "https://httpbin.org";
    const DEBUG_TOKEN = env.DEBUG_TOKEN || "super-secure-devops-token";

    // =========================================================================
    // 2. EDGE MIDDLEWARE: SECURITY & AUTHENTICATION VALIDATION
    // =========================================================================
    const isDebugRequested = url.searchParams.get("debug") === "true";
    if (isDebugRequested) {
      const providedSecret = request.headers.get("x-debug-secret");
      if (providedSecret !== DEBUG_TOKEN) {
        return new Response(
          JSON.stringify({
            status: "error",
            code: 403,
            message: "Edge Middleware: Forbidden. Invalid or missing X-Debug-Secret header.",
            edge_node: request.cf?.colo || "UNKNOWN"
          }),
          {
            status: 403,
            headers: {
              "Content-Type": "application/json",
              "X-Edge-Security": "FAILED"
            }
          }
        );
      }
    }

    // =========================================================================
    // 3. DYNAMIC ROUTING & PATH RESOLUTION
    // =========================================================================
    let targetOrigin;
    let rewrittenPath = url.pathname;

    if (url.pathname.startsWith("/api/")) {
      targetOrigin = API_ORIGIN;
      // Strip '/api' prefix: /api/products -> /products
      rewrittenPath = url.pathname.replace(/^\/api/, "");
    } else {
      // Default route & /docs route diarahkan ke upstream docs origin
      targetOrigin = DOCS_ORIGIN;
      if (url.pathname === "/" || url.pathname === "/docs" || url.pathname === "/docs/") {
        rewrittenPath = "/html"; // End-point yang mengembalikan HTML statis pada httpbin.org
      }
    }

    const upstreamUrl = new URL(rewrittenPath + url.search, targetOrigin);

    // Bangun upstream proxy request
    const upstreamHeaders = new Headers(request.headers);
    upstreamHeaders.set("Host", upstreamUrl.hostname);
    upstreamHeaders.set("X-Forwarded-Host", url.hostname);
    upstreamHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
    upstreamHeaders.set("X-Edge-Colo", request.cf?.colo || "UNKNOWN");

    const proxyRequest = new Request(upstreamUrl.toString(), {
      method: request.method,
      headers: upstreamHeaders,
      body: ["GET", "HEAD"].includes(request.method) ? null : request.body,
      redirect: "follow"
    });

    // =========================================================================
    // 4. SUBREQUEST EXECUTION & RESILIENCE
    // =========================================================================
    let originResponse;
    const originFetchStart = performance.now();

    try {
      originResponse = await fetch(proxyRequest);
    } catch (err) {
      return new Response(
        JSON.stringify({
          status: "error",
          code: 502,
          message: "Bad Gateway: Failed to establish connection to upstream origin.",
          error_detail: err.message
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" }
        }
      );
    }

    const originFetchDuration = Math.round(performance.now() - originFetchStart);
    const contentType = originResponse.headers.get("content-type") || "";

    // =========================================================================
    // 5. STREAMING TRANSFORMATION (HTMLRewriter)
    // =========================================================================
    if (contentType.includes("text/html")) {
      const edgeColo = request.cf?.colo || "EDGE-LOCAL";
      const clientCountry = request.cf?.country || "XX";

      const rewriter = new HTMLRewriter()
        // Transformasi <title>
        .on("title", {
          element(element) {
            element.setInnerContent("Enterprise Edge Portal - Managed by Cloudflare Workers");
          }
        })
        // Injeksi Top Notification Banner pada pembuka tag <body>
        .on("body", {
          element(element) {
            element.prepend(
              `<div id="edge-banner" style="background: #e11d48; color: #ffffff; padding: 12px; font-weight: bold; text-align: center; font-family: sans-serif; border-bottom: 2px solid #9f1239;">
                [PRODUCTION EDGE GATEWAY ACTIVE] Node: ${edgeColo} | Region: ${clientCountry}
              </div>`,
              { html: true }
            );
          }
        })
        // Modifikasi H1 menjadi H2 baru
        .on("h1", {
          element(element) {
            element.setInnerContent("Enterprise Distributed Edge System", { html: false });
          }
        });

      // Terapkan streaming transformation
      const transformedBody = rewriter.transform(originResponse).body;

      // Bangun Response dengan Header Telemetri
      const mutatedHeaders = new Headers(originResponse.headers);
      mutatedHeaders.set("X-Edge-Origin-Time", `${originFetchDuration}ms`);
      mutatedHeaders.set("X-Edge-Region", edgeColo);
      mutatedHeaders.set("X-Edge-Security", "PASSED");
      mutatedHeaders.set("X-Edge-Transform", "HTMLRewriter-Stream");

      return new Response(transformedBody, {
        status: originResponse.status,
        statusText: originResponse.statusText,
        headers: mutatedHeaders
      });
    }

    // =========================================================================
    // 6. RAW STREAMING PASSTHROUGH WITH TELEMETRY INJECTION (API/JSON/Assets)
    // =========================================================================
    const { readable, writable } = new TransformStream();

    // Pipe response body secara streaming tanpa buffering ke memory heap
    ctx.waitUntil(
      originResponse.body.pipeTo(writable).catch((pipeError) => {
        console.error("Downstream stream pipe failed:", pipeError);
      })
    );

    const clientHeaders = new Headers(originResponse.headers);
    clientHeaders.set("X-Edge-Origin-Time", `${originFetchDuration}ms`);
    clientHeaders.set("X-Edge-Region", request.cf?.colo || "UNKNOWN");
    clientHeaders.set("X-Edge-Security", "PASSED");
    clientHeaders.set("X-Edge-Transform", "Byte-Passthrough-Stream");

    return new Response(readable, {
      status: originResponse.status,
      statusText: originResponse.statusText,
      headers: clientHeaders
    });
  }
};