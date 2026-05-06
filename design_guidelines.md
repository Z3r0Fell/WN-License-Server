{
  "meta": {
    "product": "WatchNexus Licensing Server",
    "app_type": "hybrid_fullstack",
    "design_personality": [
      "developer-focused",
      "professional",
      "trustworthy",
      "engineered",
      "security-first",
      "data-dense (admin)",
      "friendly (customer portal)",
      "docs-first (public)"
    ],
    "north_star": "Feel like Linear/Stripe/Vercel: crisp typography, precise spacing, monospace accents, and calm confidence. Dark mode is the primary feel; light mode is equally legible."
  },

  "brand_attributes": {
    "keywords": ["signed", "verified", "audit-ready", "predictable", "fast"],
    "visual_metaphors": [
      "cryptographic seal (emerald accent)",
      "terminal precision (mono chips + code blocks)",
      "ledger/audit trail (timeline UI)",
      "hardware fingerprint (device cards)"
    ]
  },

  "color_system": {
    "accent_choice": {
      "name": "Emerald (secure/signed)",
      "rationale": "Emerald reads as verified/success/cryptographic without default SaaS-blue. Used for focus rings, active states, and key CTAs."
    },

    "palette_hex": {
      "neutrals": {
        "ink_950": "#070A0F",
        "slate_925": "#0B1220",
        "slate_900": "#0F172A",
        "slate_850": "#111C2E",
        "slate_800": "#16233A",
        "slate_700": "#24324A",
        "slate_600": "#3A4A66",
        "slate_500": "#64748B",
        "slate_300": "#CBD5E1",
        "slate_200": "#E2E8F0",
        "slate_100": "#F1F5F9",
        "paper_0": "#FFFFFF"
      },
      "emerald": {
        "emerald_50": "#ECFDF5",
        "emerald_100": "#D1FAE5",
        "emerald_200": "#A7F3D0",
        "emerald_300": "#6EE7B7",
        "emerald_400": "#34D399",
        "emerald_500": "#10B981",
        "emerald_600": "#059669",
        "emerald_700": "#047857",
        "emerald_800": "#065F46",
        "emerald_900": "#064E3B"
      },
      "status": {
        "success": "#10B981",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "info": "#38BDF8",
        "neutral": "#94A3B8"
      }
    },

    "semantic_tokens_hsl_for_shadcn": {
      "note": "Project already uses shadcn HSL tokens in index.css. Replace tokens to match this system. Keep contrast high in both modes.",
      "light": {
        "--background": "0 0% 100%",
        "--foreground": "222 47% 11%",
        "--card": "0 0% 100%",
        "--card-foreground": "222 47% 11%",
        "--popover": "0 0% 100%",
        "--popover-foreground": "222 47% 11%",

        "--primary": "222 47% 11%",
        "--primary-foreground": "210 40% 98%",

        "--secondary": "210 40% 96%",
        "--secondary-foreground": "222 47% 11%",

        "--muted": "210 40% 96%",
        "--muted-foreground": "215 16% 47%",

        "--accent": "210 40% 96%",
        "--accent-foreground": "222 47% 11%",

        "--border": "214 32% 91%",
        "--input": "214 32% 91%",

        "--ring": "160 84% 39%",

        "--destructive": "0 84% 60%",
        "--destructive-foreground": "210 40% 98%",

        "--radius": "0.75rem"
      },
      "dark": {
        "--background": "222 47% 6%",
        "--foreground": "210 40% 98%",
        "--card": "222 47% 8%",
        "--card-foreground": "210 40% 98%",
        "--popover": "222 47% 8%",
        "--popover-foreground": "210 40% 98%",

        "--primary": "210 40% 98%",
        "--primary-foreground": "222 47% 11%",

        "--secondary": "222 47% 12%",
        "--secondary-foreground": "210 40% 98%",

        "--muted": "222 47% 12%",
        "--muted-foreground": "215 20% 70%",

        "--accent": "222 47% 12%",
        "--accent-foreground": "210 40% 98%",

        "--border": "222 47% 16%",
        "--input": "222 47% 16%",

        "--ring": "160 84% 39%",

        "--destructive": "0 63% 31%",
        "--destructive-foreground": "210 40% 98%",

        "--radius": "0.75rem"
      }
    },

    "gradient_usage": {
      "allowed": [
        "Landing hero background only (<= 20% viewport)",
        "Docs header accent bar (thin, decorative)",
        "Large section background wash behind hero"
      ],
      "recommended_gradients": [
        {
          "name": "Emerald Seal Wash (dark hero)",
          "css": "radial-gradient(900px circle at 20% 10%, rgba(16,185,129,0.18), transparent 55%), radial-gradient(700px circle at 80% 30%, rgba(56,189,248,0.10), transparent 60%)",
          "note": "Not saturated; stays subtle."
        },
        {
          "name": "Paper Mint Wash (light hero)",
          "css": "radial-gradient(900px circle at 20% 10%, rgba(16,185,129,0.10), transparent 55%), radial-gradient(700px circle at 80% 30%, rgba(2,132,199,0.06), transparent 60%)"
        }
      ]
    }
  },

  "typography": {
    "font_pairing": {
      "sans": {
        "name": "Inter",
        "google_fonts": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
        "usage": "All UI text, headings, labels"
      },
      "mono": {
        "name": "JetBrains Mono",
        "google_fonts": "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap",
        "usage": "License keys, API keys, code blocks, curl examples, timestamps"
      }
    },
    "css_setup": {
      "index_css_addition": "Set body font-family to Inter; set code/mono utility to JetBrains Mono. Prefer Tailwind classes: font-sans and font-mono."
    },
    "type_scale_tailwind": {
      "h1": "text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight",
      "h2": "text-2xl sm:text-3xl font-semibold tracking-tight",
      "h3": "text-xl font-semibold",
      "subtitle": "text-base md:text-lg text-muted-foreground",
      "body": "text-sm md:text-base",
      "small": "text-xs text-muted-foreground",
      "mono_chip": "font-mono text-xs md:text-sm"
    },
    "numeric_and_keys": {
      "rule": "Any license key/API key/fingerprint must use font-mono + increased letter spacing.",
      "classes": "font-mono tracking-[0.12em]"
    }
  },

  "layout_and_grid": {
    "global_container": {
      "max_width": "max-w-6xl (marketing/docs), max-w-[1400px] (admin)",
      "padding": "px-4 sm:px-6 lg:px-8",
      "vertical_rhythm": "Use py-16 for marketing sections; py-10 for docs; py-6 for admin pages"
    },
    "admin_shell": {
      "desktop": "Left sidebar (w-64) + top bar + content area. Content uses 12-col grid with dense cards.",
      "mobile": "Sidebar collapses into Sheet; top bar remains with search + quick actions. Tables become card lists."
    },
    "docs_shell": {
      "desktop": "3-column: left nav (w-64), main (max-w-3xl), right TOC (w-64).",
      "mobile": "Left nav becomes Sheet; TOC becomes Collapsible at top of article."
    },
    "portal_shell": {
      "feel": "Same tokens, but lighter density: more whitespace, fewer columns, friendlier copy.",
      "desktop": "Top nav + content max-w-5xl; license cards grid 1-3 columns."
    }
  },

  "component_path": {
    "shadcn_primary": {
      "button": "/app/frontend/src/components/ui/button.jsx",
      "badge": "/app/frontend/src/components/ui/badge.jsx",
      "card": "/app/frontend/src/components/ui/card.jsx",
      "table": "/app/frontend/src/components/ui/table.jsx",
      "tabs": "/app/frontend/src/components/ui/tabs.jsx",
      "input": "/app/frontend/src/components/ui/input.jsx",
      "textarea": "/app/frontend/src/components/ui/textarea.jsx",
      "select": "/app/frontend/src/components/ui/select.jsx",
      "dropdown_menu": "/app/frontend/src/components/ui/dropdown-menu.jsx",
      "dialog": "/app/frontend/src/components/ui/dialog.jsx",
      "drawer": "/app/frontend/src/components/ui/drawer.jsx",
      "sheet": "/app/frontend/src/components/ui/sheet.jsx",
      "tooltip": "/app/frontend/src/components/ui/tooltip.jsx",
      "popover": "/app/frontend/src/components/ui/popover.jsx",
      "scroll_area": "/app/frontend/src/components/ui/scroll-area.jsx",
      "separator": "/app/frontend/src/components/ui/separator.jsx",
      "skeleton": "/app/frontend/src/components/ui/skeleton.jsx",
      "sonner_toasts": "/app/frontend/src/components/ui/sonner.jsx",
      "form": "/app/frontend/src/components/ui/form.jsx",
      "calendar": "/app/frontend/src/components/ui/calendar.jsx",
      "accordion": "/app/frontend/src/components/ui/accordion.jsx",
      "collapsible": "/app/frontend/src/components/ui/collapsible.jsx",
      "navigation_menu": "/app/frontend/src/components/ui/navigation-menu.jsx",
      "breadcrumb": "/app/frontend/src/components/ui/breadcrumb.jsx",
      "pagination": "/app/frontend/src/components/ui/pagination.jsx",
      "command": "/app/frontend/src/components/ui/command.jsx",
      "switch": "/app/frontend/src/components/ui/switch.jsx",
      "checkbox": "/app/frontend/src/components/ui/checkbox.jsx",
      "radio_group": "/app/frontend/src/components/ui/radio-group.jsx",
      "progress": "/app/frontend/src/components/ui/progress.jsx",
      "resizable": "/app/frontend/src/components/ui/resizable.jsx"
    },
    "recommended_new_components_to_create": [
      {
        "name": "CodeBlock",
        "path": "/app/frontend/src/components/CodeBlock.jsx",
        "purpose": "Docs + landing curl snippets with filename header + copy button + optional language tabs"
      },
      {
        "name": "CopyChip",
        "path": "/app/frontend/src/components/CopyChip.jsx",
        "purpose": "License/API key chip with copy-to-clipboard + reveal/hide + truncated display"
      },
      {
        "name": "StatusPill",
        "path": "/app/frontend/src/components/StatusPill.jsx",
        "purpose": "Active/Revoked/Expired/Grace badges with consistent colors"
      },
      {
        "name": "EmptyState",
        "path": "/app/frontend/src/components/EmptyState.jsx",
        "purpose": "Reusable empty states with icon + title + description + primary/secondary actions"
      },
      {
        "name": "AuditTimeline",
        "path": "/app/frontend/src/components/AuditTimeline.jsx",
        "purpose": "Chronological audit log with grouped days + event severity"
      },
      {
        "name": "CsvUpload",
        "path": "/app/frontend/src/components/CsvUpload.jsx",
        "purpose": "Drag/drop CSV + preview table + mapping hints"
      }
    ]
  },

  "component_patterns": {
    "buttons": {
      "style": "Professional / Corporate with slight premium softness",
      "radius": "rounded-xl (token radius 0.75rem)",
      "variants": {
        "primary": {
          "shadcn_variant": "default",
          "classes": "bg-emerald-600 text-white hover:bg-emerald-500 focus-visible:ring-2 focus-visible:ring-emerald-400",
          "data_testid_examples": ["landing-hero-primary-cta", "admin-create-license-button"]
        },
        "secondary": {
          "shadcn_variant": "secondary",
          "classes": "border border-border bg-secondary text-foreground hover:bg-muted",
          "data_testid_examples": ["landing-hero-secondary-cta"]
        },
        "ghost": {
          "shadcn_variant": "ghost",
          "classes": "hover:bg-accent",
          "data_testid_examples": ["docs-copy-link-button"]
        },
        "destructive": {
          "shadcn_variant": "destructive",
          "classes": "focus-visible:ring-2 focus-visible:ring-red-400",
          "data_testid_examples": ["admin-revoke-license-button"]
        }
      },
      "micro_interaction": "On hover: subtle background shift only. On press: scale-[0.98]. Do not use transition-all; use transition-colors and active:scale-[0.98]."
    },

    "inputs_and_forms": {
      "field_style": "Crisp, slightly taller inputs for readability; inline help text below.",
      "classes": {
        "input": "h-10 rounded-lg bg-background",
        "help": "text-xs text-muted-foreground mt-1",
        "error": "text-xs text-red-500 mt-1"
      },
      "patterns": [
        "Use shadcn Form for validation wiring",
        "Group advanced settings in Accordion (Products: signing method, fingerprint mode)",
        "Use Dialog for create/edit; Drawer for detail views"
      ],
      "data_testid_rules": "Every input/select/checkbox must have data-testid like product-create-name-input, license-filter-status-select"
    },

    "tables_and_density": {
      "admin_tables": {
        "default_row_height": "h-12 (comfortable dense)",
        "header": "sticky top-0 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        "hover": "hover:bg-muted/50",
        "zebra": "Optional for audit/webhooks: odd:bg-transparent even:bg-muted/20",
        "empty": "Replace empty table with EmptyState component (not blank rows)."
      },
      "mobile_fallback": "<768px: render list cards instead of table; keep same filters."
    },

    "status_badges": {
      "use": "shadcn Badge with custom classes",
      "definitions": {
        "active": {"label": "Active", "classes": "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"},
        "revoked": {"label": "Revoked", "classes": "bg-red-500/15 text-red-400 border border-red-500/20"},
        "expired": {"label": "Expired", "classes": "bg-slate-500/15 text-slate-300 border border-slate-500/20"},
        "grace": {"label": "Grace", "classes": "bg-amber-500/15 text-amber-300 border border-amber-500/20"},
        "pending": {"label": "Pending", "classes": "bg-sky-500/15 text-sky-300 border border-sky-500/20"}
      },
      "data_testid_examples": ["license-status-badge", "webhook-event-status-badge"]
    },

    "copy_to_clipboard": {
      "pattern": "Chip with truncated key + copy icon + toast feedback",
      "chip_classes": "inline-flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-1.5 font-mono text-xs tracking-[0.12em]",
      "truncate": "Show first 6 + ellipsis + last 4; reveal full on hover-card or click 'Reveal'",
      "toast": "Use sonner: toast.success('Copied API key')",
      "data_testid_examples": ["license-key-copy-chip", "api-key-copy-chip", "webhook-payload-copy-button"]
    },

    "drawers_and_modals": {
      "license_detail": {
        "component": "Drawer",
        "width": "sm:max-w-[520px]",
        "sections": [
          "Header: License key CopyChip + StatusPill",
          "Stats row: activations count, last seen, product",
          "Tabs: Activations | Audit | Webhooks",
          "Footer actions: Revoke, Extend, Deactivate device"
        ],
        "data_testid_examples": ["license-detail-drawer", "license-detail-revoke-button"]
      },
      "create_edit": {
        "component": "Dialog",
        "pattern": "Two-column form on desktop; single column on mobile. Sticky footer with Cancel/Save.",
        "data_testid_examples": ["product-create-dialog", "license-extend-dialog"]
      }
    },

    "docs_code_blocks": {
      "pattern": "Stripe-like code block: filename header + copy button + scrollable pre",
      "classes": {
        "wrapper": "rounded-xl border border-border bg-muted/30 overflow-hidden",
        "header": "flex items-center justify-between px-4 py-2 bg-background/40 border-b border-border",
        "filename": "font-mono text-xs text-muted-foreground",
        "copy_button": "text-xs font-mono",
        "pre": "p-4 overflow-x-auto text-[13px] leading-6 font-mono"
      },
      "syntax_hint": "No heavy syntax highlighter required; use subtle token coloring via spans if needed. Keep readable in dark mode.",
      "data_testid_examples": ["docs-activate-curl-codeblock", "docs-code-copy-button"]
    },

    "charts_placeholder": {
      "library": "Recharts (optional)",
      "placeholder": "Use Card with Skeleton bars until real data. Keep chart area 220-260px tall.",
      "data_testid_examples": ["admin-recent-activations-chart"]
    },

    "webhook_events": {
      "list_pattern": "Table with provider icon + event type + status + timestamp + 'View payload' action",
      "payload_viewer": "Dialog with ScrollArea + CodeBlock (JSON) + Copy",
      "provider_icons": "Use Lucide icons + small brand color dot (not gradients).",
      "data_testid_examples": ["webhook-events-table", "webhook-payload-dialog"]
    },

    "bulk_import_csv": {
      "pattern": "Step layout: Upload -> Preview -> Confirm",
      "upload": "Dropzone-like Card with dashed border; show accepted columns hint",
      "preview": "Table with first 20 rows + validation badges",
      "confirm": "Dialog footer with Import button + progress",
      "data_testid_examples": ["csv-upload-input", "csv-preview-table", "csv-import-confirm-button"]
    },

    "loading_and_skeletons": {
      "rule": "Prefer Skeleton for tables/cards; use small spinner only for inline actions.",
      "skeleton_patterns": [
        "Stats cards: 3 lines skeleton",
        "Table: header + 6 rows skeleton",
        "Drawer: header skeleton + tab content skeleton"
      ],
      "data_testid_examples": ["licenses-table-skeleton", "license-detail-skeleton"]
    },

    "empty_states": {
      "tone": "Action-oriented, not apologetic. Provide next step.",
      "examples": [
        {
          "context": "No licenses yet",
          "title": "No licenses issued",
          "description": "Create your first license key or import a reseller batch.",
          "primary": "Create license",
          "secondary": "Bulk import CSV",
          "data_testid": "licenses-empty-state"
        },
        {
          "context": "No activations",
          "title": "No activations recorded",
          "description": "Once a customer activates, devices will appear here with fingerprints and last seen.",
          "primary": "View docs",
          "secondary": "Copy /activate curl",
          "data_testid": "activations-empty-state"
        },
        {
          "context": "No webhook events",
          "title": "No webhook deliveries",
          "description": "Configure a webhook endpoint to receive purchase and refund events.",
          "primary": "Add webhook",
          "secondary": "Test delivery",
          "data_testid": "webhooks-empty-state"
        }
      ]
    }
  },

  "page_by_page_layout_sketches": {
    "/ (Landing)": {
      "layout": [
        "Top nav: WatchNexus logo (left), Docs, Pricing? (optional), Admin Login, Customer Portal (right).",
        "Hero (<= 20% viewport gradient wash): Left copy + right code snippet card.",
        "Hero content: H1 + subtitle + 2 CTAs (Admin login primary, View docs secondary).",
        "Feature grid (4): Sign, Activate, Validate, Audit — each Card with icon + 2 lines.",
        "Security proof section: 'Audit-ready by default' with 3 bullets + small screenshot placeholder.",
        "CTA band: 'Start issuing licenses in minutes' with button.",
        "Footer: links + small mono build/version stamp."
      ],
      "hero_code_snippet": "curl -X POST $WATCHNEXUS_URL/api/activate ...",
      "micro_motion": [
        "Hero background: slow radial drift (CSS keyframes) respecting prefers-reduced-motion",
        "CTA buttons: hover color shift + active scale",
        "Feature cards: hover lift shadow-sm -> shadow-md"
      ],
      "data_testid": {
        "primary_cta": "landing-admin-login-cta",
        "secondary_cta": "landing-view-docs-cta"
      }
    },

    "/docs (Integration Docs)": {
      "layout": [
        "Docs shell: left nav (endpoints + guides), main article, right 'On this page' TOC.",
        "Main: Intro + auth section + endpoints (/activate, /validate) with request/response blocks.",
        "Each endpoint: Tabs (curl | Node | Python) optional; keep curl default.",
        "Sticky 'Copy base URL' chip near top.",
        "Right TOC highlights active heading on scroll."
      ],
      "components": ["NavigationMenu", "ScrollArea", "Tabs", "Separator", "CodeBlock", "CopyChip"],
      "data_testid": {
        "toc": "docs-right-toc",
        "left_nav": "docs-left-nav",
        "code_copy": "docs-code-copy-button"
      }
    },

    "/admin/login": {
      "layout": [
        "Centered-ish but not text-centered: two-column split on desktop.",
        "Left: brand + short bullets (Audit logs, Webhooks, Bulk import).",
        "Right: Card with login form.",
        "Dark mode default; show subtle border + noise background."
      ],
      "data_testid": {
        "email": "admin-login-email-input",
        "password": "admin-login-password-input",
        "submit": "admin-login-submit-button"
      }
    },

    "/admin (Dashboard)": {
      "layout": [
        "Admin shell with sidebar + top bar.",
        "Top bar: global search (Command), quick create (DropdownMenu), user menu.",
        "Row 1: 4 stats cards (Total licenses, Active installs, Revoked, Expiring soon).",
        "Row 2: Recent activations chart placeholder (Card) + Recent webhook failures (Card list).",
        "Row 3: Latest audit events (Table compact)."
      ],
      "data_testid": {
        "stats_total": "admin-stats-total-licenses",
        "stats_active_installs": "admin-stats-active-installs",
        "chart": "admin-recent-activations-chart"
      }
    },

    "/admin/licenses": {
      "layout": [
        "Header: title + Create license button.",
        "Filter bar: search input + status Select + product Select + date range (Calendar in Popover) + Clear.",
        "Table: key (CopyChip), customer, product, status badge, activations count, last seen, actions.",
        "Row click opens License detail Drawer."
      ],
      "data_testid": {
        "search": "licenses-filter-search-input",
        "status": "licenses-filter-status-select",
        "product": "licenses-filter-product-select",
        "table": "licenses-table",
        "create": "licenses-create-button"
      }
    },

    "/admin/licenses/:id": {
      "layout": [
        "Prefer Drawer from list; direct route renders same content full page on mobile.",
        "Header: key CopyChip + status + actions (Revoke, Extend).",
        "Tabs: Activations (table), Audit (timeline), Webhooks (events).",
        "Activations: device name, fingerprint, first seen, last seen, deactivate button."
      ]
    },

    "/admin/products": {
      "layout": [
        "Products table + Create product Dialog.",
        "Product form: Name, Identifier, Signing method (HMAC/RSA), Fingerprint mode (None/HW/Domain/Both).",
        "Advanced: Accordion for key rotation policy + webhook defaults."
      ],
      "data_testid": {
        "create": "products-create-button",
        "signing": "product-signing-method-select",
        "fingerprint": "product-fingerprint-mode-select"
      }
    },

    "/admin/api-keys": {
      "layout": [
        "Header: Create API key.",
        "List: name, created, last used, scopes, status.",
        "Create flow: reveal-once modal with CopyChip + warning callout.",
        "Revoke action is destructive with AlertDialog confirmation."
      ],
      "data_testid": {
        "create": "api-keys-create-button",
        "reveal": "api-key-reveal-once",
        "revoke": "api-key-revoke-button"
      }
    },

    "/admin/builds": {
      "layout": [
        "Builds table: version, product, file/url, created, downloads.",
        "Create build Dialog: upload or URL, version, release notes.",
        "Customer portal consumes same list filtered by product/license."
      ]
    },

    "/admin/webhooks": {
      "layout": [
        "Webhook endpoints config (cards) + events table.",
        "Events: provider icon, event type, delivery status, timestamp, view payload.",
        "Payload viewer: Dialog with ScrollArea + CodeBlock JSON + Copy."
      ]
    },

    "/admin/audit": {
      "layout": [
        "Audit timeline with filters (user, action, date).",
        "Timeline groups by day; each event shows actor avatar, action, target, timestamp, severity badge."
      ]
    },

    "/portal/login & /portal/register": {
      "layout": [
        "Friendlier tone; lighter density.",
        "Card form with clear help text and password rules.",
        "Optional: magic link later; keep simple now."
      ]
    },

    "/portal (Customer dashboard)": {
      "layout": [
        "Top nav: Licenses, Downloads, Support.",
        "Licenses grid: Card per license with status + product + activations count + Manage button.",
        "Downloads list: builds available for their products."
      ],
      "data_testid": {
        "licenses_grid": "portal-licenses-grid",
        "downloads_list": "portal-downloads-list"
      }
    },

    "/portal/licenses/:id": {
      "layout": [
        "License detail page: key CopyChip + status.",
        "Activations list with 'Deactivate' per device (with confirmation).",
        "Downloads section filtered to product."
      ]
    }
  },

  "motion_and_microinteractions": {
    "principles": [
      "Motion is functional: indicates state change, focus, or hierarchy.",
      "Respect prefers-reduced-motion.",
      "No parallax heavy effects; keep subtle."
    ],
    "recommended_library": {
      "name": "framer-motion (optional)",
      "install": "npm i framer-motion",
      "usage": "Use for Drawer/Dialog entrance, list item fade-in, and hero background drift. Keep durations 160-220ms."
    },
    "css_only_fallback": {
      "hover": "transition-colors duration-150",
      "press": "active:scale-[0.98] transition-transform duration-100",
      "cards": "hover:shadow-md shadow-sm transition-shadow duration-150"
    }
  },

  "accessibility": {
    "requirements": [
      "WCAG AA contrast in both themes",
      "Visible focus ring (use --ring emerald)",
      "Keyboard navigation for tables, dialogs, drawers",
      "Use aria-label for icon-only buttons",
      "Prefer semantic headings in docs for TOC"
    ],
    "table_a11y": "Ensure row actions are reachable via keyboard; provide sr-only labels for icon buttons.",
    "reduced_motion": "Disable hero drift and large transitions when prefers-reduced-motion is set."
  },

  "images_and_illustrations": {
    "note": "This product can be mostly illustration-free. Use subtle abstract/security imagery only on landing.",
    "image_urls": [
      {
        "category": "landing_hero_background",
        "description": "Abstract secure/tech texture (used as faint overlay behind hero; keep subtle)",
        "urls": []
      },
      {
        "category": "landing_feature_section",
        "description": "Optional small abstract shapes or terminal screenshot placeholders",
        "urls": []
      }
    ]
  },

  "instructions_to_main_agent": [
    "Remove default CRA App.css centering patterns; do not use .App { text-align:center }.",
    "Update index.css tokens to the emerald ring system above; keep shadcn structure.",
    "Implement theme toggle (dark default) using .dark class on html/body.",
    "Create reusable components: CodeBlock, CopyChip, StatusPill, EmptyState, AuditTimeline, CsvUpload (JS files, not TSX).",
    "Use shadcn Table + Drawer for license detail; Dialog for create/edit; AlertDialog for destructive confirmations.",
    "Every interactive element and key info element must include data-testid in kebab-case.",
    "Use sonner for toasts; show success/error on copy, create, revoke, import.",
    "Docs page: implement 3-column layout with sticky left nav and right TOC on desktop; collapse to Sheet/Collapsible on mobile.",
    "Admin vs Portal distinction: Admin uses denser tables, sidebar, command palette; Portal uses card grids and more whitespace but same tokens."
  ]
}

