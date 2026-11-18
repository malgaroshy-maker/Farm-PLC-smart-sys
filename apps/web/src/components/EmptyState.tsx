/** Calm illustrated empty state (art approved in design/samples-r2). */
export default function EmptyState({ art, text }: { art: 'alarms' | 'events'; text: string }) {
  return (
    <div className="flex flex-col items-center gap-4 py-10 px-4 text-center">
      <img src={`/art/empty_${art}.webp`} alt="" className="w-56 max-w-full rounded-2xl opacity-90 shadow-lg" loading="lazy" />
      <p className="text-sm text-[#bac9cc] max-w-xs">{text}</p>
    </div>
  );
}
