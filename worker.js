/**
 * Cloudflare Worker — Proxy reverso para o backend Flask (Render)
 *
 * Todas as requisições são encaminhadas ao BACKEND_URL.
 * Defina a variável de ambiente BACKEND_URL no dashboard do Cloudflare Workers
 * com o URL do serviço Render (ex: https://myfinance.onrender.com)
 */

export default {
  async fetch(request, env) {
    const backendUrl = (env.BACKEND_URL || '').trim();

    if (!backendUrl) {
      return new Response('BACKEND_URL não configurada.', { status: 500 });
    }

    const url = new URL(request.url);
    const targetUrl = backendUrl.replace(/\/$/, '') + url.pathname + url.search;

    const proxyRequest = new Request(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      redirect: 'follow',
    });

    try {
      const response = await fetch(proxyRequest);
      const newHeaders = new Headers(response.headers);
      // Permite cookies de sessão cross-origin se necessário
      newHeaders.set('Access-Control-Allow-Origin', url.origin);
      newHeaders.set('Access-Control-Allow-Credentials', 'true');

      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers: newHeaders,
      });
    } catch (err) {
      return new Response('Erro ao contactar o backend: ' + err.message, { status: 502 });
    }
  },
};
