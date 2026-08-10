# Phase 5: Frontend Modernization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the prototype frontend (raw fetch, mock data, `alert()`, XSS-prone `dangerouslySetInnerHTML`, no state lib) with a production-grade React app: TanStack Query v5 (server state + polling), Zustand v5 (client state), TipTap (safe rich-text script editor — also kills the XSS), Vidstack video player, real nav + logout, script-first storyboard UX, incremental TypeScript.

**Architecture:** Add libs; introduce `src/api` (typed service) + `src/hooks` (query hooks) + `src/store` (zustand). Migrate `api.js` to TanStack Query under the hood (keep method surface so other phases don't break). Replace Dashboard mock data with real queries. New `ScriptEditor` (TipTap) for script input in wizard. Storyboard view maps parsed scenes to card grid. Rework `VoiceCloning`, `Profile`, `Settings` pages. Add TypeScript gradually (start with new files, `.tsx`).

**Tech Stack:** TanStack Query v5, Zustand v5, TipTap (core + starter-kit + placeholder), Vidstack, react-hook-form + zod (forms), sonner (already dep). Keep Tailwind v4 + shadcn.

## Global Constraints

- Never use `dangerouslySetInnerHTML` after this phase — TipTap renders via its own doc model (safe)
- `api.js` keeps its existing method names (login, register, getProjects, etc.) — internal impl switches to QueryClient; callers unchanged
- All fetch hooks live in `src/hooks/`; components don't `fetch` directly
- Auth state (user, token) → Zustand persisted store (localStorage); remove AuthContext or keep as thin wrapper over store
- Vite proxy for `/api` → `http://localhost:5004` (removes CORS issues, allows relative URLs)
- TypeScript: new files `.tsx`; existing `.jsx` left until touched
- 404 page + Toaster already done (Phase 0); nav bar + logout everywhere
- Keep design language (dark gradient glass) but enforce consistent tokens via Tailwind theme

---

### Task 1: Install libs + Vite proxy + QueryClientProvider

**Files:**
- Modify: `package.json`
- Modify: `vite.config.js` (proxy)
- Modify: `src/main.jsx` (QueryClientProvider + Toaster)
- Create: `src/lib/queryClient.js`

**Interfaces:**
- Produces: app boots with TanStack Query; `/api` proxied to backend

- [ ] **Step 1: Install deps**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend
pnpm add @tanstack/react-query@^5 zustand@^5 @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder @vidstack/react@^1.1.0 react-hook-form zod
```

- [ ] **Step 2: Vite proxy**

In `vite.config.js` add:

```js
server: {
  proxy: {
    '/api': { target: 'http://localhost:5004', changeOrigin: true },
  },
},
```

- [ ] **Step 3: QueryClient + provider in main.jsx**

```js
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'

root.render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
)
```

- [ ] **Step 4: lib/queryClient.js**

```js
import { QueryClient } from '@tanstack/react-query'
export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
})
```

- [ ] **Step 5: Verify + commit**

```bash
pnpm dev
# open browser, no console errors, /api hits proxy
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: tanstack query, zustand, tiptap, vidstack; vite api proxy"
```

---

### Task 2: Zustand auth store replaces AuthContext

**Files:**
- Create: `src/store/authStore.js`
- Modify: `src/contexts/AuthContext.jsx` (re-export from store for compatibility)
- Modify: `src/services/api.js` (set token from store)

**Interfaces:**
- Produces: `useAuthStore` with `user`, `token`, `login`, `logout`, `hydrate`; persisted

- [ ] **Step 1: authStore.js**

```js
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      token: localStorage.getItem('token') || null,
      setUser: (user) => set({ user }),
      setToken: (token) => set({ token }),
      logout: () => set({ user: null, token: null }),
    }),
    { name: 'auth-storage' },
  ),
)
```

- [ ] **Step 2: Keep AuthContext working**

Rewrite `AuthContext.jsx` as thin wrapper: reads `useAuthStore`, exposes same `login/logout/user/isAuthenticated` API so existing components don't change in this task.

- [ ] **Step 3: api.js uses store token**

```js
import { useAuthStore } from '@/store/authStore'
// in request(): token from useAuthStore.getState().token
```

- [ ] **Step 4: Verify + commit**

Login persists across refresh.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: zustand persisted auth store"
```

---

### Task 3: Replace Dashboard mock data with real queries

**Files:**
- Modify: `src/components/Dashboard.jsx`
- Create: `src/hooks/useProjects.js`, `useTasks.js`, `usePresets.js`, `useVoices.js`
- Create: `src/api/projects.js`, `src/api/tasks.js`, `src/api/presets.js`, `src/api/voices.js`

**Interfaces:**
- Produces: Dashboard shows real projects, stats, recent videos; loading skeletons + error toasts

- [ ] **Step 1: API modules**

Each `src/api/*.js` wraps `api` service:

```js
export function useProjects() {
  return useQuery({ queryKey: ['projects'], queryFn: () => api.get('/projects').then(r => r.data) })
}
```

- [ ] **Step 2: Dashboard rewrite**

Remove hardcoded arrays; use `useProjects()`, `usePresets()`; render with `Skeleton` while `isLoading`; `error` → sonner toast + retry button. Wire "View" → `/projects/:id`.

