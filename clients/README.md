# WatchNexus client libraries

Drop-in clients for the licensing server. Zero install (after one dependency for Python).

## Python (`/python`)

1. Install once: `pip install requests`
2. Copy `python/watchnexus_client.py` into your project.
3. Use it:

```python
from watchnexus_client import WatchNexusClient

client = WatchNexusClient(
    base_url="https://licenses.example.com",
    api_key="wnk_...",          # from /admin/quickstart
    license_key="WNX-...",      # the customer's license
)

token = client.activate(hardware_id="...", domain="...", device_name="...")
state = client.validate(token, hardware_id="...", domain="...")
client.deactivate(token)
```

Features:
- Automatic offline grace fallback (`client.validate` returns `mode="grace_offline"` if the network is down and the local JWT is still within `grace_until`).
- HMAC license verification helper for offline-first products.

## JavaScript / Node.js / Browser (`/javascript`)

Works on Node 18+, modern browsers, Electron, Tauri.

```js
import { WatchNexusClient } from './watchnexus.js';

const client = new WatchNexusClient({
  baseUrl: 'https://licenses.example.com',
  apiKey:  'wnk_...',
  licenseKey: 'WNX-...',
});

const token = await client.activate({ hardware_id, domain, device_name });
const state = await client.validate(token, { hardware_id, domain });
await client.deactivate(token);
```

Same offline-grace behaviour as the Python client.

## .NET / C#

A full minimal client is shown on the **Quickstart** page in the admin panel
(`/admin/quickstart` -> `.NET / C#` tab). Copy/paste it into your project.

## Where do I get my API key?

1. Log into the admin panel at `/admin/login` (default seeded credentials are
   printed by the backend on first boot).
2. Click **Quickstart** in the sidebar.
3. Copy the bootstrap API key. Rotate it any time with the **Rotate** button.

That's everything you need to tie WatchNexus into your app suite.
