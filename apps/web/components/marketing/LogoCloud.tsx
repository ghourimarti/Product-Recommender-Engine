"use client";

/* Auto-scrolling logo marquee (constructor.com-style "trusted by" strip).
   These are stylized wordmarks — realistic placeholder brands rendered as text
   so the strip looks alive without shipping anyone's real trademark assets. */

const BRANDS = [
  "SoundWave", "AudioMart", "PulseGear", "NovaTech", "EchoStore",
  "BassLab", "ClearNote", "VoltAudio", "MixHaus", "ToneCraft",
  "SonicHub", "WaveForm",
];

function Row() {
  return (
    <div className="flex items-center gap-14 px-7 shrink-0">
      {BRANDS.map((b) => (
        <span
          key={b}
          className="text-xl font-display font-bold text-mkt-muted whitespace-nowrap
                     hover:text-mkt-ink transition-colors select-none"
        >
          {b}
        </span>
      ))}
    </div>
  );
}

export function LogoCloud({ label = "Trusted by product teams at fast-growing retailers" }: { label?: string }) {
  return (
    <div className="py-14 border-y border-mkt-border bg-white">
      <p className="text-center text-xs font-semibold uppercase tracking-widest text-mkt-muted mb-8">
        {label}
      </p>
      <div className="marquee-mask overflow-hidden">
        {/* two identical rows animated -50% => seamless loop */}
        <div className="marquee-track flex w-max animate-marquee">
          <Row />
          <Row />
        </div>
      </div>
    </div>
  );
}
