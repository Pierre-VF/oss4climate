# Security Analysis: `src/`

## CRITICAL

### C1: Command Injection

- **File:** `oss4climate_scripts/scripts/__init__.py:34`
- **Issue:** `os.system(f"black {file_path}")` passes a file path directly to the shell without escaping. If `file_path` is attacker-controlled (it is a public parameter), commands can be injected via `;`, `&`, or `$()`. For example, a path like `/tmp/evil; rm -rf /` would execute arbitrary commands.
- **Fix:** Replace with `subprocess.run(["black", file_path], check=True)`.

---

## HIGH

### H1: Reflected XSS in JavaScript Context

- **File:** `oss4climate_app/templates/v2/results.html:100-104`
- **Issue:** Query parameters are interpolated into JavaScript string literals:

  ```javascript
  var licenseValue = "{{ request.query_params.get('license_category', '*') }}";
  ```

  Jinja2 HTML-escapes for HTML context, but inside a JS string a value like `';alert(document.cookie);//` breaks out of the string and executes arbitrary JavaScript. Same pattern on lines 28, 31-35 (HTML attribute context), and line 71 (data attribute).
- **Fix:** Use `{{ value | tojson }}` for JS context values. For HTML attributes, ensure proper quoting (current usage is safe in HTML attribute context since Jinja2 auto-escapes, but the JS context is not).

### H2: No Security Headers or CORS Middleware

- **File:** `oss4climate_app/src/routers/api.py:32-41`
- **Issue:** The FastAPI app configures zero middleware. Missing: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options`, `Strict-Transport-Security`, and CORS policy.
- **Fix:** Add `TrustedHostMiddleware`, `CORSMiddleware`, and security header middleware.

### H3: MCP Server Has No Authentication

- **File:** `oss4climate_app/src/mcp_server/__init__.py:14-16`
- **Issue:** The MCP endpoint exposes search tools with zero authentication. Anyone with network access can query the full project database.
- **Fix:** Add API key authentication or restrict to localhost/internal network.

---

## MEDIUM

### M1: Timing-Attack Vulnerable Secret Comparison

- **File:** `oss4climate_app/src/routers/api.py:91`
- **Issue:** `key != SETTINGS.DATA_REFRESH_KEY` uses standard string comparison, which is not constant-time. An attacker could brute-force the key character by character via response timing.
- **Fix:** Use `secrets.compare_digest(key, SETTINGS.DATA_REFRESH_KEY)`.

### M2: Admin Key Exposed in URL Query Params

- **File:** `oss4climate_app/src/routers/api.py:98, 114, 126`
- **Issue:** The admin `key` parameter appears in URLs for `/refresh_data`, `/download_request_metrics`, and `/download_search_metrics`. URLs are logged in browser history, proxy logs, and server access logs.
- **Fix:** Accept the key via an `Authorization` header or POST body instead.

### M3: Raw PII Stored in Logs

- **File:** `oss4climate_app/src/log_activity.py:18-24, 31-35`
- **Issue:** Raw search terms and full referer headers (which may contain auth tokens, API keys, or sensitive query strings) are stored without sanitization.
- **Fix:** Strip query strings from referers. Consider hashing or anonymizing search terms.

### M4: Search History Exportable as CSV

- **File:** `oss4climate_app/src/routers/api.py:113-134`
- **Issue:** Full CSV dumps of search logs (including user search terms) are downloadable via authenticated endpoints. Even with auth, this is a data exposure risk.
- **Fix:** Anonymize data before export. Add audit logging for these endpoints.

### M5: Plain FTP (Cleartext Credentials)

- **File:** `oss4climate_scripts/scripts/data_publication.py:45-48`
- **Issue:** Plain `ftplib.FTP` transmits credentials and data in cleartext.
- **Fix:** Replace with `ftplib.FTP_TLS` or paramiko SFTP.

### M6: SSRF via `urlretrieve`

- **File:** `oss4climate_app/src/data_io.py:24`
- **Issue:** `urlretrieve(url, target)` has no URL scheme validation, timeout, or certificate pinning. If the URL source is compromised, internal URLs (`file://`, `http://localhost`) could be targeted. Currently URLs come from config constants (low practical risk), but the function is public.
- **Fix:** Validate URL scheme (https only), add timeouts, and consider using `aiohttp` with a trusted certificate store.

