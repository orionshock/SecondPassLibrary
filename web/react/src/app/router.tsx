import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";

function LandingPage() {
  return (
    <section>
      <p className="eyebrow">React foundation</p>
      <h1>Your library, ready for its next pass.</h1>
      <p>The authenticated React Product UI shell is running.</p>
    </section>
  );
}

function PlaceholderPage() {
  return (
    <section>
      <p className="eyebrow">Coming next</p>
      <h1>This Product UI section is ready to be built.</h1>
    </section>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "*", element: <PlaceholderPage /> },
    ],
  },
]);
