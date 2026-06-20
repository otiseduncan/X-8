import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './app/App';
import './styles.css';
import './app/ideEnhancements.css';
import './app/ideEnhancements';
import './app/artifactWorkbenchCompact.css';
import './app/artifactSolidIde.css';
import './app/artifactCommandCleanReplies.css';

const root = document.getElementById('root') as HTMLElement;

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
