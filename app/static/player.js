let apiPromise;

export function loadYouTubeAPI() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (!apiPromise) {
    apiPromise = new Promise((resolve, reject) => {
      const previous = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = () => {
        resolve(window.YT);
        if (typeof previous === "function") previous();
      };
      const script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      script.async = true;
      script.onerror = () => reject(new Error("YouTube non raggiungibile"));
      document.head.append(script);
    });
  }
  return apiPromise;
}

export function playerErrorMessage(code) {
  if ([2, 100].includes(code)) return "Questo video non è disponibile. Scegli un altro set o modifica i filtri.";
  if ([101, 150].includes(code)) return "Questo video non consente la riproduzione qui. Scegli un altro set o modifica i filtri.";
  if (code === 153) return "YouTube non riesce a identificare il sito. Scegli un altro set o riprova più tardi.";
  if (code === 5) return "Il player non riesce a riprodurre il video. Scegli un altro set o modifica i filtri.";
  return "Il player non è disponibile in questo momento. Scegli un altro set o modifica i filtri.";
}

export class SetPlayer {
  constructor(container, onStatus, apiLoader = loadYouTubeAPI, timeoutMs = 12000) {
    this.container = container;
    this.onStatus = onStatus;
    this.apiLoader = apiLoader;
    this.timeoutMs = timeoutMs;
    this.version = 0;
    this.instance = null;
    this.timer = null;
    this.complete = null;
  }

  clear(version) {
    this.version = version;
    clearTimeout(this.timer);
    this.timer = null;
    if (this.complete) this.complete("cancelled");
    this.complete = null;
    if (this.instance) {
      try { this.instance.destroy(); } catch { /* A partially constructed player may already be gone. */ }
      this.instance = null;
    }
    this.container.replaceChildren();
  }

  async replace(videoId, version) {
    this.clear(version);
    let failed = false;
    const completion = new Promise(resolve => { this.complete = resolve; });
    const active = () => this.version === version && !failed;
    const finish = (status, message = "") => {
      if (!active()) return;
      clearTimeout(this.timer);
      if (status === "error") failed = true;
      this.onStatus({ status, message, version });
      if (this.complete) this.complete(status);
      this.complete = null;
    };
    this.onStatus({ status: "loading", version });
    this.timer = setTimeout(() => finish("error", playerErrorMessage("timeout")), this.timeoutMs);
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId)) {
      finish("error", playerErrorMessage(2));
      return completion;
    }
    // Keep API loading inside this selection's deadline; no polling or automatic retries.
    this.apiLoader().then(YT => {
      if (!active()) return;
      const mount = document.createElement("div");
      this.container.append(mount);
      this.instance = new YT.Player(mount, {
        width: "100%", height: "100%",
        playerVars: { autoplay: 0, controls: 1, playsinline: 1, enablejsapi: 1, origin: window.location.origin },
        events: {
          onReady: event => {
            if (active()) event.target.cueVideoById({ videoId, startSeconds: 0 });
          },
          onStateChange: event => {
            if (active() && event.data === YT.PlayerState.CUED) finish("ready");
            // ENDED deliberately does nothing. Only the visitor can start or change a set.
          },
          onError: event => finish("error", playerErrorMessage(event.data)),
        },
      });
    }).catch(() => finish("error", playerErrorMessage("network")));
    return completion;
  }
}
