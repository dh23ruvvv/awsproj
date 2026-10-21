import type { ReactElement } from 'react';

/** Render the placeholder ambient scheduling surface. */
export default function App(): ReactElement {
  return (
    <main aria-labelledby="app-title">
      <h1 id="app-title">FlowPilot</h1>
      <div className="utterance-bar" role="region" aria-labelledby="utterance-title">
        <h2 id="utterance-title">Utterance bar</h2>
        <p>Your scheduling request will appear here.</p>
      </div>
      <div className="timeline" role="region" aria-labelledby="timeline-title">
        <h2 id="timeline-title">Schedule timeline</h2>
        <p>Your schedule will appear here.</p>
      </div>
      <div className="response-line" role="region" aria-labelledby="response-title">
        <h2 id="response-title">Response line</h2>
        <p>The agent response will appear here.</p>
      </div>
      <div className="plan-preview" role="region" aria-labelledby="plan-title">
        <h2 id="plan-title">Plan preview</h2>
        <p>A proposed plan will appear here.</p>
      </div>
    </main>
  );
}
