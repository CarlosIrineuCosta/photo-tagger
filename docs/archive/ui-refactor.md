# ui-refactor.md

> ⚠️ **Priority Override**
>
> All UI-related work in this document supersedes prior Streamlit tasks.
>
> Codex must complete all ✅ items here *before* resuming any tasks in `tasks_2025-10-16.md`.
>
> Backend logic in `app/core/` remains untouched.
>
> Reference documents:
>
> * [`project_map.md`](./docs/project_map.md)
> * [`backend_interface_spec.md`](./docs/backend_interface_spec.md)

---

## Context

**Project:** Photo Tagger

**Goal:** Replace Streamlit interface with a modern React + Shadcn/UI frontend that connects via FastAPI to the stable backend defined under `app/core/`.

The new frontend must:

* Provide a fixed layout similar to `mock_v2.html`.  (./tests/UI_tests/mock_v2.html)
* Use a proper design system (Shadcn/UI + Tailwind CSS).
* Be future-integrable with *Lumen*, a project that is not in this folder.
* Serve all UI data through FastAPI endpoints as defined in `backend_interface_spec.md`.

---

## ✅ Phase 1 — Shadcn/UI Front-End Refactor

### 🎯 Objective

Create a production-ready UI foundation with full parity to the existing HTML mock and complete separation from Streamlit.

---

### ✅ Progress Tracker

| #     | Task                   | Description                                                                                          | Owner | Status |
| ----- | ---------------------- | ---------------------------------------------------------------------------------------------------- | ----- | ------ |
| ✅ 1  | **Initialize project** | Create Vite + React + TypeScript app under `/frontend`; install Tailwind CSS + Shadcn/UI. Verify `npm run dev` runs. | Codex | ✅ (2025-10-17) |
| ✅ 2  | **Theme setup**        | Translate CSS variables (`--bg`, `--panel`, etc.) into Tailwind tokens and Shadcn theme file.        | Codex | ✅ (2025-10-17) |
| ✅ 3  | **Component split**    | Port `lumen_mock.html` into:<br>• Topbar<br>• CommandBar<br>• GalleryGrid<br>• WorkflowSidebar<br>• StatusStrip | Codex | ✅ (2025-10-17) |
| ✅ 4  | **Routing**            | Configure React Router for `/`, `/config`, `/help`, `/login`.                                        | Codex | ✅ (2025-10-17) |
| ✅ 5  | **Gallery Grid**       | Use Shadcn `Card`, `AspectRatio`, and `Toggle` components; implement 6-column QHD grid, letterbox/center-crop toggle. | Codex | ✅ (2025-10-17) |
| ✅ 6  | **Workflow Sidebar**   | Implement collapsible sidebar with Shadcn `Sheet` or `Drawer`, hidden by default.                    | Codex | ✅ (2025-10-17) |
| ✅ 7  | **Status Strip**       | Create fixed bottom component showing last 20 logs (Shadcn `Toast` or custom).                       | Codex | ✅ (2025-10-17) |
| ✅ 8  | **Dropdown Actions**   | Implement Export ▾ via Shadcn `DropdownMenu` with “CSV / Sidecars / Both.”                           | Codex | ✅ (2025-10-17) |
| ✅ 9  | **Help Page**          | Static Markdown/HTML placeholder with generated text.                                                | Codex | ✅ (2025-10-17) |
| ✅ 10 | **Login Stub**         | Simple Shadcn `Card` form; no logic yet.                                                             | Codex | ✅ (2025-10-17) |
| ✅ 11 | **Final theme pass**   | Adjust gray lines, padding, scaling at 1440p–2160p.                                                  | Codex | ✅ (2025-10-17) |

Deliverable → fully navigable React frontend using mock JSON data.

---

## ⚙️ Phase 2 — FastAPI Bridge

