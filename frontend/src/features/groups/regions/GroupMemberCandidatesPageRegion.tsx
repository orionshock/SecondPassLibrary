import type { Page, UserChoice } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { Button, ErrorPanel } from "../../../components/ui";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { UserInlineIdentityComponent } from "../../../shared/users/UserInlineIdentityComponent";

export function GroupMemberCandidatesPageRegion({ search, page, pageNumber, pageSize, loading, error, pendingProfileId, controlsDisabled, onSearchChange, onSearch, onAdd, onPageChange, onPageSizeChange, onRetry }: {
  search: string;
  page?: Page<UserChoice>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  pendingProfileId?: string;
  controlsDisabled?: boolean;
  onSearchChange: (value: string) => void;
  onSearch: () => void;
  onAdd: (choice: UserChoice) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSearch();
  }

  return <section className="group-member-candidates-region" aria-label="Add group members">
    <h2>Add member</h2>
    <form className="group-edit-member-search" role="search" onSubmit={submit}>
      <label htmlFor="group-add-members-search">Search</label>
      <input id="group-add-members-search" value={search} placeholder="Username..." onChange={(event) => onSearchChange(event.target.value)} />
      <Button type="submit">Search</Button>
    </form>
    {!page && !loading && !error ? <p className="muted">Search for active users to add.</p> : null}
    {!page && loading ? <div className="group-edit-section-state" aria-live="polite" aria-busy="true">Searching...</div> : null}
    {!page && error ? <div className="group-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page ? <div className="group-member-candidates" aria-busy={loading}>
      {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
      {page.items.length === 0 ? <p className="muted">No matching users.</p> : <div className="group-member-candidate-rows">
        {page.items.map((choice) => <div className="group-member-candidate-row" key={choice.profileId}>
          <UserInlineIdentityComponent username={choice.username} />
          <Button type="button" disabled={controlsDisabled || Boolean(pendingProfileId)} onClick={() => onAdd(choice)}>
            {pendingProfileId === choice.profileId ? "Adding..." : "Add"}
          </Button>
        </div>)}
      </div>}
      <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Users" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
    </div> : null}
  </section>;
}
