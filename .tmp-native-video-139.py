from pathlib import Path

p = Path('index.html')
s = p.read_text(encoding='utf-8')
old = "async function extractVideoFrames(file, onProgress) {"
if s.count(old) != 1:
    raise SystemExit(f'extractVideoFrames esperado 1x, encontrado {s.count(old)}')

native = r'''
// APK 1.3.9+: o WebView de alguns aparelhos não consegue decodificar certos
// screen recordings mesmo quando o arquivo é válido. Quando o bridge nativo
// estiver disponível, o Android decodifica o vídeo e devolve só os JPEGs.
const _nativeVideoExtractRequests = new Map();
window.__mobNativeVideoFrame = function(token, dataUrl) {
  const r = _nativeVideoExtractRequests.get(token);
  if (!r || !dataUrl) return;
  const raw = String(dataUrl).includes(',') ? String(dataUrl).split(',').pop() : String(dataUrl);
  if (raw) r.frames.push(raw);
};
window.__mobNativeVideoProgress = function(token, done, total) {
  const r = _nativeVideoExtractRequests.get(token);
  if (r && typeof r.onProgress === 'function') r.onProgress(Number(done)||0, Number(total)||0);
};
window.__mobNativeVideoDone = function(token, emitted) {
  const r = _nativeVideoExtractRequests.get(token);
  if (!r) return;
  clearTimeout(r.timer);
  _nativeVideoExtractRequests.delete(token);
  if (!r.frames.length) r.reject(new Error('O Android não conseguiu extrair quadros deste vídeo.'));
  else r.resolve(r.frames);
};
window.__mobNativeVideoError = function(token, message) {
  const r = _nativeVideoExtractRequests.get(token);
  if (!r) return;
  clearTimeout(r.timer);
  _nativeVideoExtractRequests.delete(token);
  r.reject(new Error(message || 'Falha no decodificador nativo do vídeo.'));
};

function extractVideoFramesNative(file, onProgress) {
  return new Promise((resolve, reject) => {
    const token = 'nv_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,8);
    const timer = setTimeout(() => {
      _nativeVideoExtractRequests.delete(token);
      reject(new Error('Tempo esgotado ao decodificar o vídeo no Android.'));
    }, 120000);
    _nativeVideoExtractRequests.set(token, {frames:[], onProgress, resolve, reject, timer});
    try {
      const started = SmartMobiNative.extractSelectedVideoFrames(token, 72, 720);
      if (started === false) {
        clearTimeout(timer);
        _nativeVideoExtractRequests.delete(token);
        reject(Object.assign(new Error('O Android não recebeu o arquivo de vídeo selecionado.'), {nativeNotStarted:true}));
      }
    } catch(e) {
      clearTimeout(timer);
      _nativeVideoExtractRequests.delete(token);
      reject(Object.assign(e instanceof Error ? e : new Error(String(e)), {nativeNotStarted:true}));
    }
  });
}

async function extractVideoFrames(file, onProgress) {
  let canNative = false;
  try {
    canNative = !!(window.SmartMobiNative &&
      typeof SmartMobiNative.hasNativeVideoFrameExtraction === 'function' &&
      SmartMobiNative.hasNativeVideoFrameExtraction() &&
      typeof SmartMobiNative.extractSelectedVideoFrames === 'function');
  } catch(e) {}
  if (canNative) {
    try {
      return await extractVideoFramesNative(file, onProgress);
    } catch(e) {
      // Só cai para o decoder web se a ponte não chegou a iniciar. Se o
      // Android iniciou e reportou erro real de codec, repetir no WebView
      // apenas recriaria o travamento que motivou este caminho nativo.
      if (!e || !e.nativeNotStarted) throw e;
      console.warn('[video] bridge nativo indisponível, usando navegador:', e);
    }
  }
  return extractVideoFramesBrowser(file, onProgress);
}

async function extractVideoFramesBrowser(file, onProgress) {'''

s = s.replace(old, native, 1)
if s.count('async function extractVideoFramesBrowser(file, onProgress) {') != 1:
    raise SystemExit('wrapper browser não entrou')
if s.count('async function extractVideoFrames(file, onProgress) {') != 1:
    raise SystemExit('wrapper principal inválido')
p.write_text(s, encoding='utf-8')
