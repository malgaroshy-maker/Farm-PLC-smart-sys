import { Component, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useT } from '../lib/i18n';

function Failed() {
  const { t } = useT();
  return (
    <div role="alert" className="panel p-5 max-w-md mx-auto mt-8 text-center space-y-3">
      <p className="text-sm text-[#e5e2e1]">{t('page.failed')}</p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="px-4 py-2 rounded-xl bg-[#00e5ff] text-[#0e0e0e] text-sm font-bold"
      >
        {t('page.reload')}
      </button>
    </div>
  );
}

class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? <Failed /> : this.props.children;
  }
}

/** A page that cannot load or crashes must not take STOP ALL and the menu with it. */
export default function PageBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return <Boundary key={pathname}>{children}</Boundary>;
}
