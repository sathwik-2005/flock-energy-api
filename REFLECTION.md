# Reflection

**What assumptions did you make?**

The biggest one was treating the login endpoint's JSON response
(`{"type":"redirect","status":303,...}`) as SvelteKit's own form-action
convention rather than a real HTTP redirect — the actual response is a
plain 200, and the "303" inside the JSON body is just data telling the
browser's router where to navigate next. I also assumed the ~336-row,
~7-day window returned by the energy endpoint is a genuine server-side
limit rather than something adjustable via query params I hadn't found,
since no `from`/`to`/`page` parameters appeared anywhere in the request.
Finally, I assumed `search?q=""` paginating through all 403 meters is
the intended way to enumerate the full dataset, rather than there being
a separate bulk/export endpoint I hadn't discovered.

**Which part was the most difficult, and how did you get unstuck?**

Two things, both around guessing at structure instead of checking it
directly. First, the login kept failing with a 403 ("Cross-site POST
form submissions are forbidden") even with the exact right credentials
— it turned out the portal's SvelteKit backend enforces a same-origin
check via `Origin`/`Referer` headers, which a browser sends automatically
but a bare `httpx` client doesn't. I only found this by reading the
actual error message closely rather than assuming the credentials or
request format were wrong.

Second, and more instructive: the network hierarchy breadcrumb on the
meter detail page. My first attempt used `soup.find("nav")`, which
silently grabbed the *wrong* `<nav>` element (the page's own top nav bar
— "Meters | Transformers" — which comes earlier in the document than the
real breadcrumb). It didn't error, it just returned wrong data, which is
a worse failure mode than a crash. My second attempt tried to be clever
and match on the hierarchy code patterns instead (`(Z-03)`, `(C-06)`,
etc.) without actually looking at the DOM — that didn't work either. What
actually fixed it was opening DevTools, right-clicking the real
breadcrumb text, and inspecting the actual HTML, which showed the
breadcrumb *is* a plain `<nav>` — just not the first one in the
document. Scoping the selector to `main nav` fixed it immediately. The
lesson: when scraping, look at the real markup before guessing at a
selector, even when a guess seems reasonable.

**If you had another day, what would you improve?**

I'd write an actual automated test suite instead of relying on manual
verification through Swagger UI — that was fine for a 4-6 hour exercise,
but doesn't scale and wouldn't catch a regression like the breadcrumb bug
automatically next time. I'd also want to properly test session-expiry
behaviour against a real 1-hour timeout rather than only handling it
defensively without ever having actually observed it happen, and I'd dig
further into whether the energy endpoint's date window is truly fixed by
probing it with speculative query parameters rather than concluding that
from their absence in the one request I inspected.

**What mistake did you make while solving this?**

I wrote code against two endpoints (`geo` and `energy`) based on their
names in the DevTools Network panel before actually confirming their
full Request URL from the Headers tab. It happened to work out — the
inferred paths were correct — but that was closer to luck than good
process, and I flagged it explicitly as unverified in `PROTOCOL.md`
until I'd actually tested it end-to-end against the live portal. The
breadcrumb selector mistake (described above) was the same pattern
twice over: guessing at structure instead of confirming it first.

**If you were reviewing your own submission, what would you criticise?**

The HTML-parsing code in `client.py` (nameplate fields, breadcrumb) is
inherently fragile — it depends on label text and DOM nesting that could
shift with any frontend redesign, and there's no test coverage to catch
that if it happens. Error handling is fairly minimal: I handle 401 and
404 explicitly but anything else from the portal (5xx, malformed
responses) just propagates as a generic error rather than being
translated into something more meaningful for an API consumer. I'd also
push back on my own trade-off to skip caching entirely — for a
read-mostly system like this, even a simple TTL cache on the meter list
would meaningfully cut load on the legacy portal, and I only wrote a doc
note about it instead of building it.
