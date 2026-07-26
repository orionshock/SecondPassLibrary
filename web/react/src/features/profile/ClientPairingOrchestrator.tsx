import { decideClientPairing, lookupClientPairing, type ClientPairingRequest } from "@second-pass/spl-api";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { clientPairingBreadcrumbFallback } from "../../app/navigation/accountBreadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import "../../shared/layout/AccountPageLayout.css";
import "./ClientPairing.css";
import { PairingCompletionPageRegion } from "./regions/PairingCompletionPageRegion";
import { PairingRequestPageRegion } from "./regions/PairingRequestPageRegion";

export function ClientPairingOrchestrator() {
  usePageBreadcrumbs(clientPairingBreadcrumbFallback);
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
      setError(normalizeMutationError(caught));
    } finally {
      setPending(false);
    }
  }

  useEffect(() => {
    if (!initialCode || initialLookupStarted.current) return;
    initialLookupStarted.current = true;
    void findRequest(initialCode);
  }, [initialCode]);

  async function decide(action: "approve" | "deny") {
    if (!pairing) return;
    setPending(true);
    setError(undefined);
    try {
      const result = await decideClientPairing({ code: pairing.code, action, ...(action === "approve" ? { clientName } : {}) });
      setMessage(result === "approved" ? "Client authorized. Return to your reader." : "Client request denied.");
      setPairing(undefined);
    } catch (caught: unknown) {
      setError(normalizeMutationError(caught));
    } finally {
      setPending(false);
    }
  }

  return message
    ? <PairingCompletionPageRegion message={message} />
    : <PairingRequestPageRegion
        code={code}
        pairing={pairing}
        clientName={clientName}
        pending={pending}
        error={error}
        onCodeChange={setCode}
        onClientNameChange={setClientName}
        onLookup={() => void findRequest(code)}
        onDecision={(action) => void decide(action)}
      />;
}
