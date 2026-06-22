import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import { CockpitWindow } from './app/CockpitWindow';
import './styles.css';

const RootApp = window.location.pathname.startsWith('/cockpit') ? CockpitWindow : App;

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <RootApp />
  </React.StrictMode>
);
