from pathlib import Path

p=Path('index.html')
s=p.read_text(encoding='utf-8')

def one(old,new,label):
    global s
    n=s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: esperado 1, encontrado {n}')
    s=s.replace(old,new,1)

one(
'''  const videoUploads = [];
  let videoFrameReadFailed = false;
  for (let v = 0; v < videos.length; v++) {
    videoUploads.push(uploadImportVideo(videos[v], operationalPlat, operationalDate));
    try {''',
'''  let videoFrameReadFailed = false;
  for (let v = 0; v < videos.length; v++) {
    try {''',
'upload concorrente')

one(
'''  // Guarda o(s) id(s) do(s) vídeo(s) já salvos no Storage — usado em
  // confirmImport() pra vincular cada corrida ao vídeo que a confirmou
  // (auditoria manual futura, retenção de 180 dias).
  const _videoUploadResults = await Promise.all(videoUploads);''',
'''  // Só envia o arquivo original depois que a leitura local terminou.
  // Em celular/WebView, fazer upload e seek/decodificação simultaneamente
  // do mesmo File grande pode bloquear o decoder e deixar a tela parada.
  if (videos.length) updateRing('Salvando vídeo para conferência ' + dot, false);
  const _videoUploadResults = await Promise.all(
    videos.map(file => uploadImportVideo(file, operationalPlat, operationalDate))
  );''',
'upload depois da leitura')

one("          try { video.load(); } catch(e) {}\n", "", 'load recursivo')

one(
'''    video.onloadedmetadata = async () => {
      clearTimeout(metadataTimer);
      // loadedmetadata só garante dimensões/duração.''',
'''    video.onloadedmetadata = async () => {
      clearTimeout(metadataTimer);
      try {
      // loadedmetadata só garante dimensões/duração.''',
'abrir try loadedmetadata')

one(
'''      if (frames.length > 0) resolve(frames);
      else reject(new Error('Nenhum quadro legível foi extraído do vídeo.'));
    };

    video.onerror = (e) => {''',
'''      if (frames.length > 0) resolve(frames);
      else reject(new Error('Nenhum quadro legível foi extraído do vídeo.'));
      } catch(e) {
        try{document.body.removeChild(video);}catch(e2){}
        URL.revokeObjectURL(url);
        reject(e instanceof Error ? e : new Error(String(e)));
      }
    };

    video.onerror = (e) => {''',
'fechar try loadedmetadata')

old='''          await new Promise((res) => {
            // O handler entra antes do seek, mas damos tempo real para o WebView
            // decodificar o quadro. Em alguns Androids 1,5 s era curto e o
            // fallback desenhava um frame preto, fazendo o vídeo inteiro zerar.
            let done = false;
            const finishSeek = (fromEvent) => {
              if (done) return;
              const draw = () => {
                if (done) return;
                done = true;
                clearTimeout(timer);
                video.onseeked = null;
                try {
                  if (video.readyState >= 2) ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                } catch(e) {}
                res();
              };
              if (fromEvent) setTimeout(draw, 80); else draw();
            };
            const timer = setTimeout(() => finishSeek(false), 4000);
            video.onseeked = () => finishSeek(true);
            video.currentTime = Math.min(time, Math.max(0, duration - 0.03));
          });'''
new='''          const frameDrawn = await new Promise((res) => {
            // Só considera o seek concluído quando há um frame decodificado de
            // verdade. O fallback não transforma ausência de frame em imagem preta.
            let done = false;
            const finishSeek = (fromEvent) => {
              if (done) return;
              const draw = () => {
                if (done) return;
                done = true;
                clearTimeout(timer);
                video.onseeked = null;
                let ok = false;
                try {
                  if (video.readyState >= 2 && video.videoWidth > 0 && video.videoHeight > 0) {
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    ok = true;
                  }
                } catch(e) {}
                res(ok);
              };
              if (fromEvent && typeof video.requestVideoFrameCallback === 'function') {
                try { video.requestVideoFrameCallback(() => draw()); return; } catch(e) {}
              }
              if (fromEvent) setTimeout(draw, 120); else draw();
            };
            const timer = setTimeout(() => finishSeek(false), 4500);
            video.onseeked = () => finishSeek(true);
            video.currentTime = Math.min(time, Math.max(0, duration - 0.03));
          });
          if (!frameDrawn) continue;'''
one(old,new,'seek com frame real')

one(
'''        } catch(e) { console.warn('Frame t='+time, e); }
        if (typeof onProgress === 'function') onProgress(timeIndex + 1, times.length);
      }''',
'''        } catch(e) { console.warn('Frame t='+time, e); }
        finally {
          if (typeof onProgress === 'function') onProgress(timeIndex + 1, times.length);
        }
      }''',
'progresso em finally')

one(
'''    video.muted      = true;
    video.playsInline = true;
    video.preload    = 'auto';''',
'''    video.muted      = true;
    video.playsInline = true;
    video.setAttribute('playsinline', '');
    video.setAttribute('webkit-playsinline', '');
    video.preload    = 'auto';''',
'playsinline')

p.write_text(s,encoding='utf-8')
