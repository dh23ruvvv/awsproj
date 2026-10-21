import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';

/** Mount the frontend in its required HTML root. */
const rootElement: HTMLElement | null = document.getElementById('root');

if (rootElement === null) {
  throw new Error('FlowPilot root element is missing.');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
