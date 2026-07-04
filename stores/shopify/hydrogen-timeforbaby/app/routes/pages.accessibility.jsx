import {PolicyDoc} from '~/components/PolicyDoc';
import {getPolicy} from '~/lib/legal';
import {config} from '~/lib/theme';

const SLUG = 'accessibility';
export const meta = () => [
  {title: `${getPolicy(SLUG).title} — ${config.brand.name}`},
];

export default function Route() {
  return (
    <div className="tob-legal">
      <PolicyDoc doc={getPolicy(SLUG)} />
    </div>
  );
}
