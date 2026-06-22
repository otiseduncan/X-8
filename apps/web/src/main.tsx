import React, { Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';

const ChatApp = React.lazy(() => import('./app/App').then((module) => ({ default: module.App })));
const CockpitApp = React.lazy(() => import('./app/CockpitWindow').then((module) => ({ default: module.CockpitWindow })));

const searchParams = new URLSearchParams(window.location.search);
const isCockpitSurface =
  window.location.pathname.startsWith('/cockpit') ||
  window.location.port === '6022' ||
  searchParams.get('surface') === 'cockpit';

const RootApp = isCockpitSurface ? CockpitApp : ChatApp;

function BootFallback() {
  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#05070d', color: '#f8fafc', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <section style={{ border: '1px solid rgba(125, 211, 252, 0.25)', borderRadius: 18, padding: 24, background: 'rgba(15, 23, 42, 0.84)' }}>
        Loading X8 surface…
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <Suspense fallback={<BootFallback />}>
      <RootApp />
    </Suspense>
  </React.StrictMode>
);
