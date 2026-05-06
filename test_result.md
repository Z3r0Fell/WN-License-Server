# test_result.md

## Test Plan
This file is updated by the testing agent.

## Backend tests done by main agent (curl smoke tests):
- /api/health -> 200 OK
- /api/admin/login -> issues JWT
- /api/admin/dashboard -> works
- /api/admin/products list/create -> works
- /api/admin/licenses create -> WNX-... key generated
- /api/admin/api-keys create -> works
- /api/integrate/activate -> issues activation token
- /api/integrate/validate -> returns valid online

## Frontend smoke (manual screenshot):
- Landing renders
- Admin login + dashboard render with stats

## Pending: comprehensive testing via testing_agent_v3

## Communication with the testing sub-agent
- Skip drag-drop and camera tests; CSV upload uses native file input.
- Seeded admin: admin@watchnexus.app / admin12345
- Customer must be created via /portal/register
