// Proxy mínimo pro OpenSky Network, rodando na rede da Cloudflare.
//
// Por que existe: o banco (Supabase) e as Edge Functions do Supabase não
// conseguem alcançar opensky-network.org nem auth.opensky-network.org — as
// conexões ficam penduradas até estourar timeout, em qualquer um dos dois
// caminhos de rede do Supabase (confirmado em teste direto). A rede da
// Cloudflare enxerga o OpenSky normalmente, então este proxy só repassa a
// chamada: quem chama é o Supabase, quem responde de verdade é o OpenSky.
//
// Só encaminha para os dois hosts do OpenSky (states/all e o token OAuth2),
// nada além disso, e exige um segredo compartilhado pra não virar um proxy
// aberto pra qualquer site.

const PROXY_SECRET = 'gq_GeT2MpxiCKmKEWbJlQYsgB5T7oyIbJApWIOoeBTE';

const DESTINOS = {
  states: 'https://opensky-network.org/api/states/all',
  token: 'https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token',
};

export async function onRequest(context) {
  const { request, params } = context;
  const rota = Array.isArray(params.path) ? params.path[0] : params.path;

  if (request.headers.get('X-Proxy-Key') !== PROXY_SECRET) {
    return new Response('Forbidden', { status: 403 });
  }

  const destinoBase = DESTINOS[rota];
  if (!destinoBase) {
    return new Response('Not found', { status: 404 });
  }

  const origem = new URL(request.url);
  const destino = new URL(destinoBase);
  destino.search = origem.search;

  const headers = new Headers();
  const auth = request.headers.get('Authorization');
  if (auth) headers.set('Authorization', auth);
  const contentType = request.headers.get('Content-Type');
  if (contentType) headers.set('Content-Type', contentType);

  const resp = await fetch(destino.toString(), {
    method: request.method,
    headers,
    body: request.method === 'POST' ? await request.text() : undefined,
  });

  const respBody = await resp.text();
  return new Response(respBody, {
    status: resp.status,
    headers: { 'Content-Type': resp.headers.get('Content-Type') || 'application/json' },
  });
}
