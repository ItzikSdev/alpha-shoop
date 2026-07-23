import * as React from 'react';
import {Pagination} from '@shopify/hydrogen';

/**
 * <PaginatedResourceSection> encapsulates the previous and next pagination behaviors throughout your application.
 * Pass `autoLoad` to replace the "Load more" button with infinite scroll: the
 * next page is fetched automatically as the sentinel scrolls into view.
 * @param {Class<Pagination<NodesType>>['connection']> & {autoLoad?: boolean}}
 */
export function PaginatedResourceSection({
  connection,
  children,
  ariaLabel,
  resourcesClassName,
  autoLoad = false,
}) {
  return (
    <Pagination connection={connection}>
      {({nodes, isLoading, hasNextPage, PreviousLink, NextLink}) => {
        const resourcesMarkup = nodes.map((node, index) =>
          children({node, index}),
        );

        return (
          <div>
            <PreviousLink>
              {isLoading ? (
                'Loading...'
              ) : (
                <span>
                  <span aria-hidden="true">↑</span> Load previous
                </span>
              )}
            </PreviousLink>
            {resourcesClassName ? (
              <div
                aria-label={ariaLabel}
                className={resourcesClassName}
                role={ariaLabel ? 'region' : undefined}
              >
                {resourcesMarkup}
              </div>
            ) : (
              resourcesMarkup
            )}
            {autoLoad ? (
              <AutoLoadNext
                NextLink={NextLink}
                hasNextPage={hasNextPage}
                isLoading={isLoading}
              />
            ) : (
              <NextLink>
                {isLoading ? (
                  'Loading...'
                ) : (
                  <span>
                    Load more <span aria-hidden="true">↓</span>
                  </span>
                )}
              </NextLink>
            )}
          </div>
        );
      }}
    </Pagination>
  );
}

/**
 * Renders the Pagination NextLink but auto-clicks it whenever the sentinel
 * scrolls near the viewport, giving infinite scroll instead of a button.
 */
function AutoLoadNext({NextLink, hasNextPage, isLoading}) {
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!hasNextPage) return;
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !isLoading) {
          el.click();
        }
      },
      {rootMargin: '400px'},
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isLoading]);

  if (!hasNextPage) return null;

  return (
    <NextLink ref={ref} style={{display: 'block', textAlign: 'center'}}>
      {isLoading ? 'Loading…' : ' '}
    </NextLink>
  );
}
