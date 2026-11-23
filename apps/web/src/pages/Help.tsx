/**
 * Help (Milestone G6): the operator guide in the app. Owner's choices: opened from the "?"
 * button in the top bar; contents + sections on one scrolling page; both parts for everyone.
 * The same text (src/content/guide.json) generates docs/OPERATOR_GUIDE.md and the A4 PDFs
 * (scripts/build-guide.mjs), so the three never drift apart.
 */
import { CircleHelp, FileDown } from 'lucide-react';
import guide from '../content/guide.json';
import { useT } from '../lib/i18n';

type Lang = 'ar' | 'en';
type Text = Record<Lang, string>;
type Block =
  | { type: 'p' | 'note' | 'warn'; ar: string; en: string }
  | { type: 'steps' | 'list'; ar: string[]; en: string[] };
interface Section {
  id: string;
  title: Text;
  image?: string;
  body: Block[];
}
interface Part {
  id: string;
  title: Text;
  sections: Section[];
}

const parts = guide.parts as Part[];

function BlockView({ block, lang }: { block: Block; lang: Lang }) {
  if (block.type === 'steps' || block.type === 'list') {
    const items = block[lang];
    const cls = 'space-y-1.5 ps-5 text-sm text-[#e5e2e1] leading-relaxed';
    return block.type === 'steps' ? (
      <ol className={`${cls} list-decimal`}>{items.map((x, i) => <li key={i}>{x}</li>)}</ol>
    ) : (
      <ul className={`${cls} list-disc`}>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    );
  }
  const text = block[lang];
  if (block.type === 'p') return <p className="text-sm text-[#e5e2e1] leading-relaxed">{text}</p>;
  const warn = block.type === 'warn';
  return (
    <p
      className={`text-sm leading-relaxed rounded-lg border-s-4 px-3 py-2 ${
        warn ? 'border-[#ff9f43] bg-[#ff9f43]/10 text-[#ffd8b0]' : 'border-[#00e5ff] bg-[#00e5ff]/10 text-[#bdf6ff]'
      }`}
    >
      {text}
    </p>
  );
}

export default function HelpPage() {
  const { t, lang } = useT();
  const l = lang as Lang;
  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <CircleHelp size={24} className="text-[#00e5ff]" aria-hidden="true" /> {t('nav.help')}
          </h1>
          <p className="text-sm text-[#849396] mt-1 max-w-2xl">{guide.intro[l]}</p>
        </div>
        <a
          href={`/guide/operator-guide-${l}.pdf`}
          download
          className="flex items-center gap-1.5 px-3 py-2 min-h-11 rounded-lg border border-white/10 text-sm text-[#bac9cc] hover:bg-white/5"
        >
          <FileDown size={16} aria-hidden="true" /> {t('help.print')}
        </a>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)] items-start">
        <nav aria-label={t('help.contents')} className="panel p-3 lg:sticky lg:top-0 text-sm space-y-3">
          <div className="text-xs font-bold text-[#849396]">{t('help.contents')}</div>
          {parts.map((part) => (
            <div key={part.id} className="space-y-1">
              <a href={`#${part.id}`} className="block font-bold text-[#00e5ff]">
                {part.title[l]}
              </a>
              <ul className="space-y-0.5">
                {part.sections.map((s) => (
                  <li key={s.id}>
                    <a href={`#${s.id}`} className="block py-1 text-[#bac9cc] hover:text-[#e5e2e1]">
                      {s.title[l]}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="space-y-8 min-w-0">
          {parts.map((part) => (
            <section key={part.id} id={part.id} aria-labelledby={`${part.id}-h`} className="space-y-4 scroll-mt-4">
              <h2 id={`${part.id}-h`} className="text-xl font-bold text-[#00e5ff]">
                {part.title[l]}
              </h2>
              {part.sections.map((s) => (
                <article key={s.id} id={s.id} className="panel p-4 sm:p-5 space-y-3 scroll-mt-4">
                  <h3 className="text-lg font-bold">{s.title[l]}</h3>
                  {s.image && (
                    <img
                      src={`/${s.image}`}
                      alt={s.title[l]}
                      loading="lazy"
                      className="rounded-xl border border-white/10 max-h-[28rem] w-auto max-w-full mx-auto"
                    />
                  )}
                  {s.body.map((b, i) => (
                    <BlockView key={i} block={b} lang={l} />
                  ))}
                </article>
              ))}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
