export default function BoothSuggestions({ suggestions = [], onSelect }) {
  if (!suggestions.length) return null

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s)}
          className="px-3 py-1.5 rounded-full text-[11px] border border-white-8
                     text-text-secondary hover:text-text-primary
                     hover:scale-105 transition-all duration-200 cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #141B2D, #1A2340)' }}
          style={{ fontFamily: "'DM Sans', sans-serif" }}
        >
          {s}
        </button>
      ))}
    </div>
  )
}