| #     | Task                    | Description                                                                      | Owner | Status |
| ----- | ----------------------- | -------------------------------------------------------------------------------- | ----- | ------ |
| ✅ 12 | **Create FastAPI app**  | Scaffold under `/backend/api/` following `backend_interface_spec.md`.            | Codex | ✅ (2025-10-17) |
| ✅ 13 | **Integrate endpoints** | Implement `/api/gallery`, `/api/tag`, `/api/export`, `/api/config`.              | Codex | ✅ (2025-10-17) |
| ✅ 14 | **Connect frontend**    | Replace mock fetches with live API requests (`fetch` via `frontend/lib/api.ts`). | Codex | ✅ (2025-10-17) |
| ✅ 15 | **Testing & QA**        | Validate image paths, labels, save/export flow.                                  | Codex | ✅ (2025-10-21) |
| ✅ 16 | **Remove Streamlit**    | Delete `app/ui/streamlit_app.py` after full replacement verified.                | Codex | ✅ (2025-10-21) |
| ✅ 17 | **Dockerfile update**   | Combine backend + frontend in production image (`npm build` + `uvicorn`).        | Codex | ☐      |

---

## 🧱 Folder Structure (Final Target)

```
photo-tagger/
├─ backend/
│  ├─ api/
│  │  └─ index.py              # FastAPI entrypoint
│  └─ core/                    # untouched business logic
├─ frontend/
│  ├─ components/
│  │  ├─ Topbar.tsx
│  │  ├─ CommandBar.tsx
│  │  ├─ GalleryGrid.tsx
│  │  ├─ WorkflowSidebar.tsx
│  │  └─ StatusStrip.tsx
│  ├─ layout/
│  │  └─ AppLayout.tsx
│  ├─ pages/
│  │  ├─ GalleryPage.tsx
│  │  ├─ ConfigPage.tsx
│  │  ├─ HelpPage.tsx
│  │  └─ LoginPage.tsx
│  ├─ lib/api.ts
│  ├─ styles/globals.css
│  ├─ main.tsx
│  └─ tailwind.config.ts
└─ docs/
   ├─ project_map.md
   ├─ backend_interface_spec.md
   └─ ui-refactor.md
```

---

## 🧠 Codex Directives

1. **Backend protection:** Never alter logic in `app/core/`.
2. **Environment isolation:** Read model paths and keys only via environment or config TOML.
3. **Interface compliance:** All API routes must return JSON exactly as defined in `backend_interface_spec.md`.
4. **State persistence:** Frontend must manage its own pagination, crop mode, and workflow state.
5. **Theme:** Follow Tailwind gray palette, accent blue (`#3b82f6`), and spacing scale 4/8/12/16px.
6. **Testing:** Before merging, confirm `npm run build` and `uvicorn backend.api.index:app --reload` both succeed.
7. **Commit tags:** Each completed section should push with tag `ui-refactor-phase1`, then `phase2`.

---

## 🧭 Milestone Overview

| Milestone | Definition of Done                              | ETA   | Status |
| --------- | ----------------------------------------------- | ----- | ------ |
| **M1**    | React + Tailwind + Shadcn scaffold runs locally | Day 1 | ✅ (2025-10-17) |
| **M2**    | Components migrated, style parity with mock     | Day 2 | ✅ (2025-10-17) |
| **M3**    | Routing & mock API connected                    | Day 3 | ✅ (2025-10-17) |
| **M4**    | Live FastAPI integration                        | Day 5 | ✅ (2025-10-21) |
| **M5**    | Streamlit fully removed                         | Day 6 | ✅ (2025-10-21) |
| **M6**    | Visual + functional QA                          | Day 7 | ✅ (2025-10-21) |

---

## Remaining Work

1. **Production packaging** – create/update the Dockerfile to build the frontend (`npm run build`), bundle the static assets, and launch FastAPI via `uvicorn`.
2. **Ops documentation** – refresh `initial_setup.md` (and any operator runbooks) to describe the new `./start-tagger.sh` workflow, label pack usage, and recovery checks.
3. **Future enhancements (backlog)**
   - Consider async/background execution for `/api/process` so long pipelines do not block the API worker.
   - Add operator tools for cache maintenance (clear thumbnails, reload embeddings).
   - Expand label packs with additional tiers/localization once scoring validation is complete.
   - Revisit UI affordances (e.g., saved vs selected badges) after more real-world review sessions.

---

✅ **End of document**
