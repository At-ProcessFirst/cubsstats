import EditorialCard from './EditorialCard'

/**
 * Feed of editorial insight cards with a section title.
 *
 * @param {object} props
 * @param {string} [props.title] - Section title
 * @param {Array} props.items - Array of { title, body, category, timestamp, accentColor }
 */
export default function EditorialFeed({ title, items = [] }) {
  if (!items.length) {
    return (
      <div className="bg-surface rounded-lg border border-white-8 p-4">
        {title && (
          <h3
            className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
            style={{ fontFamily: "'JetBrains Mono', monospace" }}
          >
            {title}
          </h3>
        )}
        <p className="text-sm text-text-secondary italic">
          No insights available yet
        </p>
      </div>
    )
  }

  return (
    <div>
      {title && (
        <h3
          className="text-[11px] uppercase tracking-widest text-text-secondary mb-3"
          style={{ fontFamily: "'JetBrains Mono', monospace" }}
        >
          {title}
        </h3>
      )}
      <div className="flex flex-col gap-3">
        {items.map((item, i) => (
          <EditorialCard key={i} {...item} />
        ))}
      </div>
    </div>
  )
}
