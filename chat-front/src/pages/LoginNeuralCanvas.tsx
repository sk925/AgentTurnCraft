import { useEffect, useRef } from 'react';

/** 沿 ribbon 参数 u∈[0,1) 的基底轨迹（横向流动 + 起伏波） */
function ribbonPoint(
  u: number,
  time: number,
  w: number,
  h: number,
  stream: number,
): { x: number; y: number; tx: number; ty: number } {
  const phase = stream * 1.7;
  const p = (u + time * 0.042) % 1;
  const x =
    w * (0.06 + 0.88 * p) +
    0.12 * w * Math.sin(p * Math.PI * 2 + time * 0.95 + phase) +
    48 * Math.sin(p * 4.2 + time * 1.1 + phase);
  const y =
    h * (0.32 + stream * 0.14) +
    0.1 * h * Math.sin(p * 6 + time * 1.35 + phase) +
    62 * Math.sin(p * 3.1 + time * 0.72) +
    36 * Math.sin(p * 9 + time * 0.55 + stream);

  const eps = 0.008;
  const p2 = (p + eps) % 1;
  const x2 =
    w * (0.06 + 0.88 * p2) +
    0.12 * w * Math.sin(p2 * Math.PI * 2 + time * 0.95 + phase) +
    48 * Math.sin(p2 * 4.2 + time * 1.1 + phase);
  const y2 =
    h * (0.32 + stream * 0.14) +
    0.1 * h * Math.sin(p2 * 6 + time * 1.35 + phase) +
    62 * Math.sin(p2 * 3.1 + time * 0.72) +
    36 * Math.sin(p2 * 9 + time * 0.55 + stream);
  let tx = x2 - x;
  let ty = y2 - y;
  const len = Math.hypot(tx, ty) || 1;
  tx /= len;
  ty /= len;
  return { x, y, tx, ty };
}

type PlexusNode = {
  bx: number;
  by: number;
  ang: number;
  r: number;
};

function makePlexusCluster(
  w: number,
  h: number,
  corner: 'tl' | 'br',
  count: number,
  seed: number,
): PlexusNode[] {
  const out: PlexusNode[] = [];
  const rnd = (i: number) => {
    const s = Math.sin(i * 12.9898 + seed) * 43758.5453123;
    return s - Math.floor(s);
  };
  const marginX = w * 0.38;
  const marginY = h * 0.36;
  for (let i = 0; i < count; i++) {
    const bx = corner === 'tl' ? rnd(i) * marginX : w - marginX * 0.2 - rnd(i) * marginX * 0.85;
    const by = corner === 'tl' ? rnd(i + 3) * marginY : h - marginY * 0.2 - rnd(i + 5) * marginY * 0.85;
    out.push({
      bx,
      by,
      ang: rnd(i + 9) * Math.PI * 2,
      r: 1.1 + rnd(i + 1) * 1.8,
    });
  }
  return out;
}

