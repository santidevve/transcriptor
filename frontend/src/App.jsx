import { useState } from 'react';

const apiBaseUrl = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');
const maxUploadSize = 25 * 1024 * 1024;
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
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
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
              {cargando ? 'Transcribiendo…' : 'Transcribir'}
            </button>
          </div>
          <p className="form-hint">
            El audio se procesa en tu servidor y se elimina al terminar.
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
