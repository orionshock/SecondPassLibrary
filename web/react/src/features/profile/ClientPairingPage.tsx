import { decideClientPairing, lookupClientPairing, type ClientPairingRequest } from "@second-pass/spl-api";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Button, ErrorPanel, FormField, PageHeader, Surface } from "../../components/ui";
import { normalizedError } from "./ProfilePage";

export function ClientPairingPage() {
  const [searchParams] = useSearchParams();
  const initialCode = searchParams.get("code")?.trim() ?? "";
  const initialLookupStarted = useRef(false);
  const [code, setCode] = useState(initialCode);
  const [pairing, setPairing] = useState<ClientPairingRequest>();
  const [clientName, setClientName] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<Error>();

  async function findRequest(value: string) {
    setPending(true);
    setError(undefined);
    setMessage("");
    try {
      const found = await lookupClientPairing(value);
      setPairing(found);
      setCode(found.code);
      setClientName(found.clientName);
    } catch (caught: unknown) {
      setPairing(undefined);
      setError(normalizedError(caught));
    } finally {
      setPending(false);
    }
  }

  useEffect(() => {
    if (!initialCode || initialLookupStarted.current) return;
    initialLookupStarted.current = true;
    void findRequest(initialCode);
  }, [initialCode]);

  function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void findRequest(code);
  }

  async function decide(action: "approve" | "deny") {
    if (!pairing) return;
    setPending(true);
    setError(undefined);
    try {
      const result = await decideClientPairing({
        code: pairing.code,
        action,
        ...(action === "approve" ? { clientName } : {}),
      });
      setMessage(result === "approved" ? "Client authorized. Return to your reader." : "Client request denied.");
      setPairing(undefined);
    } catch (caught: unknown) {
      setError(normalizedError(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="page-stack pairing-page">
      <nav className="breadcrumbs" aria-label="Breadcrumb">
        <Link to="/profile">Profile</Link>
        <span aria-hidden="true">/</span>
        <span>Authorize Reader Client</span>
      </nav>
      <PageHeader title="Authorize reader/client" />
      <Surface title="Client API">
        {message ? <PairingCompletion message={message} /> : <>
          <form className="form-grid pairing-form" onSubmit={lookup}>
          <FormField label="Code" htmlFor="pairing-code">
            <div className="control-stack">
              <input id="pairing-code" value={code} required autoComplete="off" onChange={(event) => setCode(event.target.value)} />
              <span className="field-help">Enter the code shown in your reader client.</span>
            </div>
          </FormField>
          {!pairing ? <PairingActionRow error={error}><Button type="submit" disabled={pending}>{pending ? "Looking up..." : "Continue"}</Button></PairingActionRow> : null}

          {pairing ? <>
            <p className="pairing-subheading">Request</p>
            <FormField label="Device/client name" htmlFor="pairing-client-name">
              <div className="control-stack">
                <input id="pairing-client-name" value={clientName} required onChange={(event) => setClientName(event.target.value)} />
                <span className="field-help">This is how this client will appear in your Profile session list.</span>
              </div>
            </FormField>
            <div className="form-field pairing-readonly-row"><span>Client type</span><span>{pairing.clientType}</span></div>
            <PairingActionRow error={error}>
              <Button type="button" className="button--secondary" disabled={pending} onClick={() => void decide("deny")}>Deny</Button>
              <Button type="button" disabled={pending || !clientName.trim()} onClick={() => void decide("approve")}>Approve</Button>
            </PairingActionRow>
          </> : null}
          </form>
        </>}
      </Surface>
    </div>
  );
}

export function PairingCompletion({ message }: { message: string }) {
  return <div className="form-action-row">
    <div className="action-feedback action-feedback--success"><p className="success-message" role="status">{message}</p></div>
    <div className="form-actions">
      <Link className="button button--secondary" to="/">Go to Home</Link>
      <Link className="button" to="/profile">Back to Profile</Link>
    </div>
  </div>;
}

function PairingActionRow({ error, children }: { error?: Error; children: ReactNode }) {
  return <div className="form-action-row">
    <div className={`action-feedback${error ? " action-feedback--error" : ""}`}>{error ? <ErrorPanel>{error.message}</ErrorPanel> : null}</div>
    <div className="form-actions">{children}</div>
  </div>;
}
