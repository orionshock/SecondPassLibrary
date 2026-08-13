# Client API authorization

This document owns the external Reader pairing and bearer-client lifecycle. It
does not define browser sessions, general API conventions, or domain policy;
those belong to [Architecture](architecture.md), [API](api.md), and the linked
domain authorities.

## Pairing contract

A Reader client requests a short-lived pairing capability, a signed-in human
approves or denies it in the Product UI, and the client consumes an approval
once. This is deliberately not OAuth or OIDC.

1. The client posts bounded client name/type metadata to
   `/api/v1/client-api/login-requests/`.
2. The response supplies a request ID, short human code, browser authorization
   URL, polling/consumption URL, expiry, and recommended polling interval.
3. The human signs in normally and approves or denies the request at the React
   Product UI pairing surface.
4. Anonymous `GET` polling reports only `pending`, `approved`, `denied`,
   `expired`, or `consumed`. It never creates a client session or returns a
   credential.
5. Once approved, one anonymous `POST` to the consumption URL atomically creates
   the client session, transitions the request to `consumed`, and returns the
   raw bearer token exactly once. Repeated or concurrent consumption cannot
   mint or return another token.

The browser never receives the bearer token. The unguessable request capability
authorizes polling and consumption; browser approval still requires an
authenticated Django session. All pairing responses, including errors, use
`Cache-Control: no-store, private` and `Pragma: no-cache`.

Public `/.well-known/secondpass` supplies compact server discovery and the API
root. Client API discovery advertises the active pairing URLs. Authenticated
`/api/v1/server/info/` refreshes server display context; `/api/v1/accounts/me/`
supplies current-user identity, memberships, and sparse user capability flags.
Exact fields remain serializer-owned.

## Stored state and abuse bounds

`ClientLoginRequest` stores hashed code material, bounded client metadata, a
hashed fingerprint, normalized source information needed for the short-lived
limit, state timestamps, and the approving user. It never stores the raw code
or bearer token. Requests expire after ten minutes.

Creation atomically permits at most five active requests per normalized source
bucket and three per bounded client fingerprint. Missing or malformed source
addresses share one bounded bucket; IPv4-mapped IPv6 normalizes to IPv4. The
source bucket is primary abuse resistance. The fingerprint is secondary
duplicate suppression and may change when punctuation or client metadata
changes. Proxy interpretation reuses the Django-owned trust boundary in
[Deployment](deployment.md#reverse-proxy-contract).

If the approving account is inactive or gone at consumption time, the request
expires without creating a session. Denied, expired, and consumed requests are
terminal. Retention and cleanup are documented in
[Operations](operations.md#client-pairing-requests).

## Bearer-session lifecycle

Successful consumption creates one `UserClientSession` for the approving user.
Only a keyed token hash is stored. Client sessions do not expire by default;
authentication honors `expires_at` when one is present and always rejects
revoked sessions or inactive users. Revocation records `revoked_at` and makes
the credential unusable immediately.

Users may list and revoke only their own active client sessions. Self-service
password changes, managed password resets, and managed user disablement revoke
the affected user's bearer sessions as part of the coordinated credential
lifecycle in [Architecture](architecture.md#browser-sessions-and-forced-password-changes).

The browser-only `must_change_password` middleware does not apply the flag to a
bearer-only request. Bearer access remains controlled by the explicit Client
API allow-list and its normal object permissions. A password change or reset
still revokes credentials that already exist.

## Bearer authority

Bearer tokens are Reader-client credentials, not browser or management
credentials. The stable authority boundary is:

| Domain | Bearer authority |
| --- | --- |
| Current user and server context | Read only |
| Library Books, axes, Groups, and EPUB download | Visibility-scoped read only |
| Marginalia | Owner-scoped reads and supported live Session/progress/annotation writes |
| Shelves | Read visible Shelves; mutate only the token user's personal Shelves |
| Library/Group/user management, imports, exports, passwords, browser sessions, Product UI, Admin | Denied; Django session required |

Bearer capabilities are an explicit allow-list. Permanent Reading Session
deletion is not an allowed client operation and requires browser-session
authentication.

An account's broad role does not expand a bearer credential into management
authority. Library reads and EPUB downloads use the same canonical visibility
boundary as browser sessions, and download rechecks uncached authority. Advanced
versus Simple Mode does not alter that Book set or suppress authorized custom
Group reads. See the immutable [Library Book Visibility](book-visibility.md)
and [Advanced Library Groups Mode](advanced-library-groups.md) policies.

Shelf access follows [Permissions](permissions.md). Group Shelves and other
users' listed Shelves are read-only through bearer authentication, even if the
same person could manage a Group Shelf through a browser session. A Shelf never
grants Book visibility.

Marginalia remains user-owned. The exact distinction between current Library
visibility, historical Marginalia, openability, and allowed writes is immutable
policy in [Marginalia-Linked Books](marginalia-book-visibility.md). Archive
import and export are session-only workflows; general lifecycle and replay
rules belong in [Marginalia](marginalia.md).

## Security and privacy rules

- Pairing codes and bearer tokens are stored only as keyed hashes; raw values
  are returned only at their one permitted boundary.
- Pairing codes, capability URLs, request UUIDs, tokens, cookies, CSRF values,
  full headers, and full User-Agent strings are never logged.
- Approval and denial are browser-session actions; polling and consumption are
  capability-authorized anonymous operations.
- Hidden objects follow the owning domain's anti-enumeration behavior. A bearer
  credential never makes storage paths, Group internals, or another user's data
  externally visible.
- Cross-origin Reader clients use bearer authentication without credentialed
  cookies. The same-origin Product UI continues to use session authentication
  and CSRF.

## Non-goals

There is no OAuth/OIDC provider, redirect-URI/custom-scheme protocol, client
secret, bearer access to Product UI/Admin, or server-hosted Reader application.
Do not generalize this bounded pairing flow into an identity platform without a
new explicit product decision.
