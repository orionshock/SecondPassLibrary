import type { CreateUserResult } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { ActionFeedbackComponent } from "../../../shared/feedback/ActionFeedbackComponent";
import { TemporaryPasswordResultComponent } from "../../../shared/TemporaryPasswordResultComponent";
import { UserInlineIdentityComponent } from "../../../shared/users/UserInlineIdentityComponent";
import { usersEditBreadcrumbTrail } from "../usersBreadcrumbs";

export function UserCreateSuccessPageRegion({ result }: { result: CreateUserResult }) {
  return <section className="user-create-result" aria-live="polite">
    <h2>User created</h2>
    <dl className="user-create-result__details">
      <div><dt>Username</dt><dd><UserInlineIdentityComponent username={result.user.username} /></dd></div>
      <div><dt><label htmlFor="created-user-temporary-password">Temporary credentials</label></dt><dd><TemporaryPasswordResultComponent id="created-user-temporary-password" username={result.user.username} password={result.temporaryPassword} /></dd></div>
    </dl>
    <div className="form-action-row">
      <ActionFeedbackComponent state={{ pending: false, message: "User created." }} />
      <div className="form-actions">
        <Link className="button button--secondary" to="/users">Back to Users</Link>
        <Link className="button" to={`/users/${encodeURIComponent(result.user.id)}/edit`} state={breadcrumbNavigationState(usersEditBreadcrumbTrail(result.user.username))}>Edit user</Link>
      </div>
    </div>
  </section>;
}
