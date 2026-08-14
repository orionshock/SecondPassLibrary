import { createUser, type CreateUserResult } from "@second-pass/spl-api";
import { useReducer, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel } from "../../components/UiPrimitives";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import { UserCreateFormPageRegion } from "./regions/UserCreateFormPageRegion";
import { UserCreateSuccessPageRegion } from "./regions/UserCreateSuccessPageRegion";
import { createUserInputFromDraft, emptyUserCreateDraft, userCreateDraftReducer } from "./userCreateForm";
import { creatableUserRoles } from "./userCreateRoles";
import { usersCreateBreadcrumbFallback } from "./usersBreadcrumbs";
import "./Users.css";

export function UserCreateOrchestrator() {
  usePageBreadcrumbs(usersCreateBreadcrumbFallback);
  const { currentUser } = useOutletContext<AppOutletContext>();
  const roles = creatableUserRoles(currentUser);
  const [draft, dispatch] = useReducer(userCreateDraftReducer, emptyUserCreateDraft);
  const [state, setState] = useState<MutationState>(idleMutationState);
  const [result, setResult] = useState<CreateUserResult>();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (roles.length === 0 || !roles.includes(draft.role)) return;
    setState({ pending: true });
    try {
      const created = await createUser(createUserInputFromDraft(draft));
      dispatch({ type: "reset" });
      setResult(created);
      setState(idleMutationState);
    } catch (error: unknown) {
      setState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  return <ProductPageShell className="users-page" title="Create User">
    {roles.length === 0 ? <ErrorPanel>You do not have permission to create users.</ErrorPanel> : result
      ? <UserCreateSuccessPageRegion result={result} />
      : <UserCreateFormPageRegion
          draft={draft}
          roles={roles}
          state={state}
          onChange={(field, value) => dispatch({ type: "change", field, value })}
          onSubmit={submit}
        />}
  </ProductPageShell>;
}