---

## LOW

### L1: `| safe` Filter on THEME_CSS

- **File:** `oss4climate_app/templates/v2/_base.html:20`
- **Issue:** `{{ THEME_CSS | safe }}` bypasses auto-escaping. Low risk since `THEME_CSS` is generated server-side from `theme.py`, but becomes an XSS vector if theme generation ever accepts external input.

### L2: No SRI on External Script

- **File:** `oss4climate_app/templates/v2/_base.html:13`
- **Issue:** The Umami analytics script at `cloud.umami.is/script.js` has no Subresource Integrity hash. If the CDN is compromised, arbitrary JS could be injected.

### L3: Empty String Defaults for Secrets

- **File:** `oss4climate/src/config.py:36-37`
- **Issue:** `TYPESENSE_API_KEY` and `TYPESENSE_HOST` default to empty strings rather than failing loudly on misconfiguration.

### L4: No Rate Limiting on Search

- **File:** `oss4climate_app/src/routers/api.py`, `routers/ui.py`
- **Issue:** No rate limiting on `/search` or `/results`. An attacker could exhaust Typesense resources or generate excessive log entries.

### L5: Bare Except Swallows All Exceptions

- **File:** `oss4climate_scripts/scripts/data_publication.py:52`
- **Issue:** `except: pass` on line 52 swallows all exceptions including `KeyboardInterrupt` and `SystemExit`.

### L6: Bug: `str.__name__` Raises AttributeError

- **File:** `oss4climate_scripts/scripts/data_publication.py:33, 37`
- **Issue:** `f"{i.__name__} must be defined..."` -- strings have no `__name__` attribute. This raises `AttributeError` instead of the intended `EnvironmentError`, making the validation dead code.

### L7: `TemplateResponse` Args in Wrong Order

- **File:** `oss4climate_app/src/templates.py:32-33`
- **Issue:** `TemplateResponse(request, template_file, resp, ...)` passes `request` as the first positional arg where `name` (template name) is expected. The arguments are in the wrong order -- `request` should be a keyword argument. This is a functional bug that may cause incorrect template rendering.

---

## Positives

- **SQL injection prevented:** SQLModel (ORM) is used for all database queries, preventing SQL injection.
- **Jinja2 auto-escaping enabled:** FastAPI's `Jinja2Templates` defaults to `autoescape=True`, mitigating stored XSS from database data in HTML context.
- **No file upload endpoints:** Eliminates a common attack surface.
- **No user auth system:** Nothing to compromise in terms of user credentials.
- **GET-only routes:** Eliminates CSRF risk.
- **`.env` properly gitignored:** No secrets committed to the repository.
- **Dependencies reasonably pinned:** Security-sensitive packages (cryptography, urllib3, starlette) are at recent versions.

---

## Priority Remediation Order

| Priority | Fix | Effort |
|----------|-----|--------|
| 1 | Replace `os.system()` with `subprocess.run()` (C1) | 5 min |
| 2 | Use `\| tojson` for JS context values in results.html (H1) | 15 min |
| 3 | Add security headers middleware (H2) | 30 min |
| 4 | Add auth to MCP endpoint or restrict to localhost (H3) | 30 min |
| 5 | Use `secrets.compare_digest()` for key comparison (M1) | 5 min |
| 6 | Move admin key from query param to header (M2) | 30 min |
| 7 | Replace plain FTP with FTP_TLS (M5) | 15 min |
| 8 | Fix the `TemplateResponse` argument order (L7) | 5 min |
| 9 | Fix the dead-code bug in FTP validation (L6) | 5 min |
