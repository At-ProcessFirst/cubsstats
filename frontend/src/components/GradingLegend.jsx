import { GRADE_ORDER, GRADES } from '../utils/grading'

/**
 * Grading legend bar — appears on every page.
 * Shows all 5 grades with colors + "Benchmarks update weekly from live MLB data."
 */
export default function GradingLegend() {
  return (
    <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-surface border border-white-8">
      {GRADE_ORDER.map((key) => {
        const g = GRADES[key]
        return (
          <div key={key} className="flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: g.color }}
            />
            <span
              className="text-[9px] font-semibold tracking-wide"
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                color: g.color,
              }}
            >
              {g.label}
            </span>
          </div>
        )
      })}

      <span className="ml-auto text-[10px] text-text-secondary italic">
        Benchmarks update weekly from live MLB data
      </span>
    </div>
  )
}
