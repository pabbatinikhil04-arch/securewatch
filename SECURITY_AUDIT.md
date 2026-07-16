# Security Checklist Audit — SecureWatch

Checked against the actual code in this repo as of this update. ✅ = implemented, ⚠️ = partial / needs action from you, ❌ = not implemented.

| # | Item | Status | Where / Notes |
|---|------|--------|----------------|
| 1 | HTTPS everywhere | ⚠️ | `nginx.conf` sends HSTS and has a commented-out HTTP→HTTPS redirect block, but **no TLS termination is configured** — you must add a certificate (e.g. via a reverse proxy like Caddy/Traefik, or certbot) before this is production-ready. Locally over HTTP this is expected to still work. |
| 2 | Validate every input | ✅ | `schemas.py` (Pydantic `field_validator`s for username/password/email/url/name) + HTML5 `required`/`minlength`/`maxlength`/`type=url` on the frontend forms (UX only, not a security boundary — server-side validation is what actually protects you). |
| 3 | Prevent SQL injection | ✅ | All queries go through SQLAlchemy's ORM (`db.query(...).filter(...)`) with no raw string concatenation anywhere. |
| 4 | Prevent XSS | ✅ | `app.js` renders all server data through `escapeHtml()` before inserting into the DOM — website names/URLs/alert text are escaped. |
| 5 | CSRF protection | ✅ (by design) | The app uses a `Bearer` token in an `Authorization` header, not cookies, for authenticated requests — CSRF specifically exploits *cookie*-based auth being sent automatically by the browser, which doesn't apply here. If you ever switch to cookie-based sessions, add CSRF tokens then. |
| 6 | Strong authentication | ✅ | `schemas.py` enforces 12+ char passwords with letters+numbers; `models.py` hashes with bcrypt via `passlib`; plaintext passwords are never stored. |
| 7 | Secure sessions | ⚠️ | Frontend now stores the JWT in `sessionStorage` (cleared when the tab closes) instead of `localStorage`, which is an improvement, but it's still JS-readable and thus vulnerable to theft via XSS. Token expiry is enforced server-side (`ACCESS_TOKEN_EXPIRE_MINUTES`). For stronger protection, move to an `HttpOnly` + `Secure` + `SameSite=Strict` cookie — that's a bigger backend change (needs CSRF tokens added back in) so it's flagged here rather than done silently. |
| 8 | Role-based access control | ✅ | `auth.py` → `require_role()`, used in `main.py` on `/api/admin/users`. Enforced server-side, not just hidden in the UI. |
| 9 | File upload security | N/A | This app has no file upload feature. If you add one, allow-list extensions/content-type, cap size, rename on save, and scan uploads. |
| 10 | API security (JWT/OAuth, keys, rate limiting) | ✅ | JWT via `python-jose` (`auth.py`); rate limiting via `RateLimitMiddleware` in `middleware.py` (5/min on login, 10/min on register, 100/min default). No secrets are exposed in frontend JS. |
| 11 | Store secrets properly | ✅ (now) | `docker-compose.yml` no longer hardcodes `postgres/postgres` or a default `SECRET_KEY` — it requires them via a `.env` file (`${SECRET_KEY:?...}` fails the build if unset). Copy `.env.example` → `.env` and fill in real values; `.env` should be in `.gitignore` and never committed. |
| 12 | Rate limiting | ✅ | See #10. |
| 13 | Prevent clickjacking | ✅ | `X-Frame-Options: DENY` sent by both the backend (`middleware.py`) and now the frontend (`nginx.conf`) — previously only the API sent it, so the static site itself was unprotected. |
| 14 | Content Security Policy | ✅ | Backend already sent `default-src 'self'`. Added the same to `nginx.conf` for the frontend, scoped a bit further (`script-src 'self'`, `style-src 'self' 'unsafe-inline'` since the CSS is inline-free but kept for safety, `connect-src 'self'`). |
| 15 | Secure headers | ✅ | Both backend and frontend now send `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `CSP`, `HSTS`. |
| 16 | Encrypt sensitive data | ✅ | Only credential data stored is the bcrypt password hash. No PII like card numbers/government IDs is collected by this app. |
| 17 | Logging | ✅ | `logging_config.py` + calls in `main.py` log registrations, logins, and failed logins — with an explicit convention comment not to log passwords/tokens/OTPs. |
| 18 | Error messages don't leak internals | ✅ | API responses use generic `HTTPException(detail=...)` messages ("Invalid credentials", "Could not validate credentials") rather than raw stack traces or DB errors. |
| 19 | Keep dependencies updated | ⚠️ | `requirements.txt` versions are pinned (good for reproducibility) but pins age — you need to periodically run `pip list --outdated` / `pip-audit` and bump them. Not something a one-time code review can guarantee going forward. |
| 20 | Backups | ❌ | No backup strategy is configured in this repo (it's infra/ops, not app code). At minimum, schedule `pg_dump` of the `postgres_data` volume and store source in a remote git repo. |

## The actual bug you reported
The Dashboard/Websites/Alerts nav links were plain anchor tags (`#dashboard`, `#websites`, `#alerts`) with **no JavaScript listening for clicks** and only one visible section in the HTML — so the URL hash changed but nothing on screen ever did. Fixed by:
- Splitting the page into three `<section class="view">` blocks (`dashboard-view`, `websites-view`, `alerts-view`).
- Adding a `showView()` router in `app.js` that toggles the active section/nav-link, keeps the URL hash in sync (so back/forward and bookmarking work), and reloads that view's data.

## Other changes made while fixing this
- **CORS**: `main.py` was using `allow_origins=["*"]` together with `allow_credentials=True`, which is a well-known misconfiguration (it lets Starlette reflect *any* origin back with credentials allowed). Replaced with an explicit allow-list read from `ALLOWED_ORIGINS`.
- **Same-origin API calls**: `nginx.conf` now reverse-proxies `/api/*` to the backend container, so `app.js` calls a relative `/api` path instead of a hardcoded `http://localhost:8000`. This also means the frontend works if you deploy it anywhere, not just `localhost`.
- **New color palette**: teal/indigo theme (see `style.css` `:root` variables) replacing the previous purple, plus status-colored pills for website state and clearer critical-alert styling.

## Not done (needs a decision from you, not just code)
- Real TLS certificate + HTTPS redirect (needs a domain + cert).
- Moving JWT storage to an `HttpOnly` cookie (bigger change, needs CSRF tokens added).
- Automated dependency/vulnerability scanning (`pip-audit`, `npm audit`-equivalent, Trivy on the Docker images) — recommend wiring one of these into CI.
- Backup automation.
