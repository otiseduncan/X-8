import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import { CockpitWindow } from './app/CockpitWindow';
import './styles.css';

const searchParams = new URLSearchParams(window.location.search);
const isCockpitSurface =
  window.location.pathname.startsWith('/cockpit') ||
  window.location.port === '6022' ||
  searchParams.get('surface') === 'cockpit';

const RootApp = isCockpitSurface ? CockpitWindow : App;

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <RootApp />
  </React.StrictMode>
);
