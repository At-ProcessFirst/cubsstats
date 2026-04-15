export default function BoothSuggestions({ suggestions = [], onSelect }) {
  if (!suggestions.length) return null

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s)}
          className="px-3 py-1.5 rounded-full text-[11px] bg-surface border border-white-8
                     text-text-secondary hover:text-text-primary hover:bg-surface-hover
                     transition-colors cursor-pointer"
          style={{ fontFamily: "'DM Sans', sans-serif" }}
        >
          {s}
        </button>
      ))}
    </div>
  )
}