- [ ] **Step 3: Add logout + nav**

Add top nav with logout button calling `useAuthStore.logout()` + `api.post('/auth/logout')` + navigate `/login`.

- [ ] **Step 4: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend
pnpm lint
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: real dashboard data via react-query; logout nav"
```

---

### Task 4: TipTap ScriptEditor (kills XSS)

**Files:**
- Create: `src/components/ScriptEditor.jsx`
- Modify: `src/components/VideoCreationWizard.jsx`
- Delete (or stop using): `dangerouslySetInnerHTML` in Dashboard.jsx:222-227

**Interfaces:**
- Produces: safe rich-text editor for script input; parsed storyboard below

- [ ] **Step 1: ScriptEditor with TipTap**

```jsx
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'

export function ScriptEditor({ value, onChange }) {
  const editor = useEditor({
    extensions: [StarterKit, Placeholder.configure({ placeholder: 'Write your script. Use **bold** for emphasis words...' })],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  })
  return <EditorContent editor={editor} className="min-h-[300px] ..." />
}
```

- [ ] **Step 2: Parse to storyboard**

Convert editor HTML back to plain scenes: use TipTap `editor.getText()` + existing scene regex OR extend backend parse. Render scene cards with duration + narration preview.

- [ ] **Step 3: Remove dangerouslySetInnerHTML usage**

Replace with TipTap `editor` render or escaped text. Grep:

```bash
grep -rn "dangerouslySetInnerHTML" money_weaver_frontend/src/
```

Ensure zero matches remain.

- [ ] **Step 4: Verify + commit**

Bold markers render as styled text in editor; pasted HTML shows as text not markup.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: tiptap script editor, remove XSS-prone innerHTML"
```

---

### Task 5: Vidstack video player in ProjectDetail

**Files:**
- Modify: `src/pages/ProjectDetail.jsx`
- Create: `src/components/VideoPlayer.jsx`

**Interfaces:**
- Produces: `<VideoPlayer src={video_url} poster={thumbnail_url} />` with full controls

- [ ] **Step 1: VideoPlayer**

```jsx
import { HlsProvider, VideoLayout, MediaPlayer } from '@vidstack/react'
import '@vidstack/react/player/styles/default/theme.css'
import '@vidstack/react/player/styles/default/layouts/video.css'

export function VideoPlayer({ src, poster }) {
  return (
    <MediaPlayer src={src} poster={poster} title="Generated video" crossOrigin>
      <VideoLayout />
    </MediaPlayer>
  )
}
```

- [ ] **Step 2: Use in ProjectDetail**

Replace `<video controls>` with `<VideoPlayer ... />`.

- [ ] **Step 3: Verify + commit**

Video plays with Vidstack UI; poster shows thumbnail.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: vidstack video player"
```

---

### Task 6: Real Profile + Settings pages

**Files:**
- Modify: `src/components/ProfilePage.jsx`
- Modify: `src/components/SettingsPage.jsx`
- Modify: `src/routes/user.py` (backend PATCH /users/me)

**Interfaces:**
- Produces: profile shows real user + editable username; settings has real account actions (change password, delete account, API key management)

- [ ] **Step 1: Backend PATCH /api/users/me**

```python
@user_bp.route('/api/users/me', methods=['PATCH'])
@auth_required
def update_me():
    data = request.get_json()
    user = User.query.get(g.current_user['id'])
    if 'username' in data: user.username = data['username']
    if 'password' in data: user.hash_password(data['password'])
    db.session.commit()
    return jsonify({'id': user.id, 'username': user.username, 'email': user.email})
```

- [ ] **Step 2: Profile page**

Fetch `/users/me`; inline edit username; save via PATCH with react-hook-form + zod.

- [ ] **Step 3: Settings page**

Change password (PATCH), show/revoke API keys (fetch `/api-keys`), delete account (DELETE → logout).

- [ ] **Step 4: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: real profile and settings with backend endpoints"
```

---

### Task 7: Script-first storyboard wizard redesign

**Files:**
- Create: `src/components/Storyboard.jsx`
- Modify: `src/components/VideoCreationWizard.jsx`

**Interfaces:**
- Produces: wizard is script-first: (1) write script, (2) see storyboard scenes, (3) pick preset+voice, (4) generate

- [ ] **Step 1: Storyboard component**

Card grid of scenes: index, narration text, duration chip, stock-photo/video placeholder, generate-single-scene action (reuse per-scene endpoint).

- [ ] **Step 2: Wizard 4-step layout**

Step indicators; each step validates; "Generate" disabled until script + preset selected.

- [ ] **Step 3: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: script-first storyboard wizard"
```

---

### Task 8: Phase 5 verification

- [ ] **Step 1: Full app run**

`pnpm dev` + backend: register → dashboard (real data) → create via wizard → storyboard → generate → project detail plays video.

- [ ] **Step 2: XSS check**

Paste `<img src=x onerror=alert(1)>` into script → no alert fires.

- [ ] **Step 3: lint + build**

```bash
pnpm lint && pnpm build
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 5 frontend modernization verified"
```
