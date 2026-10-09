import {config} from '~/lib/theme';

/**
 * Rotating announcement strip — §5 item 1 / v1.36 item 1.
 *
 * Its own band ABOVE the header row, never merged into it and never below it.
 * Content comes from theme.config.json's `announcement` array.
 */
export function AnnouncementTicker() {
  const items = config.announcement || [];
  if (!items.length) return null;
  const loop = [...items, ...items];
  return (
    <div className="tob-ticker" role="complementary" aria-label="Store announcements">
      <div className="tob-ticker-track">
        {loop.map((t, i) => (
          <span key={`${t}-${i}`} className="tob-ticker-item">
            {t}
            <span aria-hidden="true" className="tob-ticker-sep">✦</span>
          </span>
        ))}
      </div>
    </div>
  );
}
