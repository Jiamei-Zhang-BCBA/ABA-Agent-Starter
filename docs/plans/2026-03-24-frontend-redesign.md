# Frontend Redesign — Next.js + shadcn/ui

**Date**: 2026-03-24
**Status**: Approved
**Stack**: Next.js 15 (App Router) + shadcn/ui + Tailwind CSS + Zustand + react-hook-form + zod

---

## 1. Architecture

- **Independent project** in `web/` directory, deployed separately from the API
- **App Router** with route groups: `(auth)` for public pages, `(dashboard)` for authenticated pages
- **API communication** via `lib/api.ts` — unified fetch wrapper with auto token refresh and 401 redirect
- **State management** — Zustand for auth state (token, user), React state for page-local data
- **Markdown rendering** — `react-markdown` + `remark-gfm` for job output display

## 2. Project Structure

```
web/
├── app/
│   ├── (auth)/                    # Public pages (centered card layout)
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   ├── invite/page.tsx
│   │   ├── forgot-password/page.tsx
│   │   ├── reset-password/page.tsx
│   │   └── layout.tsx
│   ├── (dashboard)/               # Authenticated pages (nav bar layout)
│   │   ├── features/page.tsx
│   │   ├── jobs/page.tsx
│   │   ├── clients/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── reviews/page.tsx
│   │   ├── users/page.tsx
│   │   ├── settings/page.tsx
│   │   └── layout.tsx
│   ├── layout.tsx
│   └── globals.css
├── components/
│   ├── ui/                        # shadcn/ui components
│   ├── feature-card.tsx
│   ├── job-form-modal.tsx
│   ├── markdown-viewer.tsx
│   ├── markdown-editor.tsx
│   ├── review-card.tsx
│   └── nav-bar.tsx
├── lib/
│   ├── api.ts                     # Fetch wrapper + token refresh
│   ├── auth.ts                    # Zustand auth store
│   └── utils.ts
├── next.config.ts
├── tailwind.config.ts
├── package.json
└── tsconfig.json
```

## 3. Page → API Mapping

| Page | Route | API Endpoints |
|------|-------|---------------|
| Login | `/login` | `POST /auth/login`, `GET /auth/me` |
| Register | `/register` | `POST /users/register` |
| Accept Invite | `/invite?token=xxx` | `POST /users/invite/accept` |
| Forgot Password | `/forgot-password` | `POST /users/password-reset` |
| Reset Password | `/reset-password?token=xxx` | `POST /users/password-reset/confirm` |
| Features | `/features` | `GET /features`, `GET /features/{id}/schema`, `GET /clients`, `GET /staff` |
| Submit Job | Modal on `/features` | `POST /jobs` (multipart) |
| Jobs | `/jobs` | `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/output`, `PATCH /jobs/{id}/output` |
| Clients | `/clients` | `GET /clients` |
| Client Detail | `/clients/[id]` | `GET /clients/{id}`, `GET /clients/{id}/timeline` |
| Reviews | `/reviews` | `GET /reviews`, `POST /reviews/{id}/approve`, `POST /reviews/{id}/reject` |
| Users | `/users` | `GET /users`, `POST /users/invite`, `PATCH /users/{id}`, `DELETE /users/{id}` |
| Settings | `/settings` | `GET /auth/me`, `POST /users/password-reset/confirm` |

## 4. Core Interaction Flows

### Authentication
- Login → store token in localStorage + Zustand → redirect to `/features`
- `lib/api.ts`: auto-attach `Authorization` header, attempt refresh on 401, redirect to `/login` on failure
- Dashboard layout checks token on mount, redirects if missing

### Feature Center → Job Submission
1. Card grid with category tabs filter
2. Click card → Modal → dynamic form from `form_schema.fields` (react-hook-form + zod runtime schema)
3. `select_client` / `select_staff` fields auto-fetch dropdown options
4. Submit as `FormData` multipart → close modal → toast → navigate to `/jobs`

### Job Output Viewing
- Table list with feature name, status badge, timestamp
- Click row → detail panel
- `delivered`: react-markdown render + edit button → textarea → save
- Other statuses: processing/pending review/failed indicators

### Review Queue (admin/BCBA only)
- Card list with output preview
- Approve (optional modified content) / Reject (required comments)

### User Management (admin only)
- Table: email, role, status, actions
- Invite button → Dialog (email + role)
- Inline actions: change role (dropdown), deactivate (confirm dialog)

## 5. Role-Based Access (Frontend Route Guard)

| Page | org_admin | bcba | teacher | parent |
|------|-----------|------|---------|--------|
| Features | ✅ | ✅ | ✅ | ✅ |
| Jobs | ✅ | ✅ | ✅ | ✅ |
| Clients | ✅ | ✅ | ✅ | ✅ |
| Reviews | ✅ | ✅ | ❌ | ❌ |
| Users | ✅ | ❌ | ❌ | ❌ |

## 6. Key Dependencies

- `next` 15.x
- `react` 19.x
- `tailwindcss` 4.x
- `shadcn/ui` (Button, Card, Dialog, Table, Badge, Input, Select, Textarea, Tabs, Toast, DropdownMenu)
- `zustand` — auth state
- `react-hook-form` + `@hookform/resolvers` + `zod` — dynamic forms
- `react-markdown` + `remark-gfm` — Markdown rendering
- `lucide-react` — icons (shadcn default)

## 7. Design Decisions

- **No SSR for API calls** — all data fetching is client-side (`"use client"` pages) since the API requires JWT auth
- **No BFF** — direct browser → FastAPI communication, CORS configured on backend
- **Dynamic form generation** — form schema from API drives field rendering at runtime, no hardcoded forms
- **Markdown editor** — simple textarea + preview toggle, not a full WYSIWYG (matches current behavior)
