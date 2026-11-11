import { useState } from 'react';

const apiBaseUrl = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');
const maxUploadSize = 25 * 1024 * 1024;
const maxCookieFileSize = 1024 * 1024;
const acceptedFileTypes = '.flac,.m4a,.mp3,.mp4,.mov,.ogg,.wav,.webm';

function formatTime(seconds) {
  const totalSeconds = Math.floor(Number(seconds) || 0);
  const minutes = Math.floor(totalSeconds / 60);
  const remainingSeconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`;
}

export default function App() {
  const [url, setUrl] = useState('');
  const [archivo, setArchivo] = useState(null);
  const [archivoCookies, setArchivoCookies] = useState(null);
  const [cookiesConfirmadas, setCookiesConfirmadas] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [descargandoWord, setDescargandoWord] = useState(false);
  const [error, setError] = useState('');
  const [notificationPermission, setNotificationPermission] = useState(() => (
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission
  ));
  const [notificationMessage, setNotificationMessage] = useState('');

  async function activarAvisos() {
    if (typeof Notification === 'undefined') {
      setNotificationPermission('unsupported');
      setNotificationMessage('Este navegador no admite notificaciones web.');
      return;
    }

    try {
      const permission = await Notification.requestPermission();
      setNotificationPermission(permission);
      setNotificationMessage(
        permission === 'granted'
          ? 'Te avisaremos cuando una transcripción termine mientras esta página siga abierta.'
          : 'No se concedió el permiso. El resultado seguirá apareciendo aquí.',
      );
    } catch {
      setNotificationMessage(
        'No se pudo activar el permiso de notificaciones en este navegador.',
      );
    }
  }

  async function enviarTranscripcion(endpoint, body, headers = {}) {
    setCargando(true);
    setError('');
    setResultado(null);

    try {
      const response = await fetch(`${apiBaseUrl}${endpoint}`, {
        method: 'POST',
        headers,
        body,
      });

      let data;
      try {
        data = await response.json();
      } catch {
        throw new Error('El servidor devolvió una respuesta no válida.');
      }

      if (!response.ok) {
        throw new Error(data.error || 'No se pudo completar la transcripción.');
      }

      if (!data || !Array.isArray(data.segmentos)) {
        throw new Error('La respuesta del servidor no tiene el formato esperado.');
      }

      setResultado(data);
      if (
        document.visibilityState === 'hidden'
        && typeof Notification !== 'undefined'
        && Notification.permission === 'granted'
      ) {
        try {
          const notification = new Notification('Tu transcripción está lista', {
            body: data.titulo || 'Ya puedes consultar el resultado.',
            tag: 'transcripcion-lista',
          });
          notification.onclick = () => {
            window.focus();
            notification.close();
          };
        } catch {
          setNotificationMessage(
            'La transcripción terminó, pero el navegador no pudo mostrar la notificación.',
          );
        }
      }
    } catch (requestError) {
      setError(
        requestError.message || 'No fue posible conectarse con el servidor.',
      );
    } finally {
      setCargando(false);
    }
  }

  async function solicitarTranscripcion(event) {
    event.preventDefault();
    const urlLimpia = url.trim();

    if (!urlLimpia) {
      setError('Pega el enlace de un video de YouTube.');
      setResultado(null);
      return;
    }

    if (archivoCookies && archivoCookies.size > maxCookieFileSize) {
      setError('El archivo de cookies no puede superar 1 MB.');
      setResultado(null);
      return;
    }
    if (archivoCookies && !cookiesConfirmadas) {
      setError('Confirma que entiendes el riesgo antes de enviar tus cookies.');
      setResultado(null);
      return;
    }

    if (archivoCookies) {
      const formData = new FormData();
      formData.append('url', urlLimpia);
      formData.append('cookies', archivoCookies);
      await enviarTranscripcion('/api/transcribir/', formData);
      return;
    }

    await enviarTranscripcion(
      '/api/transcribir/',
      JSON.stringify({ url: urlLimpia }),
      { 'Content-Type': 'application/json' },
    );
  }

  async function solicitarArchivo(event) {
    event.preventDefault();

    if (!archivo) {
      setError('Selecciona un archivo de audio o video.');
      setResultado(null);
      return;
    }
    if (archivo.size > maxUploadSize) {
      setError('El archivo no puede superar los 25 MB.');
      setResultado(null);
      return;
    }

    const formData = new FormData();
    formData.append('archivo', archivo);
    await enviarTranscripcion('/api/transcribir-archivo/', formData);
  }

  async function descargarTranscripcionWord() {
    setDescargandoWord(true);
    setError('');
    try {
      const response = await fetch(`${apiBaseUrl}/api/descargar-transcripcion-docx/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resultado),
      });

      if (!response.ok) {
        let message = 'No se pudo generar el documento Word.';
        try {
          const data = await response.json();
          message = data.error || message;
        } catch {
          // Keep the readable fallback when the server does not return JSON.
        }
        throw new Error(message);
      }

      const documentUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = documentUrl;
      const safeTitle = (resultado.titulo || 'transcripcion')
        .normalize('NFKD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-zA-Z0-9_-]+/g, '-')
        .replace(/^-|-$/g, '') || 'transcripcion';
      link.download = `${safeTitle}.docx`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(documentUrl), 1000);
    } catch (requestError) {
      setError(requestError.message || 'No se pudo descargar el documento Word.');
    } finally {
      setDescargandoWord(false);
    }
  }

  return (
    <main className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Transcriptor, inicio">
          <span className="brand-mark" aria-hidden="true">T</span>
          <span>Transcriptor</span>
        </a>
        <span className="topbar-note">Audio a texto, en minutos</span>
      </header>

      <section className="workspace" aria-labelledby="page-title">
        <div className="intro">
          <span className="eyebrow">TRANSCRIPCIÓN CON IA</span>
          <h1 id="page-title">Convierte audio en texto.</h1>
          <p>
            Sube un archivo para transcribirlo con marcas de tiempo. También
            puedes probar con un enlace de YouTube.
          </p>
        </div>

        <form className="url-form upload-form" onSubmit={solicitarArchivo}>
          <label htmlFor="audio-file">Archivo de audio o video</label>
          <input
            accept={acceptedFileTypes}
            id="audio-file"
            onChange={(event) => setArchivo(event.target.files?.[0] || null)}
            type="file"
          />
          <p className="form-hint">
            MP3, WAV, M4A, MP4, MOV, OGG, FLAC o WebM; máximo 25 MB y 60
            segundos. Se elimina al terminar.
          </p>
          {archivo && (
            <p className="selected-file" aria-live="polite">
              Archivo seleccionado: {archivo.name}
            </p>
          )}
          <button className="upload-button" disabled={cargando} type="submit">
            {cargando ? 'Transcribiendo…' : 'Transcribir archivo'}
          </button>
        </form>

        <form className="url-form" onSubmit={solicitarTranscripcion}>
          <label htmlFor="video-url">O pega un enlace de YouTube</label>
          <details className="cookie-guide">
            <summary>Cómo usar cookies de YouTube (opcional)</summary>
            <ol>
              <li>
                Instala una extensión confiable:{' '}
                <a
                  href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc"
                  rel="noreferrer"
                  target="_blank"
                >
                  Get cookies.txt LOCALLY para Chrome
                </a>
                {' '}o{' '}
                <a
                  href="https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/"
                  rel="noreferrer"
                  target="_blank"
                >
                  cookies.txt para Firefox
                </a>
                . No instales la extensión antigua “Get cookies.txt” que no
                incluya “LOCALLY”.
              </li>
              <li>
                Inicia sesión en YouTube, abre el video y usa la extensión para
                exportar las cookies de youtube.com en formato Netscape
                cookies.txt.
              </li>
              <li>
                Selecciona ese archivo, pega el enlace del video y pulsa
                “Descargar y transcribir desde YouTube”. El servidor descarga
                el audio solo para procesarlo y luego lo elimina; no se entrega
                un archivo de audio para guardar.
              </li>
            </ol>
            <p className="cookie-warning">
              Las cookies pueden dar acceso a tu cuenta. Exporta solo las de
              YouTube, úsalo solo con videos a los que tengas derecho de acceso,
              no compartas este archivo y evita usar tu cuenta principal. Se
              envían por HTTPS al servidor para esta solicitud y no se guardan
              como archivo permanente. YouTube puede invalidarlas o limitar la
              cuenta; las cookies no garantizan que se evite un bloqueo.
            </p>
          </details>
          <label htmlFor="youtube-cookies">Archivo cookies.txt (opcional)</label>
          <input
            accept=".txt,text/plain"
            id="youtube-cookies"
            onChange={(event) => {
              setArchivoCookies(event.target.files?.[0] || null);
              setCookiesConfirmadas(false);
            }}
            type="file"
          />
          {archivoCookies && (
            <>
              <p className="selected-file" aria-live="polite">
                Archivo seleccionado: {archivoCookies.name}
              </p>
              <label className="cookie-consent">
                <input
                  checked={cookiesConfirmadas}
                  onChange={(event) => setCookiesConfirmadas(event.target.checked)}
                  type="checkbox"
                />
                Entiendo que el archivo contiene credenciales de sesión y autorizo
                su uso temporal para esta transcripción.
              </label>
            </>
          )}
          <div className="input-row">
            <input
              autoComplete="url"
              id="video-url"
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              spellCheck="false"
              type="url"
              value={url}
            />
            <button disabled={cargando} type="submit">
              {cargando
                ? 'Descargando y transcribiendo…'
                : 'Descargar y transcribir desde YouTube'}
            </button>
          </div>
          <p className="form-hint">
            El audio se procesa en el servidor y se elimina al terminar. Las
            cookies son opcionales y solo se usan para este intento.
          </p>
          <div className="notification-controls">
            {notificationPermission === 'default' && (
              <button
                className="notification-button"
                onClick={activarAvisos}
                type="button"
              >
                Activar avisos del navegador
              </button>
            )}
            {notificationPermission === 'granted' && (
              <span className="notification-enabled">Avisos del navegador activados</span>
            )}
            {notificationPermission === 'denied' && (
              <span className="notification-note">
                Avisos bloqueados; el resultado aparecerá en esta página.
              </span>
            )}
            {notificationPermission === 'unsupported' && (
              <span className="notification-note">
                Este navegador no admite avisos web.
              </span>
            )}
          </div>
          {notificationMessage && (
            <p className="notification-message" role="status">
              {notificationMessage}
            </p>
          )}
        </form>

        {cargando && (
          <div className="status-card loading-card" role="status">
            <span className="spinner" aria-hidden="true" />
            <div>
              <strong>Estamos preparando tu transcripción</strong>
              <p>
                La primera solicitud puede tardar mientras se carga el modelo
                de voz.
              </p>
            </div>
          </div>
        )}

        {error && (
          <div className="status-card error-card" role="alert">
            <strong>No se pudo completar</strong>
            <p>{error}</p>
          </div>
        )}

        {resultado && (
          <section className="transcript-card" aria-labelledby="transcript-title">
            <div className="transcript-heading">
              <div>
                <span className="eyebrow">RESULTADO</span>
                <h2 id="transcript-title">{resultado.titulo}</h2>
              </div>
              {resultado.idioma && (
                <span className="language-badge">
                  Idioma: {resultado.idioma}
                </span>
              )}
              <button
                className="download-word-button"
                disabled={descargandoWord}
                onClick={descargarTranscripcionWord}
                type="button"
              >
                {descargandoWord ? 'Preparando Word…' : 'Descargar en Word'}
              </button>
            </div>
            {resultado.segmentos.length === 0 ? (
              <p className="empty-state">No se detectó voz en este video.</p>
            ) : (
              <ol className="segments">
                {resultado.segmentos.map((segmento, index) => (
                  <li
                    className="segment"
                    key={`${segmento.inicio}-${index}`}
                  >
                    <time className="timestamp">
                      {formatTime(segmento.inicio)}
                    </time>
                    <p>{segmento.texto}</p>
                  </li>
                ))}
              </ol>
            )}
          </section>
        )}
      </section>

      <footer className="footer">
        <span>Transcriptor de audio y video</span>
        <span>El resultado depende de la calidad del audio.</span>
      </footer>
    </main>
  );
}