function drawBackground(ctx: CanvasRenderingContext2D, w: number, h: number) {
  const g = ctx.createRadialGradient(w * 0.5, h * 0.35, 0, w * 0.5, h * 0.5, Math.hypot(w, h) * 0.72);
  g.addColorStop(0, 'rgba(15, 40, 72, 0.55)');
  g.addColorStop(0.45, 'rgba(6, 14, 34, 0.92)');
  g.addColorStop(1, 'rgba(2, 6, 18, 1)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  const g2 = ctx.createRadialGradient(w * 0.85, h * 0.15, 0, w * 0.85, h * 0.15, h * 0.5);
  g2.addColorStop(0, 'rgba(14, 116, 185, 0.14)');
  g2.addColorStop(1, 'rgba(2, 6, 18, 0)');
  ctx.fillStyle = g2;
  ctx.fillRect(0, 0, w, h);

  const g3 = ctx.createRadialGradient(w * 0.08, h * 0.88, 0, w * 0.08, h * 0.88, h * 0.45);
  g3.addColorStop(0, 'rgba(37, 99, 235, 0.1)');
  g3.addColorStop(1, 'rgba(2, 6, 18, 0)');
  ctx.fillStyle = g3;
  ctx.fillRect(0, 0, w, h);
}

function drawParticleGlow(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  alpha: number,
  cool: boolean,
) {
  const r = radius * 2.8;
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  const c0 = cool ? 'rgba(224, 242, 254,' : 'rgba(255, 255, 255,';
  const c1 = cool ? 'rgba(56, 189, 248,' : 'rgba(125, 211, 252,';
  g.addColorStop(0, `${c0}${alpha * 0.95})`);
  g.addColorStop(0.35, `${c1}${alpha * 0.35})`);
  g.addColorStop(0.65, `rgba(14, 165, 233,${alpha * 0.12})`);
  g.addColorStop(1, 'rgba(2, 6, 18, 0)');
  ctx.beginPath();
  ctx.fillStyle = g;
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

export function LoginNeuralCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      return;
    }

    let w = 0;
    let h = 0;
    let lastW = 0;
    let lastH = 0;
    let raf = 0;
    let t = 0;

    let ribbonCount = 52;
    const spreads0: number[] = [];
    const spreads1: number[] = [];
    const phases0: number[] = [];
    const phases1: number[] = [];
    let plexusTL: PlexusNode[] = [];
    let plexusBR: PlexusNode[] = [];

    const initArrays = () => {
      spreads0.length = 0;
      spreads1.length = 0;
      phases0.length = 0;
      phases1.length = 0;
      const area = (w * h) / 1_000_000;
      ribbonCount = Math.min(72, Math.max(36, Math.floor(38 + area * 28)));
      const rnd = (i: number, stream: number) => {
        const s = Math.sin(i * 19.9898 + stream * 7 + w * 0.01) * 43758.5453123;
        return s - Math.floor(s);
      };
      for (let i = 0; i < ribbonCount; i++) {
        spreads0.push((rnd(i, 0) - 0.5) * 26);
        spreads1.push((rnd(i, 1) - 0.5) * 26);
        phases0.push(rnd(i + 1, 0) * Math.PI * 2);
        phases1.push(rnd(i + 1, 1) * Math.PI * 2);
      }
      const seed = (w * 0.13 + h * 0.07) | 0;
      plexusTL = makePlexusCluster(w, h, 'tl', 14, seed);
      plexusBR = makePlexusCluster(w, h, 'br', 14, seed + 17);
    };

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) {
        return;
      }
      const rect = parent.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      h = rect.height;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (Math.abs(w - lastW) > 6 || Math.abs(h - lastH) > 6) {
        lastW = w;
        lastH = h;
        initArrays();
      }
    };

    const plexusLinkDist = () => Math.min(110, Math.max(72, w * 0.085));

    const tick = () => {
      t += 0.016;
      if (w < 16 || h < 16 || ribbonCount === 0) {
        raf = requestAnimationFrame(tick);
        return;
      }

      drawBackground(ctx, w, h);

      const linkD = plexusLinkDist();
      const linkD2 = linkD * linkD;

      const drawPlexus = (nodes: PlexusNode[]) => {
        const positions: { x: number; y: number }[] = [];
        for (let i = 0; i < nodes.length; i++) {
          const n = nodes[i];
          const x = n.bx + 5 * Math.sin(t * 0.55 + n.ang);
          const y = n.by + 5 * Math.cos(t * 0.48 + n.ang * 1.3);
          positions.push({ x, y });
        }
        for (let i = 0; i < positions.length; i++) {
          for (let j = i + 1; j < positions.length; j++) {
            const a = positions[i];
            const b = positions[j];
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const d2 = dx * dx + dy * dy;
            if (d2 > linkD2 || d2 < 4) {
              continue;
            }
            const d = Math.sqrt(d2);
            const alpha = (1 - d / linkD) * 0.14;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
            ctx.lineWidth = 0.45;
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
        for (let i = 0; i < positions.length; i++) {
          const p = positions[i];
          const n = nodes[i];
          const pulse = 0.45 + 0.35 * Math.sin(t * 2.1 + n.ang);
          drawParticleGlow(ctx, p.x, p.y, n.r * 0.85, 0.22 + pulse * 0.12, true);
          ctx.beginPath();
          ctx.fillStyle = `rgba(224, 242, 254, ${0.35 + pulse * 0.25})`;
          ctx.arc(p.x, p.y, n.r * 0.45, 0, Math.PI * 2);
          ctx.fill();
        }
      };

      drawPlexus(plexusTL);
      drawPlexus(plexusBR);

      const drawRibbon = (stream: 0 | 1, spreads: number[], phases: number[]) => {
        const pts: { x: number; y: number }[] = [];
        for (let i = 0; i < ribbonCount; i++) {
          const u = (i / ribbonCount + t * 0.036) % 1;
          const base = ribbonPoint(u, t, w, h, stream);
          const spread = spreads[i] ?? 0;
          const nx = -base.ty;
          const ny = base.tx;
          const wob = 4 * Math.sin(t * 1.2 + phases[i] + u * 8);
          pts.push({
            x: base.x + nx * spread + wob * base.tx * 0.02,
            y: base.y + ny * spread + wob * base.ty * 0.02,
          });
        }
        const segMax = Math.min(140, w * 0.14);
        const segMax2 = segMax * segMax;
        for (let i = 0; i < pts.length - 1; i++) {
          const a = pts[i];
          const b = pts[i + 1];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 > segMax2) {
            continue;
          }
          const d = Math.sqrt(d2);
          const pulse = 0.5 + 0.5 * Math.sin(t * 2.4 + i * 0.08 + stream);
          const alpha = pulse * (1 - d / segMax) * 0.38;
          ctx.beginPath();
          ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
          ctx.lineWidth = 0.5 + (1 - d / segMax) * 0.75;
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        for (let i = 0; i < pts.length; i++) {
          const p = pts[i];
          const pr = phases[i];
          const sizeVar = 0.85 + 0.55 * Math.sin(t * 2.8 + pr + i * 0.15);
          const bokeh = i % 3 === 0 ? 1.15 : 0.72;
          const r = (1.15 + sizeVar * 0.45) * bokeh;
          if (i % 2 === 0) {
            drawParticleGlow(ctx, p.x, p.y, r, 0.28 + 0.12 * Math.sin(t * 1.9 + pr), true);
          }
          ctx.beginPath();
          ctx.fillStyle = `rgba(186, 230, 253, ${0.42 + 0.28 * Math.sin(t * 2.2 + pr)})`;
          ctx.arc(p.x, p.y, r * 0.42, 0, Math.PI * 2);
          ctx.fill();
          ctx.beginPath();
          ctx.fillStyle = `rgba(248, 250, 252, ${0.55 + 0.25 * Math.sin(t * 2.5 + pr)})`;
          ctx.arc(p.x, p.y, r * 0.18, 0, Math.PI * 2);
          ctx.fill();
        }
      };

      drawRibbon(0, spreads0, phases0);
      drawRibbon(1, spreads1, phases1);

      raf = requestAnimationFrame(tick);
    };

    resize();
    const ro = new ResizeObserver(() => {
      resize();
    });
    ro.observe(canvas.parentElement!);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className="login-page__canvas" aria-hidden />;
}
