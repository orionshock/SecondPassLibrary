import { decideClientPairing, lookupClientPairing, type ClientPairingRequest } from "@second-pass/spl-api";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Button, ErrorPanel, FormField, PageHeader, Surface } from "../../components/ui";
import { normalizedError } from "./ProfilePage";

export function ClientPairingPage() {
  const [code, setCode] = useState("");
  const [pairing, setPairing] = useState<ClientPairingRequest>();
  const [clientName, setClientName] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<Error>();

  async function lookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(undefined); setMessage("");
    try { const found = await lookupClientPairing(code); setPairing(found); setCode(found.code); setClientName(found.clientName); }
    catch (caught: unknown) { setPairing(undefined); setError(normalizedError(caught)); }
    finally { setPending(false); }
  }
  async function decide(action: "approve" | "deny") {
    if (!pairing) return; setPending(true); setError(undefined);
    try { const result = await decideClientPairing({ code: pairing.code, action, ...(action === "approve" ? { clientName } : {}) }); setMessage(result === "approved" ? "Client paired. Return to the reader client." : "Pairing request denied."); setPairing(undefined); }
    catch (caught: unknown) { setError(normalizedError(caught)); }
    finally { setPending(false); }
  }
  return <div className="page-stack profile-page"><PageHeader eyebrow="Connected clients" title="Pair a client" actions={<Link to="/profile">Back to profile</Link>} />
    <Surface><form className="form-grid" onSubmit={lookup}><FormField label="Pairing code" htmlFor="pairing-code"><input id="pairing-code" value={code} required autoComplete="off" onChange={(event) => setCode(event.target.value)} /></FormField><div className="form-actions form-actions--right"><Button type="submit" disabled={pending}>{pending ? "Looking up..." : "Find request"}</Button></div></form></Surface>
    {pairing ? <Surface title="Pairing request"><div className="form-grid"><FormField label="Client type" htmlFor="pairing-client-type"><input id="pairing-client-type" value={pairing.clientType} readOnly /></FormField><FormField label="Client name" htmlFor="pairing-client-name"><input id="pairing-client-name" value={clientName} required onChange={(event) => setClientName(event.target.value)} /></FormField><div className="form-actions form-actions--right"><Button className="button--secondary" disabled={pending} onClick={() => void decide("deny")}>Deny</Button><Button disabled={pending || !clientName.trim()} onClick={() => void decide("approve")}>Approve</Button></div></div></Surface> : null}
    {error ? <ErrorPanel>{error.message}</ErrorPanel> : null}{message ? <p className="success-message" role="status">{message}</p> : null}
  </div>;
}
