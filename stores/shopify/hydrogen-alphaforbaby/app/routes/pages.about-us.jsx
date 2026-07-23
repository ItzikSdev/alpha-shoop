import {config} from '~/lib/theme';

export const meta = () => [
  {title: `About Us — ${config.brand.name}`},
  {
    name: 'description',
    content:
      'Learn about ALPHA FOR BABY — our story, our mission, and why we care so deeply about the little ones.',
  },
];

export default function AboutUs() {
  const {brand} = config;

  return (
    <div className="tob-legal">
      <article className="tobp-legal tob-about">
        {/* ── Hero banner ── */}
        <div className="tob-about-hero">
          <p className="tob-about-eyebrow">Our story</p>
          <h1 className="tob-about-title">Made for the moments that matter.</h1>
          <p className="tob-about-sub">
            {brand.tagline}
          </p>
        </div>

        {/* ── Mission ── */}
        <section className="tob-about-section">
          <h2>Why we started</h2>
          <p>
            Every parent knows the feeling — you want the very best for your baby, but finding
            clothes that are truly soft, safe, and beautifully made can feel impossible. That's
            exactly why {brand.name} was born.
          </p>
          <p>
            We set out to build a store where every single item is hand-picked for quality,
            comfort, and style — so you can shop with confidence and dress your little one in
            pieces you'll actually love.
          </p>
        </section>

        {/* ── Values grid ── */}
        <section className="tob-about-section">
          <h2>What we stand for</h2>
          <div className="tob-about-values">
            <div className="tob-about-value">
              <span className="tob-about-value-icon" aria-hidden="true">🌿</span>
              <h3>Organic &amp; safe</h3>
              <p>
                We prioritise organic cotton and non-toxic materials — gentle on delicate skin
                from day one.
              </p>
            </div>
            <div className="tob-about-value">
              <span className="tob-about-value-icon" aria-hidden="true">✦</span>
              <h3>Thoughtful design</h3>
              <p>
                Every piece is chosen for its fit, finish, and practicality — because parents
                deserve beautiful AND functional.
              </p>
            </div>
            <div className="tob-about-value">
              <span className="tob-about-value-icon" aria-hidden="true">🌍</span>
              <h3>Ships worldwide</h3>
              <p>
                We ship to families across the globe — fast, tracked, and with free shipping on
                orders over $50.
              </p>
            </div>
            <div className="tob-about-value">
              <span className="tob-about-value-icon" aria-hidden="true">💛</span>
              <h3>30-day returns</h3>
              <p>
                Not happy? No problem. We offer hassle-free 30-day returns because your
                satisfaction matters.
              </p>
            </div>
          </div>
        </section>

        {/* ── Promise ── */}
        <section className="tob-about-section tob-about-promise">
          <h2>Our promise to you</h2>
          <p>
            We personally vet every product before it goes live on the store. If we wouldn't put
            it on our own baby, it doesn't make the cut. That's the {brand.name} standard — and
            we're proud of it.
          </p>
          <p>
            Questions? We're always here.{' '}
            <a href={`mailto:${brand.supportEmail}`}>{brand.supportEmail}</a>
          </p>
        </section>
      </article>
    </div>
  );
}
