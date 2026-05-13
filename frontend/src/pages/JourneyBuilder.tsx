/**
 * Journey Builder — embeds Dittofeed inside cdp-main's shell.
 *
 * The URL is /journey-builder/<sub>; <sub> maps directly to the same path
 * inside Dittofeed at /dashboard/<sub>. cdp-main keeps the sidebar + top
 * chrome; Dittofeed's own nav is stripped via CSS injection at the nginx
 * layer (see journeys/dashboard-overrides.css). To the user it feels
 * native — they never see Dittofeed branding or its sidebar.
 *
 * Implementation note: the iframe is the simplest way to mount a third
 * party Next.js app inside a React app without rebuilding it. Same origin
 * (via the reverse proxy) means no CORS / cookie issues. We deliberately
 * don't show iframe chrome (scrollbars, borders) — the page area expands
 * full bleed.
 */
import { useMemo, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';

const JOURNEY_BUILDER_ROOT = '/journey-builder';
const DITTOFEED_ROOT = '/dashboard';

// Valid Dittofeed sub-paths we still iframe. As surfaces are rebuilt
// natively (Phase 0+: Deliveries → native), they're removed from here AND
// get their own React Router route in App.tsx.
const ALLOWED_SUBS = new Set([
  'journeys',
  'templates',
  'broadcasts',
  'analysis/overview',
]);
const DEFAULT_SUB = 'journeys';

export default function JourneyBuilder() {
  // Pull whatever follows /journey-builder/ from the URL. React Router's
  // splat `*` parameter captures the remainder.
  const params = useParams();
  const sub = (params['*'] || DEFAULT_SUB).replace(/^\//, '');
  const safeSub = ALLOWED_SUBS.has(sub) ? sub : DEFAULT_SUB;

  // Same-origin URL (nginx routes /dashboard/* to Dittofeed).
  const iframeSrc = `${DITTOFEED_ROOT}/${safeSub}`;

  // Bumping this key forces React to remount the iframe — useful when the
  // user clicks the Reload affordance.
  const [reloadKey, setReloadKey] = useState(0);

  // Reset reloadKey whenever the user navigates to a different sub-path so
  // the iframe element is reused (no flash) but the src change kicks the
  // internal navigation.
  useEffect(() => {
    // no-op; keep this hook for future sub-path side effects.
  }, [safeSub]);

  return (
    <div className="relative h-screen -mx-6 -my-10 animate-fade-in sm:-mx-8 lg:-mx-14 lg:-my-16">
      <button
        type="button"
        onClick={() => setReloadKey((k) => k + 1)}
        className="absolute right-4 top-3 z-10 inline-flex items-center gap-1.5 bg-white/90 px-2.5 py-1 text-xs text-gray-500 shadow-sm backdrop-blur hover:text-gray-900 dark:bg-gray-950/90 dark:text-gray-400 dark:hover:text-gray-100"
        title="Reload Journey Builder"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        Reload
      </button>

      {/* Full-bleed iframe — Dittofeed UI minus its own chrome */}
      <iframe
        key={`${safeSub}-${reloadKey}`}
        src={iframeSrc}
        title="Journey Builder"
        className="h-full w-full border-0 bg-white dark:bg-gray-950"
        allow="clipboard-read; clipboard-write"
      />
    </div>
  );
}
