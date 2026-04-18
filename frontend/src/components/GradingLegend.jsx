import { GRADE_ORDER, GRADES } from '../utils/grading'

export default function GradingLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2 md:gap-3 px-3 md:px-4 py-2 rounded-lg bg-surface border border-white-8">
      <span
        className="text-[9px] md:text-[10px] uppercase tracking-widest text-text-secondary font-semibold mr-1"
        style={{ fontFamily: "'JetBrains Mono', monospace" }}
      >
        Grades:
      </span>
      {GRADE_ORDER.map((key) => {
        const g = GRADES[key]
        return (
          <div key={key} className="flex items-center gap-1 md:gap-1.5">
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: g.color }}
            />
            <span
              className="text-[8px] md:text-[9px] font-semibold tracking-wide"
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

      <span className="basis-full md:basis-auto md:ml-auto text-[9px] md:text-[10px] text-text-secondary italic mt-1 md:mt-0">
        Benchmarks update weekly from live MLB data
      </span>
    </div>
  )
}
