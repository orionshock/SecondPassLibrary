import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";

function LandingPage() {
  return (
    <section>
      <p className="eyebrow">React foundation</p>
      <h1>Your library, ready for its next pass.</h1>
      <p>The new Product UI shell is running. Existing Django pages remain unchanged.</p>
    </section>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [{ index: true, element: <LandingPage /> }],
  },
]);