---

<General UI UX Design Guidelines>  
    - You must **not** apply universal transition. Eg: `transition: all`. This results in breaking transforms. Always add transitions for specific interactive elements like button, input excluding transforms
    - You must **not** center align the app container, ie do not add `.App { text-align: center; }` in the css file. This disrupts the human natural reading flow of text
   - NEVER: use AI assistant Emoji characters like`🤖🧠💭💡🔮🎯📚🎭🎬🎪🎉🎊🎁🎀🎂🍰🎈🎨🎰💰💵💳🏦💎🪙💸🤑📊📈📉💹🔢🏆🥇 etc for icons. Always use **FontAwesome cdn** or **lucid-react** library already installed in the package.json

 **GRADIENT RESTRICTION RULE**
NEVER use dark/saturated gradient combos (e.g., purple/pink) on any UI element.  Prohibited gradients: blue-500 to purple 600, purple 500 to pink-500, green-500 to blue-500, red to pink etc
NEVER use dark gradients for logo, testimonial, footer etc
NEVER let gradients cover more than 20% of the viewport.
NEVER apply gradients to text-heavy content or reading areas.
NEVER use gradients on small UI elements (<100px width).
NEVER stack multiple gradient layers in the same viewport.

**ENFORCEMENT RULE:**
    • Id gradient area exceeds 20% of viewport OR affects readability, **THEN** use solid colors

**How and where to use:**
   • Section backgrounds (not content backgrounds)
   • Hero section header content. Eg: dark to light to dark color
   • Decorative overlays and accent elements only
   • Hero section with 2-3 mild color
   • Gradients creation can be done for any angle say horizontal, vertical or diagonal

- For AI chat, voice application, **do not use purple color. Use color like light green, ocean blue, peach orange etc**

</Font Guidelines>

- Every interaction needs micro-animations - hover states, transitions, parallax effects, and entrance animations. Static = dead. 
   
- Use 2-3x more spacing than feels comfortable. Cramped designs look cheap.

- Subtle grain textures, noise overlays, custom cursors, selection states, and loading animations: separates good from extraordinary.
   
- Before generating UI, infer the visual style from the problem statement (palette, contrast, mood, motion) and immediately instantiate it by setting global design tokens (primary, secondary/accent, background, foreground, ring, state colors), rather than relying on any library defaults. Don't make the background dark as a default step, always understand problem first and define colors accordingly
    Eg: - if it implies playful/energetic, choose a colorful scheme
           - if it implies monochrome/minimal, choose a black–white/neutral scheme

**Component Reuse:**
	- Prioritize using pre-existing components from src/components/ui when applicable
	- Create new components that match the style and conventions of existing components when needed
	- Examine existing components to understand the project's component patterns before creating new ones

**IMPORTANT**: Do not use HTML based component like dropdown, calendar, toast etc. You **MUST** always use `/app/frontend/src/components/ui/ ` only as a primary components as these are modern and stylish component

**Best Practices:**
	- Use Shadcn/UI as the primary component library for consistency and accessibility
	- Import path: ./components/[component-name]

**Export Conventions:**
	- Components MUST use named exports (export const ComponentName = ...)
	- Pages MUST use default exports (export default function PageName() {...})

**Toasts:**
  - Use `sonner` for toasts"
  - Sonner component are located in `/app/src/components/ui/sonner.tsx`

Use 2–4 color gradients, subtle textures/noise overlays, or CSS-based noise to avoid flat visuals.
</General UI UX Design Guidelines>
