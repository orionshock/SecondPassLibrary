import type { ClientPairingRequest } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { Button, FormField } from "../../../components/UiPrimitives";
import { ActionRow } from "../../../shared/forms/ActionRow";
import { PairingPageFrame } from "../components/PairingPageFrame";

export function PairingRequestPageRegion({ code, pairing, clientName, pending, error, onCodeChange, onClientNameChange, onLookup, onDecision }: {
  code: string;
  pairing?: ClientPairingRequest;
  clientName: string;
  pending: boolean;
  error?: Error;
  onCodeChange: (value: string) => void;
  onClientNameChange: (value: string) => void;
  onLookup: () => void;
  onDecision: (action: "approve" | "deny") => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onLookup(); }
  const actionState = { pending, error };
  return <PairingPageFrame><form className="form-grid pairing-form" onSubmit={submit}>
    <FormField label="Code" htmlFor="pairing-code"><div className="control-stack"><input id="pairing-code" value={code} required autoComplete="off" onChange={(event) => onCodeChange(event.target.value)} /><span className="field-help">Enter the code shown in your reader client.</span></div></FormField>
    {!pairing ? <ActionRow state={actionState}><Button type="submit" disabled={pending}>{pending ? "Looking up..." : "Continue"}</Button></ActionRow> : null}
    {pairing ? <>
      <p className="pairing-subheading">Request</p>
      <FormField label="Device/client name" htmlFor="pairing-client-name"><div className="control-stack"><input id="pairing-client-name" value={clientName} required onChange={(event) => onClientNameChange(event.target.value)} /><span className="field-help">This is how this client will appear in your Profile session list.</span></div></FormField>
      <div className="form-field pairing-readonly-row"><span>Client type</span><span>{pairing.clientType}</span></div>
      <ActionRow state={actionState}><Button type="button" tone="secondary" disabled={pending} onClick={() => onDecision("deny")}>Deny</Button><Button type="button" disabled={pending || !clientName.trim()} onClick={() => onDecision("approve")}>Approve</Button></ActionRow>
    </> : null}
  </form></PairingPageFrame>;
}
