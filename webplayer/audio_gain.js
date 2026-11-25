/* Volume values above 100% need Web Audio: HTMLMediaElement.volume is capped at 1. */
(() => {
  const states = new WeakMap();
  const clamp = value => Math.max(0, Math.min(200, Number(value) || 0));
  function stateFor(video) {
    let state = states.get(video);
    if (state) return state;
    state = { effective: 100, gain: null, context: null };
    try {
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) throw new Error('Web Audio unavailable');
      const context = new Context();
      const gain = context.createGain();
      context.createMediaElementSource(video).connect(gain).connect(context.destination);
      state.context = context;
      state.gain = gain;
    } catch (_) {
      // Keep native volume working when a provider does not permit Web Audio.
    }
    states.set(video, state);
    return state;
  }
  window.__tvpAudioGain = {
    set(video, value) {
      const requested = clamp(value);
      const state = states.get(video) || (requested > 100 ? stateFor(video) : null);
      video.volume = Math.min(1, requested / 100);
      if (state?.gain) {
        state.gain.gain.value = Math.max(1, requested / 100);
        state.context.resume().catch(() => {});
        state.effective = requested;
      } else if (state) {
        state.effective = Math.min(100, requested);
      }
      if (!state) {
        return Math.min(100, requested);
      }
      return state.effective;
    },
    get(video) {
      return states.get(video)?.effective ?? video.volume * 100;
    },
    resume(video) {
      const context = states.get(video)?.context;
      return context ? context.resume().catch(() => {}) : Promise.resolve();
    }
  };
})();
